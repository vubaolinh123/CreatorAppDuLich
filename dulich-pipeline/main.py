"""
Main entry point — Run the content production pipeline.

Usage:
  # Single clip (personal / legacy mode)
  python main.py --topic "Đà Nẵng"

  # News batch (10-20 clips/day)
  python main.py --channel news --batch 5 --topics "Đà Nẵng,Hội An,Phú Quốc,Hà Giang,Nha Trang"

  # Control worker count
  python main.py --channel news --batch 3 --workers 2

  # With API keys
  python main.py --channel news --batch 5 --provider vbee
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Fix Windows encoding
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).parent))

from config import config

# Default topic pool for news channel (used when --topics not provided)
DEFAULT_TOPICS = [
    "Đà Nẵng biển đẹp mùa hè",
    "Hội An phố cổ về đêm",
    "Phú Quốc resort cao cấp",
    "Hà Giang mùa hoa tam giác mạch",
    "Nha Trang lặn biển san hô",
    "Đà Lạt cafe view đẹp",
    "Sapa trekking bản làng",
    "Mũi Né cồn cát đỏ",
    "Ninh Bình tràng an",
    "Huế ẩm thực cung đình",
]


def main():
    parser = argparse.ArgumentParser(description="DuLichApp Content Pipeline")

    # Common
    parser.add_argument("--topic", type=str, default="Vietnam travel", help="Single topic")
    parser.add_argument("--channel", type=str, default="personal",
                        choices=["personal", "news"],
                        help="Channel type: personal | news")
    parser.add_argument("--provider", type=str, default=config.voice_provider,
                        choices=["vbee", "elevenlabs", "mock"],
                        help="Voice provider")
    parser.add_argument("--sheet-id", type=str, default="", help="Google Sheet ID")

    # News channel specific
    parser.add_argument("--batch", type=int, default=1,
                        help="Number of clips to produce (news channel)")
    parser.add_argument("--workers", type=int, default=config.max_workers,
                        help="Max parallel workers")
    parser.add_argument("--topics", type=str, default="",
                        help="Comma-separated topics list (news channel)")

    # Personal channel specific
    parser.add_argument("--creator", type=str, default="", help="Creator ID")
    parser.add_argument("--script", type=str, default="", help="Script text")
    parser.add_argument("--clips", type=str, default="", help="Comma-separated raw clips paths")
    parser.add_argument("--hook-style", type=str, default="", help="Hook effect style")
    parser.add_argument("--hook-text", type=str, default="", help="Hook overlay text")


    # Resource config (from Desktop App UI)
    parser.add_argument("--ram-gb", type=float, default=config.ram_gb,
                        help="Available RAM in GB (used to auto-cap workers)")
    parser.add_argument("--cpu-cores", type=int, default=config.cpu_cores,
                        help="Available CPU cores")

    # Album generation action specific
    parser.add_argument("--action", type=str, default="video", choices=["video", "album"],
                        help="Action type: video | album")
    parser.add_argument("--title", type=str, default="Khám phá Việt Nam", help="Album main title text")
    parser.add_argument("--subtitle", type=str, default="Những hành trình tuyệt vời", help="Album subtitle text")
    parser.add_argument("--frame", type=str, default="", help="Path to custom Canva frame template")

    args = parser.parse_args()

    # ── Apply resource config ─────────────────────────────────────────────────
    config.voice_provider = args.provider
    config.max_workers = min(args.workers, args.cpu_cores, _ram_to_workers(args.ram_gb))
    config.ram_gb = args.ram_gb
    config.cpu_cores = args.cpu_cores

    print(f"[Config] Channel: {args.channel} | Voice: {args.provider}")
    print(f"[Config] Workers: {config.max_workers} | RAM: {args.ram_gb}GB | CPU: {args.cpu_cores} cores")

    if not config.anthropic_api_key or config.anthropic_api_key == "your-anthropic-key":
        print("[WARNING] ANTHROPIC_API_KEY not set. Running in Mock/Free Mode...")

    # ── Run pipeline ──────────────────────────────────────────────────────────
    try:
        if args.action == "album":
            _run_album_channel(args)
        elif args.channel == "news":
            _run_news_channel(args)
        else:
            _run_personal_channel(args)
    except Exception as e:
        print(f"[FATAL] Pipeline failed: {e}")
        sys.exit(1)


def _run_news_channel(args) -> None:
    """Run multi-job news pipeline."""
    from graph.news_pipeline import run_news_pipeline

    # Build topics list
    if args.topics:
        topics = [t.strip() for t in args.topics.split(",") if t.strip()]
    else:
        n = min(args.batch, len(DEFAULT_TOPICS))
        topics = DEFAULT_TOPICS[:n]

    print(f"[NewsPipeline] Topics ({len(topics)}): {topics}")

    summary = run_news_pipeline(
        topics=topics,
        api_key=config.anthropic_api_key,
        max_workers=config.max_workers,
    )

    print("\n" + "═" * 60)
    print(f"[DONE] Batch hoàn tất!")
    print(f"  ✅ Thành công : {summary['success']} / {summary['total']}")
    print(f"  📁 Brief ID   : {summary['brief']['brief_id']}")
    print(f"  📂 Drive folder: {summary['brief']['drive_folder']}")
    print("═" * 60)

    # Save latest_run.json for Tauri desktop client
    output_dir = Path(config.output_dir)
    output_dir.mkdir(exist_ok=True)
    latest_run = {
        "channel": "news",
        "batch_id": summary["brief"]["brief_id"],
        "total": summary["total"],
        "success": summary["success"],
        "topics": [r.get("topic") for r in summary["results"]],
        "results": summary["results"],
        "brief": summary["brief"],
    }
    latest_path = output_dir / "latest_run.json"
    latest_path.write_text(
        json.dumps(latest_run, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[SUCCESS] Saved to {latest_path}")

    # Sync to dashboard if configured
    _sync_to_dashboard(latest_run)


def _run_personal_channel(args) -> None:
    """Run single-clip personal channel pipeline."""
    if args.creator:
        # Run new Personal Creator pipeline
        from agents.personal_video_agent import run_personal_pipeline
        from tools.db import create_job
        
        # Create a MongoDB job document
        job = create_job(channel="personal", topic=args.topic or "Personal Creator Video", creator_id=args.creator)
        job_id = job["_id"]
        
        clips = [c.strip() for c in args.clips.split(",") if c.strip()] if args.clips else []
        
        print(f"[PersonalPipeline] Job ID: {job_id} | Creator: {args.creator}")
        result = run_personal_pipeline(
            job_id=job_id,
            creator_id=args.creator,
            script_text=args.script or args.topic or "Review du lịch cá nhân.",
            media_paths=clips,
            hook_style=args.hook_style,
            hook_text=args.hook_text,
            provider_override=args.provider
        )
        
        # Save latest_run.json
        output_dir = Path(config.output_dir)
        output_dir.mkdir(exist_ok=True)
        run_data = {
            "channel": "personal",
            "job_id": job_id,
            "creator_id": args.creator,
            "video_path": result.get("video_path", ""),
            "audio_path": result.get("audio_path", ""),
            "script": result.get("script", {}),
            "hook_style": result.get("hook_style", ""),
            "hook_text": result.get("hook_text", ""),
        }
        latest_path = output_dir / "latest_run.json"
        latest_path.write_text(
            json.dumps(run_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"[SUCCESS] Personal run saved to {latest_path}")
        _sync_to_dashboard(run_data)
        return

    # Legacy mode
    from graph.pipeline import run_pipeline

    print(f"[PersonalPipeline] Topic: {args.topic}")

    result = run_pipeline(
        trends=[{"destination": args.topic, "activity": "general", "sentiment": "positive"}],
        api_key=config.anthropic_api_key,
    )

    print("[Pipeline] Complete!")
    print(f"  Video: {result.get('video_path', 'N/A')}")
    print(f"  Captions: {result.get('captions', {})}")

    # Save latest_run.json
    output_dir = Path(config.output_dir)
    output_dir.mkdir(exist_ok=True)
    run_data = {
        "channel": "personal",
        "topic": args.topic,
        "video_path": result.get("video_path", ""),
        "audio_path": result.get("video_path", "").replace(".mp4", ".mp3").replace("videos", "audio"),
        "script": result.get("script", {
            "hook": f"Bạn đã nghe về {args.topic} chưa?",
            "body": f"Hôm nay mình sẽ review {args.topic}...",
            "cta": "Follow nha!",
        }),
        "captions": result.get("captions", {
            "caption_short": f"Khám phá {args.topic}",
            "caption_long": f"Hành trình khám phá {args.topic}...",
            "hashtags": ["#dulich", f"#{args.topic.split()[0].lower()}"],
        }),
        "image_assets": result.get("image_assets", []),
    }
    latest_path = output_dir / "latest_run.json"
    latest_path.write_text(
        json.dumps(run_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[SUCCESS] Saved to {latest_path}")
    _sync_to_dashboard(run_data)


def _run_album_channel(args) -> None:
    """Run album image generation pipeline."""
    from agents.image_agent import run_album_pipeline
    from tools.db import create_job
    
    # Create MongoDB job
    job = create_job(channel="album", topic=args.topic, creator_id=args.creator or "lan_anh")
    job_id = job["_id"]
    
    print(f"[AlbumPipeline] Job ID: {job_id} | Topic: {args.topic}")
    result = run_album_pipeline(
        job_id=job_id,
        topic=args.topic,
        title=args.title,
        subtitle=args.subtitle,
        creator_id=args.creator or "lan_anh",
        canva_template_path=args.frame
    )
    
    # Save latest_run.json
    output_dir = Path(config.output_dir)
    output_dir.mkdir(exist_ok=True)
    run_data = {
        "channel": "album",
        "job_id": job_id,
        "topic": args.topic,
        "title": args.title,
        "subtitle": args.subtitle,
        "images": result.get("images", {}),
    }
    latest_path = output_dir / "latest_run.json"
    latest_path.write_text(
        json.dumps(run_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[SUCCESS] Album run saved to {latest_path}")
    _sync_to_dashboard(run_data)



def _sync_to_dashboard(payload: dict) -> None:
    """Post result to dashboard API if configured."""
    if not config.dashboard_url:
        return
    try:
        import requests
        res = requests.post(
            f"{config.dashboard_url}/api/videos",
            json=payload,
            timeout=10,
        )
        if res.status_code == 200:
            print(f"[Sync] ✓ Dashboard synced: {config.dashboard_url}")
        else:
            print(f"[Sync] ⚠ Sync failed: HTTP {res.status_code}")
    except Exception as e:
        print(f"[Sync] ⚠ Could not sync: {e}")


def _ram_to_workers(ram_gb: float) -> int:
    """
    Auto-cap workers based on available RAM.
    Each worker uses ~500MB for Python + ffmpeg overhead.
    """
    return max(1, int(ram_gb / 0.5))


if __name__ == "__main__":
    main()
