"""
News Pipeline — Multi-job batch pipeline for the news channel.
Runs 10-20 clips per day in parallel using ThreadPoolExecutor.

Job lifecycle per clip:
  research → script → brief → voice → subtitle → video → caption → DB save

Resource allocation is controlled by config.max_workers (set from Desktop App
via env vars or CLI args).
"""

from __future__ import annotations

import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import config
from tools.db import create_job, update_job, append_job_log, save_content
from tools.voice_generator import VoiceGenerator
from tools.video_renderer import VideoEngine

# ── Agent imports ─────────────────────────────────────────────────────────────
from agents.research_agent import research_agent
from agents.script_agent import script_agent
from agents.caption_agent import caption_agent
from agents.subtitle_agent import subtitle_agent
from agents.brief_agent import create_brief


def _log(job_id: str, level: str, text: str) -> None:
    """Log to console AND MongoDB job record."""
    print(f"[{level.upper()}] [{job_id[:8]}] {text}")
    try:
        append_job_log(job_id, level, text)
    except Exception:
        pass


def _run_single_job(
    topic: str,
    batch_index: int,
    brief_id: str,
    llm,
    voice_gen: VoiceGenerator,
    video_engine: VideoEngine,
) -> dict:
    """
    Process a single news clip end-to-end.
    Returns a result dict suitable for saving to content collection.
    """
    job_doc = create_job(channel="news", topic=topic, batch_index=batch_index)
    job_id = job_doc["_id"]

    _log(job_id, "info", f"═══ Bắt đầu job #{batch_index + 1}: {topic} ═══")

    try:
        update_job(job_id, {"status": "running", "progress": 5})

        # ── 1. Research (reuse brief data or quick mock) ───────────────────
        import asyncio
        _log(job_id, "info", "[Research] Phân tích xu hướng...")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        res_result = loop.run_until_complete(
            research_agent(
                {"trends": [{"destination": topic, "activity": "general", "sentiment": "positive"}]},
                llm,
            )
        )
        loop.close()
        trends = res_result.get("trends", [{"destination": topic, "activity": "general", "sentiment": "positive"}])
        _log(job_id, "success", f"[Research] ✓ Trends: {[t['destination'] for t in trends[:3]]}")
        update_job(job_id, {"progress": 20})

        # ── 2. Script ──────────────────────────────────────────────────────
        _log(job_id, "info", "[Script] Viết kịch bản...")
        script = script_agent(
            topic=topic,
            trends=trends,
            seeds=[],
            llm=llm,
        )
        _log(job_id, "success", f"[Script] ✓ Hook: {script.get('hook', '')[:60]}...")
        update_job(job_id, {"progress": 35, "script": script})

        # ── 3. Captions ────────────────────────────────────────────────────
        _log(job_id, "info", "[Caption] Tạo caption + hashtags...")
        captions = caption_agent(script=script, video_desc=topic, llm=llm)
        _log(job_id, "success", f"[Caption] ✓ {len(captions.get('hashtags', []))} hashtags")
        update_job(job_id, {"progress": 50, "captions": captions})

        # ── 4. Voice ───────────────────────────────────────────────────────
        _log(job_id, "info", f"[Voice] Tạo giọng nói ({config.voice_provider})...")
        full_text = " ".join([
            script.get("hook", ""),
            script.get("body", ""),
            script.get("cta", ""),
        ])
        output_name = f"news_{batch_index:02d}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        voice_path = voice_gen.generate_voice(
            text=full_text,
            voice_id=config.creator_voices.get("creator1", "default"),
            output_name=output_name,
        )
        _log(job_id, "success", f"[Voice] ✓ Audio: {Path(voice_path).name}")
        update_job(job_id, {"progress": 65, "voice_path": voice_path})

        # ── 5. Subtitle ────────────────────────────────────────────────────
        _log(job_id, "info", "[Subtitle] Tạo phụ đề SRT...")
        sub_result = subtitle_agent(script=script, output_name=output_name)
        subtitle_path = sub_result.get("subtitle_path")
        _log(job_id, "success", f"[Subtitle] ✓ SRT: {Path(subtitle_path).name}")
        update_job(job_id, {"progress": 75, "subtitle_path": subtitle_path})

        # ── 6. Video ───────────────────────────────────────────────────────
        _log(job_id, "info", "[Video] Dựng video...")
        video_path = video_engine.assemble_video(
            clips=[{"path": "", "duration": 10}],
            voiceover_path=voice_path,
            subtitle_path=subtitle_path,
            output_name=output_name,
            template_id="news_9x16",
        )
        _log(job_id, "success", f"[Video] ✓ Video: {Path(video_path).name}")
        update_job(job_id, {"progress": 95, "video_path": video_path})

        # ── 7. Save to DB ──────────────────────────────────────────────────
        result = {
            "job_id": job_id,
            "topic": topic,
            "brief_id": brief_id,
            "script": script,
            "captions": captions,
            "voice_path": voice_path,
            "subtitle_path": subtitle_path,
            "video_path": video_path,
            "batch_index": batch_index,
            "status": "done",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        save_content(job_id=job_id, content_type="video", data=result)
        update_job(job_id, {"status": "done", "progress": 100, "result": result})
        _log(job_id, "success", f"[Done] ✅ Job #{batch_index + 1} hoàn tất!")
        return result

    except Exception as e:
        _log(job_id, "error", f"[Error] ❌ Job #{batch_index + 1} lỗi: {e}")
        update_job(job_id, {"status": "error", "error_message": str(e)})
        return {"job_id": job_id, "topic": topic, "status": "error", "error": str(e)}


def run_news_pipeline(
    topics: list[str],
    api_key: Optional[str] = None,
    max_workers: Optional[int] = None,
) -> dict:
    """
    Run the news channel pipeline for a list of topics in parallel.

    Args:
        topics: List of topics/destinations to produce content for
        api_key: Anthropic API key (overrides config)
        max_workers: Max parallel workers (overrides config.max_workers)

    Returns:
        { "brief": {...}, "results": [...], "total": int, "success": int }
    """
    api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
    workers = max_workers or config.max_workers

    print(f"[NewsPipeline] 🚀 Bắt đầu batch {len(topics)} clips | {workers} workers")

    # ── Init LLM ──────────────────────────────────────────────────────────────
    llm = None
    if api_key and api_key not in ("", "your-anthropic-key"):
        try:
            from langchain_anthropic import ChatAnthropic
            llm = ChatAnthropic(model="claude-haiku-4-5", api_key=api_key)
            print("[NewsPipeline] ✓ LLM: Claude Haiku (cost-optimized for batch)")
        except Exception as e:
            print(f"[NewsPipeline] ⚠ LLM init failed: {e}. Mock mode.")
    else:
        print("[NewsPipeline] ⚠ ANTHROPIC_API_KEY not set. Mock/Free mode.")

    # ── Generate scripts first (brief creation) ───────────────────────────────
    print("[NewsPipeline] Viết kịch bản cho tất cả topics...")
    scripts = []
    for topic in topics:
        script = script_agent(topic=topic, trends=[], seeds=[], llm=llm)
        scripts.append(script)

    # Create brief document
    brief = create_brief(topics=topics, scripts=scripts, channel="news")
    brief_id = brief.get("brief_id", "unknown")

    # ── Init shared tools ─────────────────────────────────────────────────────
    voice_gen = VoiceGenerator(provider=config.voice_provider)
    video_engine = VideoEngine(output_dir=str(Path(config.output_dir) / "videos"))

    # ── Parallel execution ────────────────────────────────────────────────────
    results = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                _run_single_job,
                topic,
                idx,
                brief_id,
                llm,
                voice_gen,
                video_engine,
            ): (topic, idx)
            for idx, topic in enumerate(topics)
        }

        for future in as_completed(futures):
            topic, idx = futures[future]
            try:
                result = future.result()
                results.append(result)
                status = "✅" if result.get("status") == "done" else "❌"
                print(f"[NewsPipeline] {status} Topic {idx+1}/{len(topics)}: {topic}")
            except Exception as e:
                print(f"[NewsPipeline] ❌ Topic {idx+1} exception: {e}")
                results.append({"topic": topic, "status": "error", "error": str(e)})

    # ── Summary ───────────────────────────────────────────────────────────────
    success_count = sum(1 for r in results if r.get("status") == "done")
    print(
        f"[NewsPipeline] 📊 Kết quả: {success_count}/{len(topics)} thành công "
        f"| Brief: {brief_id}"
    )

    # Save batch summary to output
    summary = {
        "brief": brief,
        "results": results,
        "total": len(topics),
        "success": success_count,
        "workers_used": workers,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    output_dir = Path(config.output_dir)
    output_dir.mkdir(exist_ok=True)
    summary_path = output_dir / f"batch_{brief_id}.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[NewsPipeline] 💾 Batch summary: {summary_path}")

    return summary
