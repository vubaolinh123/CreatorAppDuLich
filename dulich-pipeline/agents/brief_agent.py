"""
Brief Agent — Creates a "brief" document for a news video.

A brief contains:
  - Unique brief_id
  - Date / topic
  - Expected script outline
  - Google Drive folder path where human uploads source media
  - Status tracking

The brief is saved to:
  1. MongoDB (briefs collection)
  2. output/briefs/<brief_id>.json  (for offline reading by the Desktop App)
  3. A Google Drive folder is created/documented for this brief
"""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

from tools.db import save_brief, briefs_col

OUTPUT_BRIEFS_DIR = Path("./output/briefs")
OUTPUT_BRIEFS_DIR.mkdir(parents=True, exist_ok=True)


def _generate_brief_id() -> str:
    today = date.today().strftime("%Y%m%d")
    short_uuid = str(uuid.uuid4())[:6].upper()
    return f"BRIEF-{today}-{short_uuid}"


def create_brief(
    topics: list[str],
    scripts: list[dict],
    channel: str = "news",
    drive_base_folder: str = "DuLichApp/01_Source/NewsChannel",
) -> dict:
    """
    Create a brief document for one batch of topics.

    Args:
        topics: List of destination/topic strings
        scripts: List of script dicts (one per topic)
        channel: "news" | "personal"
        drive_base_folder: Base Drive folder path

    Returns:
        The brief document dict (also saved to DB + JSON file)
    """
    brief_id = _generate_brief_id()
    today_str = date.today().isoformat()
    drive_folder = f"{drive_base_folder}/{brief_id}"

    # Build per-topic entries
    entries = []
    for i, (topic, script) in enumerate(zip(topics, scripts)):
        entries.append({
            "index": i + 1,
            "topic": topic,
            "script": script,
            "expected_clips": _estimate_clips_needed(script),
            "drive_subfolder": f"{drive_folder}/{i+1:02d}_{_slugify(topic)}",
            "source_status": "waiting",  # waiting | uploaded | processing | done
        })

    brief = {
        "brief_id": brief_id,
        "date": today_str,
        "channel": channel,
        "total_topics": len(topics),
        "drive_folder": drive_folder,
        "entries": entries,
        "status": "open",  # open | closed | done
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "notes": (
            f"Upload source media vào Google Drive folder: {drive_folder}\n"
            f"Mỗi topic có subfolder riêng. Sau khi upload xong, "
            f"bấm 'Mark Ready' trên Desktop App để pipeline bắt đầu xử lý."
        ),
    }

    # Save to MongoDB
    try:
        saved = save_brief(brief)
        brief["_id"] = saved.get("_id", brief_id)
    except Exception as e:
        print(f"[Brief] ⚠ MongoDB save failed: {e}")
        brief["_id"] = brief_id

    # Save to local JSON
    json_path = OUTPUT_BRIEFS_DIR / f"{brief_id}.json"
    json_path.write_text(
        json.dumps(brief, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[Brief] ✓ Brief created: {brief_id} ({len(topics)} topics)")
    print(f"[Brief]   Drive folder: {drive_folder}")
    print(f"[Brief]   Local JSON:   {json_path}")

    return brief


def update_brief_entry_status(
    brief_id: str,
    entry_index: int,
    status: str,
) -> None:
    """
    Update the source_status of a single entry in the brief.
    status: "waiting" | "uploaded" | "processing" | "done"
    """
    try:
        col = briefs_col()
        col.update_one(
            {"brief_id": brief_id},
            {
                "$set": {
                    f"entries.{entry_index}.source_status": status,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            },
        )
    except Exception as e:
        print(f"[Brief] ⚠ Update entry failed: {e}")

    # Also update local JSON
    json_path = OUTPUT_BRIEFS_DIR / f"{brief_id}.json"
    if json_path.exists():
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            for entry in data.get("entries", []):
                if entry.get("index") == entry_index + 1:
                    entry["source_status"] = status
                    break
            json_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass


def get_open_briefs() -> list[dict]:
    """Return all briefs with status='open' from MongoDB (or local folder)."""
    try:
        col = briefs_col()
        return list(col.find({"status": "open"}))
    except Exception:
        pass

    # Fallback: read from local JSON files
    briefs = []
    for json_file in sorted(OUTPUT_BRIEFS_DIR.glob("BRIEF-*.json")):
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            if data.get("status") == "open":
                briefs.append(data)
        except Exception:
            continue
    return briefs


def list_local_briefs() -> list[dict]:
    """List all local brief JSON files (for Desktop App display)."""
    briefs = []
    for json_file in sorted(OUTPUT_BRIEFS_DIR.glob("BRIEF-*.json"), reverse=True):
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            briefs.append(data)
        except Exception:
            continue
    return briefs


# ── Helpers ───────────────────────────────────────────────────────────────────

def _estimate_clips_needed(script: dict) -> int:
    """Rough estimate: 1 clip per 5 seconds of content."""
    total_chars = sum(len(v) for v in script.values() if isinstance(v, str))
    duration_sec = total_chars / 12  # ~12 chars/sec Vietnamese
    return max(3, int(duration_sec / 5))


def _slugify(text: str) -> str:
    """Convert topic to a safe folder name."""
    import re
    text = text.lower().strip()
    text = re.sub(r"[àáạảãâầấậẩẫăằắặẳẵ]", "a", text)
    text = re.sub(r"[èéẹẻẽêềếệểễ]", "e", text)
    text = re.sub(r"[ìíịỉĩ]", "i", text)
    text = re.sub(r"[òóọỏõôồốộổỗơờớợởỡ]", "o", text)
    text = re.sub(r"[ùúụủũưừứựửữ]", "u", text)
    text = re.sub(r"[ỳýỵỷỹ]", "y", text)
    text = re.sub(r"[đ]", "d", text)
    text = re.sub(r"[^a-z0-9\s]", "", text)
    text = re.sub(r"\s+", "_", text)
    return text[:30]
