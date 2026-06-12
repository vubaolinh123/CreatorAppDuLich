"""frame_learner.py — Learning pipeline: upload → extract → analyze → store.

Handles batch import of Canva frame PNGs (single file or ZIP archive),
runs two-pass analysis, and stores results in MongoDB.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import uuid
import zipfile
from pathlib import Path
from typing import Optional

from tools.db import frame_templates_col, now_utc
from tools.frame_analyzer import analyze_frame, make_thumbnail
from tools.vision_provider import VisionProvider

# Canva frame sets often ship in standard aspect ratios
FORMAT_RATIO_MAP: dict[str, list[str]] = {
    "story": (1080, 1920, ["story", "reels_cover"]),
    "feed_square": (1080, 1080, ["feed_square", "carousel_slide", "seeding_card"]),
    "feed_portrait": (1080, 1350, ["feed_portrait"]),
    "youtube_thumb": (1280, 720, ["youtube_thumb"]),
    "pinterest": (1000, 1500, ["pinterest"]),
    "facebook_cover": (820, 312, ["facebook_cover"]),
    "blog_header": (1200, 630, ["blog_header"]),
}

FRAMES_ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets" / "frames"
FRAMES_ASSETS_DIR.mkdir(parents=True, exist_ok=True)


def _resolve_aspect_ratio(w: int, h: int) -> list[str]:
    """Map (w, h) to compatible format names."""
    ratio = w / h if h > 0 else 0
    compatible = []
    for fmt, (fw, fh, names) in FORMAT_RATIO_MAP.items():
        fmt_ratio = fw / fh
        if abs(ratio - fmt_ratio) < 0.05:
            compatible.extend(names)
        # Also match if one is multiple of the other (e.g. 1080x1920 == 2160x3840)
        if w % fw == 0 and h % fh == 0:
            compatible.extend(names)
    return list(set(compatible)) or ["story"]  # default fallback


def _detect_known_dimensions(w: int, h: int) -> Optional[tuple[int, int]]:
    """Check if dimensions match any known format, return (fw, fh) or None."""
    for fmt, (fw, fh, _) in FORMAT_RATIO_MAP.items():
        if w == fw and h == fh:
            return (fw, fh)
    return None


def learn_single_frame(
    png_path: str,
    creator_id: str = "system",
    vision: Optional[VisionProvider] = None,
    name: Optional[str] = None,
) -> dict:
    """Analyze a single Canva frame PNG and store as a learned template.

    Args:
        png_path: Path to PNG file.
        creator_id: Who uploaded this frame.
        vision: Optional VisionProvider for AI-based analysis.
        name: Optional human-readable name.

    Returns:
        Stored frame template dict.
    """
    from PIL import Image

    png_path = str(Path(png_path).resolve())
    if not os.path.exists(png_path):
        raise FileNotFoundError(f"Frame not found: {png_path}")

    # Open to check dimensions
    with Image.open(png_path) as img:
        w, h = img.size

    # Copy file to assets/frames with stable name
    frame_id = f"frame_{uuid.uuid4().hex[:12]}"
    ext = Path(png_path).suffix or ".png"
    dest_path = FRAMES_ASSETS_DIR / f"{frame_id}{ext}"
    import shutil
    shutil.copy2(png_path, str(dest_path))

    # Pass 1 + Pass 2 analysis
    analysis = analyze_frame(str(dest_path), vision=vision)

    # Determine compatible formats
    compatible = _resolve_aspect_ratio(analysis["width"], analysis["height"])

    # Generate thumbnail
    thumb_path = make_thumbnail(str(dest_path))

    # Build metadata
    doc = {
        "frame_id": frame_id,
        "name": name or f"Khung Canva {w}x{h}",
        "original_path": str(dest_path),
        "thumbnail_path": thumb_path,
        "uploaded_by": creator_id,
        "uploaded_at": now_utc().isoformat(),
        "source_type": "canva_upload",
        "width": analysis["width"],
        "height": analysis["height"],
        "aspect_ratio": f"{w}x{h}",
        "analysis": analysis,
        "compatible_formats": compatible,
        "usage_count": 0,
        "last_used_at": None,
        "rating": 0.0,
    }

    frame_templates_col().insert_one(doc)
    print(f"[FrameLearner] Learned frame '{doc['name']}' ({w}x{h}, {len(compatible)} formats)")
    return doc


def learn_from_zip(
    zip_path: str,
    creator_id: str = "system",
    vision: Optional[VisionProvider] = None,
) -> list[dict]:
    """Extract and learn all PNG frames from a ZIP archive.

    Args:
        zip_path: Path to ZIP file containing Canva frame PNGs.
        creator_id: Who uploaded this.
        vision: Optional VisionProvider.

    Returns:
        List of stored frame template dicts.
    """
    zip_path = str(Path(zip_path).resolve())
    if not os.path.exists(zip_path):
        raise FileNotFoundError(f"ZIP not found: {zip_path}")

    results = []
    with zipfile.ZipFile(zip_path, "r") as zf:
        png_files = [f for f in zf.namelist() if f.lower().endswith(".png")]

        if not png_files:
            print(f"[FrameLearner] No PNG files found in {zip_path}")
            return []

        print(f"[FrameLearner] Found {len(png_files)} PNG(s) in ZIP")

        for i, name in enumerate(png_files):
            try:
                # Extract to temp
                data = zf.read(name)
                suffix = Path(name).suffix or ".png"
                with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                    tmp.write(data)
                    tmp_path = tmp.name

                frame_name = Path(name).stem.replace("_", " ").title()
                doc = learn_single_frame(tmp_path, creator_id, vision, name=frame_name)
                results.append(doc)

                os.unlink(tmp_path)
            except Exception as e:
                print(f"[FrameLearner] Error processing '{name}': {e}", file=sys.stderr)

    print(f"[FrameLearner] ✓ Learned {len(results)}/{len(png_files)} frames")
    return results


def list_learned_frames(
    creator_id: Optional[str] = None,
    format_name: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    """Query stored frame templates."""
    query: dict = {}
    if creator_id:
        query["uploaded_by"] = creator_id
    if format_name:
        query["compatible_formats"] = format_name

    docs = list(
        frame_templates_col().find(query).sort("uploaded_at", -1).limit(limit)
    )
    return docs


def delete_frame(frame_id: str) -> bool:
    """Delete a frame template and its files."""
    doc = frame_templates_col().find_one({"frame_id": frame_id})
    if not doc:
        return False

    # Clean up files
    for path_key in ["original_path", "thumbnail_path"]:
        p = doc.get(path_key)
        if p and os.path.exists(p):
            os.unlink(p)

    frame_templates_col().delete_one({"frame_id": frame_id})
    print(f"[FrameLearner] Deleted frame '{frame_id}'")
    return True
