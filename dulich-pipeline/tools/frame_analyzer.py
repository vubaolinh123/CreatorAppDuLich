"""frame_analyzer.py — Two-pass Canva frame analysis.

Pass 1: Pixel-level analysis (PIL, deterministic, free).
Pass 2: Vision AI (Gemini/GPT-4o, semantic understanding).

Output: unified JSON dict describing frame structure.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

from PIL import Image

from tools.vision_provider import VisionProvider

# numpy is optional — fallback to pure PIL if unavailable
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    np = None
    HAS_NUMPY = False

FRAMES_DIR = Path(__file__).resolve().parent.parent / "assets" / "frames"
FRAMES_DIR.mkdir(parents=True, exist_ok=True)


# ── Pass 1: Pixel Analysis ──────────────────────────────────────────────────


def _dominant_colors(arr, n: int = 4) -> list[str]:
    """Extract n dominant hex colors from an RGBA pixel array (ignoring transparent)."""
    if not HAS_NUMPY:
        return ["#7c3aed", "#4f46e5"]
    mask = arr[:, :, 3] > 50  # ignore near-transparent
    if not mask.any():
        return ["#000000"]
    pixels = arr[mask][:, :3]  # RGB only
    # Simple quantisation: round to nearest 32 and count
    quantized = (pixels // 64) * 64
    unique_rows, counts = np.unique(quantized, axis=0, return_counts=True)
    top_idx = np.argsort(counts)[-n:][::-1]
    return ["#%02x%02x%02x" % tuple(unique_rows[i]) for i in top_idx]


def _detect_transparent_regions(arr: np.ndarray) -> list[dict]:
    """Find bounding boxes of all transparent (alpha==0) regions."""
    alpha = arr[:, :, 3]
    transparent = alpha < 10
    if not transparent.any():
        return []

    # Label connected components
    try:
        from scipy import ndimage

        labeled, num = ndimage.label(transparent)
    except ImportError:
        # Fallback: treat entire transparent area as one region
        ys, xs = np.where(transparent)
        if len(xs) == 0:
            return []
        return [
            {
                "x": int(xs.min()),
                "y": int(ys.min()),
                "w": int(xs.max() - xs.min()),
                "h": int(ys.max() - ys.min()),
                "type": "image_area",
            }
        ]

    regions = []
    for i in range(1, num + 1):
        ys, xs = np.where(labeled == i)
        if len(xs) < 100:  # skip tiny specks
            continue
        regions.append(
            {
                "x": int(xs.min()),
                "y": int(ys.min()),
                "w": int(xs.max() - xs.min()),
                "h": int(ys.max() - ys.min()),
                "type": "image_area",
            }
        )
    return regions


def _detect_border(arr: np.ndarray) -> dict:
    """Scan edges for non-transparent border bands."""
    h, w = arr.shape[:2]
    alpha = arr[:, :, 3]

    top = 0
    for y in range(min(200, h)):
        if alpha[y, :].mean() > 30:
            top = y
        else:
            break

    bottom = 0
    for y in range(h - 1, max(h - 200, 0) - 1, -1):
        if alpha[y, :].mean() > 30:
            bottom = h - y
        else:
            break

    left = 0
    for x in range(min(200, w)):
        if alpha[:, x].mean() > 30:
            left = x
        else:
            break

    right = 0
    for x in range(w - 1, max(w - 200, 0) - 1, -1):
        if alpha[:, x].mean() > 30:
            right = w - x
        else:
            break

    colors = _dominant_colors(arr[:, :4], n=2)
    return {
        "top": top,
        "bottom": bottom,
        "left": left,
        "right": right,
        "style": "solid" if top > 0 else "none",
        "dominant_colors": colors,
    }


def _detect_header_footer(arr: np.ndarray, border: dict) -> dict:
    """Detect header/footer bands from the top/bottom edges."""
    h, w = arr.shape[:2]
    alpha = arr[:, :, 3]

    # Header: find first horizontal band with low alpha after the border
    header_height = 0
    for y in range(border["top"], min(border["top"] + 300, h)):
        row_alpha = alpha[y, :].mean()
        if row_alpha > 100:
            header_height = y - border["top"] + 1

    # Footer: scan from bottom
    footer_height = 0
    for y in range(h - border["bottom"] - 1, max(h - border["bottom"] - 300, 0), -1):
        row_alpha = alpha[y, :].mean()
        if row_alpha > 100:
            footer_height = h - border["bottom"] - y

    return {
        "header": {
            "exists": header_height > 30,
            "height": header_height,
            "background": "dark_solid" if header_height > 30 else "none",
            "text_areas": [],
        },
        "footer": {
            "exists": footer_height > 30,
            "height": footer_height,
            "text_areas": [],
        },
    }


def pixel_analysis(image_path: str) -> dict:
    """Pass 1: pure pixel-level structural analysis (no AI cost)."""
    if not HAS_NUMPY:
        print("[FrameAnalyzer] numpy not available — using basic PIL analysis")
        img = Image.open(image_path).convert("RGBA")
        w, h = img.size
        return {
            "width": w, "height": h,
            "transparent_regions": [],
            "border": {"top": 0, "bottom": 0, "left": 0, "right": 0, "style": "none", "dominant_colors": ["#7c3aed"]},
            "header": {"exists": False, "height": 0, "background": "none", "text_areas": []},
            "footer": {"exists": False, "height": 0, "text_areas": []},
            "color_palette": ["#7c3aed", "#4f46e5"],
            "style_tags": [],
            "decorations": [],
        }
    import numpy as np
    img = Image.open(image_path).convert("RGBA")
    arr = np.array(img)
    h, w = arr.shape[:2]

    border = _detect_border(arr)
    transparent = _detect_transparent_regions(arr)
    hf = _detect_header_footer(arr, border)
    palette = _dominant_colors(arr[:, :4], n=5)

    return {
        "width": w,
        "height": h,
        "transparent_regions": transparent,
        "border": border,
        "header": hf["header"],
        "footer": hf["footer"],
        "color_palette": palette,
        "style_tags": [],
        "decorations": [],
    }


# ── Pass 2: Vision AI merge ─────────────────────────────────────────────────


def merge_analysis(pixel: dict, ai: dict) -> dict:
    """Merge pixel analysis (precise sizes) with AI analysis (semantic)."""
    merged = dict(pixel)

    # AI overrides for semantic fields
    if ai.get("border"):
        merged["border"]["style"] = ai["border"].get("style", pixel["border"]["style"])
        if ai["border"].get("dominant_colors"):
            merged["border"]["dominant_colors"] = ai["border"]["dominant_colors"]

    if ai.get("header") and ai["header"].get("exists"):
        merged["header"]["background"] = ai["header"].get("background", "dark_solid")
        merged["header"]["text_areas"] = ai["header"].get("text_areas", [])

    if ai.get("footer") and ai["footer"].get("exists"):
        merged["footer"]["text_areas"] = ai["footer"].get("text_areas", [])

    if ai.get("decorations"):
        merged["decorations"] = ai["decorations"]

    if ai.get("style_tags"):
        merged["style_tags"] = ai["style_tags"]

    if ai.get("color_palette"):
        merged["color_palette"] = ai["color_palette"]

    return merged


# ── Public API ──────────────────────────────────────────────────────────────


def analyze_frame(image_path: str, vision: Optional[VisionProvider] = None) -> dict:
    """Full two-pass analysis. Returns frame metadata dict.

    Args:
        image_path: Path to PNG frame file.
        vision: Optional VisionProvider (skip AI pass if None).

    Returns:
        Dict with keys: width, height, transparent_regions, border,
        header, footer, color_palette, style_tags, decorations.
    """
    # Pass 1
    pixel_data = pixel_analysis(image_path)
    print(f"[FrameAnalyzer] Pass 1 done: {pixel_data['width']}x{pixel_data['height']}, "
          f"{len(pixel_data['transparent_regions'])} transparent region(s)")

    # Pass 2
    if vision is not None:
        try:
            ai_data = vision.analyze_frame(image_path)
            print(f"[FrameAnalyzer] Pass 2 (Vision AI) done: "
                  f"{len(ai_data.get('style_tags', []))} tags, "
                  f"{len(ai_data.get('decorations', []))} decorations")
            return merge_analysis(pixel_data, ai_data)
        except Exception as e:
            print(f"[FrameAnalyzer] Pass 2 failed: {e}. Using pixel data only.", file=sys.stderr)

    return pixel_data


def scale_frame_to_format(frame_path: str, target_w: int, target_h: int) -> str:
    """Scale a frame to fit target dimensions, preserving aspect ratio."""
    frame = Image.open(frame_path).convert("RGBA")
    fw, fh = frame.size

    scale = min(target_w / fw, target_h / fh)
    new_size = (int(fw * scale), int(fh * scale))
    scaled = frame.resize(new_size, Image.Resampling.LANCZOS)

    canvas = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
    x = (target_w - new_size[0]) // 2
    y = (target_h - new_size[1]) // 2
    canvas.paste(scaled, (x, y), scaled)

    out_name = f"scaled_{target_w}x{target_h}_{Path(frame_path).name}"
    out_path = FRAMES_DIR / out_name
    canvas.save(str(out_path), "PNG")
    return str(out_path)


def make_thumbnail(frame_path: str, max_size: int = 240) -> str:
    """Generate a small thumbnail PNG for gallery display."""
    img = Image.open(frame_path).convert("RGBA")
    w, h = img.size
    scale = max_size / max(w, h)
    thumb = img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)

    # Composite onto dark background for gallery display
    bg = Image.new("RGBA", (max_size, max_size), (17, 12, 46, 255))
    x = (max_size - thumb.width) // 2
    y = (max_size - thumb.height) // 2
    bg.paste(thumb, (x, y), thumb)

    out_path = FRAMES_DIR / f"thumb_{Path(frame_path).name}"
    bg.save(str(out_path), "PNG")
    return str(out_path)
