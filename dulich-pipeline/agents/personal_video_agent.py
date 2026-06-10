"""
Personal Video Agent — Controls the pipeline for individual creators.
Applies specific voice clones, hook templates, and custom script text.

Pipeline Flow (2 stages):
  Stage 1: run_research_and_script()  → AI generates script + scene plan
  Stage 2: run_assemble_video()       → FFmpeg assembles video from user-uploaded clips
"""

from __future__ import annotations

import os
import sys
import json
import uuid
from pathlib import Path
from typing import Optional

from tools.db import jobs_col, creators_col, content_col, update_job, append_job_log, save_content, new_doc
from tools.voice_generator import VoiceGenerator
from agents.subtitle_agent import generate_srt
from tools.video_renderer import VideoEngine

# Default creators data to seed database
DEFAULT_CREATORS = [
    {
        "_id": "lan_anh",
        "name": "Lan Anh",
        "voice_provider": "vbee",
        "voice_id": "hn_female_lananh",
        "hook_preference": "zoom_in",
        "created_at": "2026-06-09T00:00:00Z",
        "updated_at": "2026-06-09T00:00:00Z",
    },
    {
        "_id": "minh_tuan",
        "name": "Minh Tuấn",
        "voice_provider": "vbee",
        "voice_id": "hn_male_minhtuan",
        "hook_preference": "glitch",
        "created_at": "2026-06-09T00:00:00Z",
        "updated_at": "2026-06-09T00:00:00Z",
    },
    {
        "_id": "thu_ha",
        "name": "Thu Hà",
        "voice_provider": "vbee",
        "voice_id": "hn_female_thutrang",
        "hook_preference": "cinematic_vignette",
        "created_at": "2026-06-09T00:00:00Z",
        "updated_at": "2026-06-09T00:00:00Z",
    },
    {
        "_id": "duc_anh",
        "name": "Đức Anh",
        "voice_provider": "vbee",
        "voice_id": "hcm_male_ducanh",
        "hook_preference": "zoom_out",
        "created_at": "2026-06-09T00:00:00Z",
        "updated_at": "2026-06-09T00:00:00Z",
    },
    {
        "_id": "ngoc_mai",
        "name": "Ngọc Mai",
        "voice_provider": "vbee",
        "voice_id": "hn_female_ngocmai",
        "hook_preference": "zoom_in",
        "created_at": "2026-06-09T00:00:00Z",
        "updated_at": "2026-06-09T00:00:00Z",
    }
]


def ensure_creators_seeded() -> None:
    """Ensure that the 5 default creators are present in MongoDB."""
    try:
        col = creators_col()
        existing_count = col.count_documents({}) if hasattr(col, "count_documents") else len(list(col.find({})))
        if existing_count < 5:
            print(f"[PersonalPipeline] Seeding {5 - existing_count} default creators into database.", file=sys.stderr)
            for c in DEFAULT_CREATORS:
                if not col.find_one({"_id": c["_id"]}):
                    col.insert_one(c)
    except Exception as e:
        print(f"[PersonalPipeline] Warning during seeding creators: {e}", file=sys.stderr)


# ─────────────────────────────────────────────────────────────────────────────
# Scene Plan Generation
# ─────────────────────────────────────────────────────────────────────────────

# Scene type: video clip or image
SCENE_TYPES = ["clip", "image"]

# Preset templates keyed by video template (ratio)
SCENE_PRESETS = {
    "9:16": [  # TikTok / Reels — 4 scenes, ~60s total
        {"description": "Cảnh mở đầu hook — toàn cảnh điểm đến hoặc khoảnh khắc gây tò mò", "min_duration_sec": 5, "type": "clip"},
        {"description": "Giới thiệu địa điểm — cảnh đẹp nổi bật, đặc trưng của vùng", "min_duration_sec": 12, "type": "clip"},
        {"description": "Trải nghiệm cụ thể — ẩm thực, hoạt động, không gian check-in", "min_duration_sec": 18, "type": "clip"},
        {"description": "Kết thúc CTA — cảnh tổng hợp đẹp nhất kèm thông tin liên hệ", "min_duration_sec": 10, "type": "clip"},
    ],
    "1:1": [  # Instagram — 3 scenes, ~30s total
        {"description": "Hook ngắn — khoảnh khắc đặc sắc nhất của chuyến đi", "min_duration_sec": 5, "type": "clip"},
        {"description": "Điểm nhấn nội dung — trải nghiệm hoặc cảnh đẹp nổi bật", "min_duration_sec": 15, "type": "clip"},
        {"description": "Kết thúc — logo hoặc thông tin creator", "min_duration_sec": 8, "type": "clip"},
    ],
    "16:9": [  # YouTube — 6 scenes, ~90-120s total
        {"description": "Intro hook — teaser cảnh đẹp nhất, kích thích xem tiếp", "min_duration_sec": 8, "type": "clip"},
        {"description": "Giới thiệu tổng quan điểm đến — drone shot hoặc cảnh rộng", "min_duration_sec": 15, "type": "clip"},
        {"description": "Trải nghiệm ẩm thực — cận cảnh món ăn đặc sản", "min_duration_sec": 20, "type": "clip"},
        {"description": "Hoạt động vui chơi / cảnh đặc trưng của điểm đến", "min_duration_sec": 20, "type": "clip"},
        {"description": "Lưu trú / không gian nghỉ ngơi — khách sạn, resort, glamping", "min_duration_sec": 15, "type": "clip"},
        {"description": "Outro & CTA — tổng hợp highlight, thông tin đặt tour", "min_duration_sec": 12, "type": "clip"},
    ],
}


def generate_scene_plan(
    topic: str,
    script: dict,
    template_ratio: str = "9:16",
    scene_mode: str = "ai",           # "ai" | "preset" | "custom"
    custom_scenes: list[dict] = None,  # For "custom" mode: [{description, min_duration_sec, type}]
    scene_count: int = 0,              # For "preset" mode override: how many scenes
) -> list[dict]:
    """
    Generate a scene plan based on script and preferences.

    Args:
        topic: Video topic/destination
        script: Dict with hook, body, cta keys
        template_ratio: "9:16" | "1:1" | "16:9"
        scene_mode: 
            "ai"     → AI decides count and descriptions from script context
            "preset" → Use template preset scenes (optionally override count)
            "custom" → User supplied scene list (custom_scenes param)
        custom_scenes: User-defined scenes for "custom" mode
        scene_count: If > 0 in "preset" mode, use that many preset scenes

    Returns:
        List of scene dicts with keys: scene_id, description, min_duration_sec, type
    """
    scenes = []

    if scene_mode == "custom" and custom_scenes:
        for i, s in enumerate(custom_scenes):
            scenes.append({
                "scene_id": f"scene_{i + 1}",
                "description": s.get("description", f"Scene {i + 1}"),
                "min_duration_sec": max(3, int(s.get("min_duration_sec", 10))),
                "type": s.get("type", "clip"),
                "uploaded": False,
                "file_path": None,
            })
        return scenes

    if scene_mode == "preset":
        preset = SCENE_PRESETS.get(template_ratio, SCENE_PRESETS["9:16"])
        if scene_count > 0:
            # Trim or extend preset
            if scene_count <= len(preset):
                preset = preset[:scene_count]
            else:
                # Duplicate last scene to fill
                while len(preset) < scene_count:
                    preset.append({
                        "description": f"Cảnh bổ sung {len(preset) + 1} — thêm nội dung cho video",
                        "min_duration_sec": 10,
                        "type": "clip"
                    })
        for i, s in enumerate(preset):
            scenes.append({
                "scene_id": f"scene_{i + 1}",
                "description": s["description"],
                "min_duration_sec": s["min_duration_sec"],
                "type": s["type"],
                "uploaded": False,
                "file_path": None,
            })
        return scenes

    # "ai" mode — derive scenes intelligently from script
    hook = script.get("hook", "")
    body = script.get("body", "")
    cta = script.get("cta", "")

    # Estimate total video duration from body length (approx 4 chars/sec spoken Vietnamese)
    body_duration = max(10, len(body) / 4)
    hook_duration = max(5, len(hook) / 4)
    cta_duration = max(5, len(cta) / 4)
    total_duration = hook_duration + body_duration + cta_duration

    # Derive number of scenes from template
    ratio_scene_counts = {"9:16": 4, "1:1": 3, "16:9": 6}
    n_scenes = ratio_scene_counts.get(template_ratio, 4)

    # Build scene descriptions from script parts
    body_sentences = [s.strip() for s in body.replace("。", ".").split(".") if len(s.strip()) > 10]

    scene_descriptions = []

    # Scene 1: Hook
    scene_descriptions.append({
        "description": f"Cảnh mở đầu thu hút: {hook[:80]}...",
        "min_duration_sec": round(hook_duration),
        "type": "clip",
    })

    # Middle scenes: from body sentences
    body_per_scene = max(1, len(body_sentences) // max(1, n_scenes - 2))
    for chunk_i in range(n_scenes - 2):
        start = chunk_i * body_per_scene
        end = start + body_per_scene
        chunk_text = ". ".join(body_sentences[start:end]) if body_sentences[start:end] else f"Cảnh {chunk_i + 2} về {topic}"
        scene_descriptions.append({
            "description": f"Scene {chunk_i + 2}: {chunk_text[:100]}",
            "min_duration_sec": round(body_duration / max(1, n_scenes - 2)),
            "type": "clip",
        })

    # Last scene: CTA
    scene_descriptions.append({
        "description": f"Cảnh kết thúc kêu gọi: {cta[:80]}",
        "min_duration_sec": round(cta_duration),
        "type": "clip",
    })

    for i, s in enumerate(scene_descriptions[:n_scenes]):
        scenes.append({
            "scene_id": f"scene_{i + 1}",
            "description": s["description"],
            "min_duration_sec": max(3, s["min_duration_sec"]),
            "type": s["type"],
            "uploaded": False,
            "file_path": None,
        })

    return scenes


# ─────────────────────────────────────────────────────────────────────────────
# Stage 1: Research + Script Generation
# ─────────────────────────────────────────────────────────────────────────────

def run_research_and_script(
    job_id: str,
    creator_id: str,
    script_text: str,
    hook_style: str = "",
    hook_text: str = "",
    provider_override: str = "",
    template_ratio: str = "9:16",
    scene_mode: str = "ai",
    custom_scenes: list[dict] = None,
    scene_count: int = 0,
) -> dict:
    """
    Stage 1: AI researches the topic, writes the script, then generates scene plan.
    Pipeline STOPS here — waits for user to upload media per scene.

    Returns:
        {
            job_id, creator_id, hook_style, voice_provider, voice_id,
            script: {hook, body, cta},
            scenes: [{scene_id, description, min_duration_sec, type, uploaded, file_path}]
        }
    """
    ensure_creators_seeded()
    append_job_log(job_id, "INFO", f"[Stage 1] Bắt đầu Research & Script cho Creator: {creator_id}")

    # ── 1. Parse / Generate Script ──
    script = {"hook": "", "body": "", "cta": ""}
    is_just_topic = len(script_text.strip()) < 60 and "\n" not in script_text

    if is_just_topic:
        append_job_log(job_id, "INFO", f"[Script] Nhận diện đầu vào là chủ đề. Viết kịch bản cho: '{script_text}'...")

        from tools.db import get_seeding_items
        location_keyword = ""
        for word in ["Đà Nẵng", "Hội An", "Phú Quốc", "Nha Trang", "Đà Lạt", "Sapa", "Hà Nội", "Hồ Chí Minh", "Huế", "Ninh Bình"]:
            if word.lower() in script_text.lower():
                location_keyword = word
                break

        seeds = get_seeding_items(location=location_keyword, limit=2)
        if seeds:
            seed_names = ", ".join([s.get("name", "") for s in seeds])
            append_job_log(job_id, "INFO", f"[Script] Tìm thấy địa điểm seeding: {seed_names}")

        from config import config
        if config.anthropic_api_key and config.anthropic_api_key != "your-anthropic-key":
            from agents.script_agent import script_agent
            from langchain_anthropic import ChatAnthropic
            llm = ChatAnthropic(model="claude-3-5-sonnet-20240620", api_key=config.anthropic_api_key)
            try:
                script = script_agent(topic=script_text, trends=[], seeds=seeds, llm=llm)
            except Exception as e:
                append_job_log(job_id, "WARNING", f"[Script] Lỗi LLM: {e}. Dùng mock script.")
                script = _generate_mock_script_with_seeds(script_text, seeds)
        else:
            script = _generate_mock_script_with_seeds(script_text, seeds)
    else:
        if script_text.strip().startswith("{") and script_text.strip().endswith("}"):
            try:
                script = json.loads(script_text)
            except Exception:
                script["body"] = script_text
        else:
            lines = [line.strip() for line in script_text.split("\n") if line.strip()]
            if len(lines) >= 3:
                script["hook"] = lines[0]
                script["body"] = " ".join(lines[1:-1])
                script["cta"] = lines[-1]
            elif len(lines) == 2:
                script["hook"] = lines[0]
                script["body"] = lines[1]
                script["cta"] = "Hãy theo dõi mình để biết thêm nhé!"
            elif len(lines) == 1:
                script["hook"] = "Khám phá cùng mình nhé!"
                script["body"] = lines[0]
                script["cta"] = "Follow kênh mình nha!"
            else:
                script["hook"] = "Cùng đi du lịch nào!"
                script["body"] = "Trải nghiệm chuyến đi tuyệt vời ngày hôm nay."
                script["cta"] = "Nhấn follow để xem thêm video nhé!"

    append_job_log(job_id, "INFO", f"[Script] ✓ Kịch bản hoàn thiện — Hook: '{script['hook'][:50]}...'")

    # ── 2. Retrieve Creator Profile ──
    col = creators_col()
    creator = col.find_one({"_id": creator_id})
    if not creator:
        append_job_log(job_id, "WARNING", f"[Creator] Không tìm thấy '{creator_id}', dùng mặc định.")
        creator = DEFAULT_CREATORS[0]

    voice_provider = provider_override or creator.get("voice_provider", "vbee")
    voice_id = creator.get("voice_id", "hn_female_lananh")
    chosen_hook_style = hook_style or creator.get("hook_preference", "zoom_in")

    # ── 3. Generate Scene Plan ──
    append_job_log(job_id, "INFO", f"[Scenes] Đang tạo kịch bản scene (mode={scene_mode}, ratio={template_ratio})...")

    scenes = generate_scene_plan(
        topic=script_text,
        script=script,
        template_ratio=template_ratio,
        scene_mode=scene_mode,
        custom_scenes=custom_scenes,
        scene_count=scene_count,
    )

    append_job_log(job_id, "INFO", f"[Scenes] ✓ Đã tạo {len(scenes)} scene. Đang chờ user upload media...")

    # Save intermediate state to DB
    update_job(job_id, {
        "status": "waiting_media",
        "stage": "script_done",
        "script": script,
        "scenes": scenes,
        "creator_id": creator_id,
        "voice_provider": voice_provider,
        "voice_id": voice_id,
        "hook_style": chosen_hook_style,
        "hook_text": hook_text or script["hook"],
        "template_ratio": template_ratio,
    })

    return {
        "job_id": job_id,
        "creator_id": creator_id,
        "hook_style": chosen_hook_style,
        "hook_text": hook_text or script["hook"],
        "voice_provider": voice_provider,
        "voice_id": voice_id,
        "script": script,
        "scenes": scenes,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Stage 2: Assemble Video from User-uploaded Scenes
# ─────────────────────────────────────────────────────────────────────────────

def run_assemble_video(
    job_id: str,
    scene_uploads: list[dict],   # [{scene_id, file_path}]
    transition: str = "fade",    # "fade" | "dissolve" | "wipeleft" | "slideright"
) -> dict:
    """
    Stage 2: Assemble real video from user-uploaded scene clips.
    Reads job state from DB to get script, creator info, voice config.

    Returns:
        {video_path, audio_path, srt_path}
    """
    from tools.db import get_db

    append_job_log(job_id, "INFO", "[Stage 2] Bắt đầu ghép video từ các scene đã upload...")

    # ── Load job state ──
    db = get_db()
    jobs = db["jobs"] if hasattr(db, "__getitem__") else None

    job_doc = None
    if jobs is not None:
        job_doc = jobs.find_one({"_id": job_id})

    if not job_doc:
        append_job_log(job_id, "WARNING", "[Stage 2] Không tìm thấy job trong DB — dùng tham số mặc định.")
        job_doc = {}

    script = job_doc.get("script", {"hook": "Xin chào!", "body": "Video du lịch.", "cta": "Follow mình nhé!"})
    creator_id = job_doc.get("creator_id", "lan_anh")
    voice_provider = job_doc.get("voice_provider", "mock")
    voice_id = job_doc.get("voice_id", "hn_female_lananh")
    hook_style = job_doc.get("hook_style", "zoom_in")
    hook_text = job_doc.get("hook_text", script.get("hook", ""))
    scenes_meta = job_doc.get("scenes", [])
    template_ratio = job_doc.get("template_ratio", "9:16")

    # Map scene_id → file_path from uploads
    upload_map = {u["scene_id"]: u.get("file_path", "") for u in scene_uploads}

    # ── 1. Generate Voiceover ──
    update_job(job_id, {"progress": 10, "status": "assembling"})
    append_job_log(job_id, "INFO", f"[Voice] Đang tạo giọng nói AI — Provider: {voice_provider}, Voice: {voice_id}")

    full_speech_text = f"{script['hook']}. {script['body']}. {script['cta']}"
    voice_gen = VoiceGenerator(provider=voice_provider)
    audio_output_name = f"personal_{creator_id}_{job_id[:8]}"

    try:
        audio_path = voice_gen.generate_voice(
            text=full_speech_text,
            voice_id=voice_id,
            output_name=audio_output_name,
        )
        append_job_log(job_id, "INFO", f"[Voice] ✓ Đã sinh audio: {audio_path}")
    except Exception as e:
        append_job_log(job_id, "ERROR", f"[Voice] Lỗi sinh giọng nói: {e}")
        raise e

    # Estimate audio duration
    import wave
    audio_duration = 10.0
    if audio_path.endswith(".wav"):
        try:
            with wave.open(audio_path, "r") as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                audio_duration = frames / float(rate)
        except Exception:
            pass
    else:
        audio_duration = max(5.0, len(full_speech_text) / 12.0)

    append_job_log(job_id, "INFO", f"[Voice] Thời lượng audio: {audio_duration:.1f}s")

    # ── 2. Generate Subtitles ──
    update_job(job_id, {"progress": 25})
    append_job_log(job_id, "INFO", "[Subtitle] Đang tạo phụ đề SRT...")

    hook_len = len(script["hook"])
    body_len = len(script["body"])
    cta_len = len(script["cta"])
    total_len = max(1, hook_len + body_len + cta_len)
    hook_end = (hook_len / total_len) * audio_duration
    body_end = ((hook_len + body_len) / total_len) * audio_duration

    try:
        srt_path = generate_srt(
            script=script,
            output_name=f"sub_{audio_output_name}",
            voice_duration_sec=audio_duration,
            hook_end=hook_end,
            body_end=body_end,
            cta_end=audio_duration,
        )
        append_job_log(job_id, "INFO", f"[Subtitle] ✓ Đã sinh SRT: {srt_path}")
    except Exception as e:
        append_job_log(job_id, "ERROR", f"[Subtitle] Lỗi: {e}")
        srt_path = None

    # ── 3. Build Scene Clip List ──
    update_job(job_id, {"progress": 40})
    append_job_log(job_id, "INFO", f"[Assembly] Đang xây dựng danh sách {len(scenes_meta)} scene để ghép...")

    total_scene_min_dur = sum(s.get("min_duration_sec", 5) for s in scenes_meta) if scenes_meta else audio_duration
    time_scale = audio_duration / max(1.0, total_scene_min_dur)

    clips = []
    for scene in scenes_meta:
        sid = scene.get("scene_id", "")
        file_path = upload_map.get(sid, "")
        min_dur = scene.get("min_duration_sec", 5)
        # Scale duration to match audio, unless user uploaded clip is longer
        scaled_dur = min_dur * time_scale

        clips.append({
            "scene_id": sid,
            "path": file_path,            # Empty string → placeholder black screen
            "duration": scaled_dur,
            "media_type": scene.get("type", "clip"),  # "clip" or "image"
            "description": scene.get("description", ""),
        })

        if file_path:
            append_job_log(job_id, "INFO", f"  ✓ Scene [{sid}]: {os.path.basename(file_path)} ({scaled_dur:.1f}s)")
        else:
            append_job_log(job_id, "WARNING", f"  ⚠ Scene [{sid}]: Không có file → dùng placeholder")

    # If no scenes in DB, fall back to empty placeholder
    if not clips:
        clips = [{"path": "", "duration": audio_duration, "media_type": "clip", "scene_id": "scene_1", "description": ""}]

    # ── 4. Assemble with FFmpeg ──
    update_job(job_id, {"progress": 60})
    append_job_log(job_id, "INFO", f"[FFmpeg] Đang ghép video với transition '{transition}'...")

    video_engine = VideoEngine()
    video_output_name = f"video_personal_{creator_id}_{job_id[:8]}"

    try:
        raw_video = video_engine.assemble_from_scenes(
            clips=clips,
            voiceover_path=audio_path,
            output_name=f"{video_output_name}_raw",
            hook_style=hook_style,
            hook_text=hook_text,
            transition=transition,
            template_ratio=template_ratio,
        )
        append_job_log(job_id, "INFO", f"[FFmpeg] ✓ Video thô: {raw_video}")
    except Exception as e:
        append_job_log(job_id, "ERROR", f"[FFmpeg] Lỗi ghép video: {e}")
        raise e

    # ── 5. Burn Subtitles ──
    update_job(job_id, {"progress": 80})
    final_video = raw_video

    if srt_path:
        append_job_log(job_id, "INFO", "[FFmpeg] Đang chèn phụ đề vào video...")
        try:
            final_video = video_engine.add_subtitles(raw_video, srt_path)
            append_job_log(job_id, "INFO", f"[FFmpeg] ✓ Video hoàn chỉnh: {final_video}")
        except Exception as e:
            append_job_log(job_id, "WARNING", f"[FFmpeg] Lỗi chèn phụ đề: {e} — Dùng video không phụ đề")

    # ── 6. Save Artifact ──
    update_job(job_id, {"progress": 100})

    col = creators_col()
    creator = col.find_one({"_id": creator_id}) or DEFAULT_CREATORS[0]

    content_data = {
        "creator_id": creator_id,
        "creator_name": creator.get("name", creator_id),
        "video_path": final_video,
        "audio_path": audio_path,
        "srt_path": srt_path,
        "script": script,
        "hook_style": hook_style,
        "hook_text": hook_text,
        "voice_provider": voice_provider,
        "voice_id": voice_id,
        "scenes_used": len(clips),
        "transition": transition,
    }

    save_content(job_id=job_id, content_type="personal_video", data=content_data)

    update_job(job_id, {
        "status": "done",
        "result": {
            "video_path": final_video,
            "audio_path": audio_path,
            "creator_id": creator_id,
            "hook_style": hook_style,
            "audio_duration": audio_duration,
        }
    })

    append_job_log(job_id, "INFO", "✅ Job hoàn thành thành công!")

    # Ensure paths are absolute so the browser /open-folder endpoint can use them
    content_data["video_path"] = str(Path(final_video).resolve())
    content_data["audio_path"] = str(Path(audio_path).resolve()) if audio_path else ""
    content_data["srt_path"]   = str(Path(srt_path).resolve())   if srt_path   else ""

    return content_data


# ─────────────────────────────────────────────────────────────────────────────
# Legacy wrapper (kept for backward compatibility with existing Tauri commands)
# ─────────────────────────────────────────────────────────────────────────────

def run_personal_pipeline(
    job_id: str,
    creator_id: str,
    script_text: str,
    media_paths: list[str],
    hook_style: str = "",
    hook_text: str = "",
    provider_override: str = "",
) -> dict:
    """
    Legacy single-stage pipeline. Kept for compatibility.
    Runs Stage 1 then immediately assembles using media_paths as scene files.
    """
    result1 = run_research_and_script(
        job_id=job_id,
        creator_id=creator_id,
        script_text=script_text,
        hook_style=hook_style,
        hook_text=hook_text,
        provider_override=provider_override,
        scene_mode="preset",
    )

    # Map media_paths to scenes
    scenes = result1.get("scenes", [])
    scene_uploads = []
    for i, path in enumerate(media_paths):
        if i < len(scenes):
            scene_uploads.append({"scene_id": scenes[i]["scene_id"], "file_path": path})

    return run_assemble_video(job_id=job_id, scene_uploads=scene_uploads)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _generate_mock_script_with_seeds(topic: str, seeds: list[dict]) -> dict:
    seed_str = ""
    if seeds:
        seed_details = []
        for s in seeds:
            name = s.get("name", "")
            cat = "quán" if s.get("category", "") == "restaurant" else "khách sạn"
            desc = s.get("description", "")
            seed_details.append(f"ghé {cat} {name} ({desc})")
        seed_str = " Và đừng quên " + ", ".join(seed_details)

    return {
        "hook": f"Đừng đi du lịch {topic} nếu bạn chưa biết điều này! 😱",
        "body": f"Hôm nay mình sẽ bật mí cho các bạn hành trình review {topic} siêu chất.{seed_str}. Nơi đây phong cảnh siêu đẹp và người dân cực kỳ mến khách luôn. Mình đã dành 3 ngày 2 đêm khám phá từng ngóc ngách và đây là những điều bạn nhất định phải thử khi đến nơi này.",
        "cta": "Nhấn follow kênh mình để nhận thêm nhiều bí kíp du lịch nhé!",
    }
