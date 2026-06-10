"""
hook_overlay.py — Render the "Đà Lạt review" hook as a transparent PNG overlay (1080x1920).

Reproduces the reference style with three text layers:
  1. Title  — bouncy yellow bubble (Baloo 2), per-letter rotation + hand-drawn sparkle doodles.
  2. Script — white handwriting (Caveat), centered, soft shadow.
  3. Caption — white rounded sans (Be Vietnam Pro) with outline (the spoken subtitle line).

The PNG is meant to be composited over vertical video via FFmpeg overlay.
"""

from __future__ import annotations

import math
import unicodedata
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
TITLE_FONT = FONT_DIR / "Baloo2-VF.ttf"           # variable, use wght=800
SCRIPT_FONT = FONT_DIR / "DancingScript-VF.ttf"   # variable, use wght=700
CAPTION_FONT = FONT_DIR / "BeVietnamPro-Bold-full.ttf"

W, H = 1080, 1920

# Palette tuned to the reference frame
YELLOW = (251, 201, 53, 255)        # warm golden title
CREAM = (255, 248, 231, 255)        # thin outline around title
WHITE = (255, 255, 255, 255)
SHADOW = (0, 0, 0, 110)


def _load(path: Path, size: int, weight: int | None = None) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(str(path), size)
    if weight is not None:
        try:
            f.set_variation_by_axes([weight])
        except Exception:
            pass
    return f


def _wobble(i: int, n: int) -> float:
    """Alternating tilt per letter so the title reads hand-placed, not rigid."""
    base = -7 if i % 2 == 0 else 7
    # nudge the ends inward a touch
    return base * (0.7 + 0.3 * math.cos(math.pi * i / max(n - 1, 1)))


def _draw_bouncy_title(canvas: Image.Image, text: str, cx: int, top: int,
                       font: ImageFont.FreeTypeFont) -> tuple[int, int, int]:
    """Render each glyph on its own layer, rotate, and lay out left-to-right.
    Returns (left, right, bottom) bounding box of the placed title."""
    text = unicodedata.normalize("NFC", text)
    chars = list(text)
    n = len(chars)

    glyphs = []
    total_w = 0
    max_h = 0
    for ch in chars:
        if ch == " ":
            glyphs.append((" ", None, int(font.size * 0.32), 0))
            total_w += int(font.size * 0.32)
            continue
        bb = font.getbbox(ch, stroke_width=10)
        gw, gh = bb[2] - bb[0], bb[3] - bb[1]
        pad = 30
        tile = Image.new("RGBA", (gw + pad * 2, gh + pad * 2), (0, 0, 0, 0))
        d = ImageDraw.Draw(tile)
        # soft drop shadow first
        d.text((pad - bb[0] + 5, pad - bb[1] + 6), ch, font=font, fill=(120, 80, 0, 90),
               stroke_width=10, stroke_fill=(120, 80, 0, 90))
        # cream outline + yellow fill
        d.text((pad - bb[0], pad - bb[1]), ch, font=font, fill=YELLOW,
               stroke_width=10, stroke_fill=CREAM)
        glyphs.append((ch, tile, gw + pad * 2, gh + pad * 2))
        total_w += int(gw + pad * 1.2)
        max_h = max(max_h, gh)

    x = cx - total_w // 2
    left, right, bottom = x, x, top
    for i, (ch, tile, gw, gh) in enumerate(glyphs):
        if tile is None:
            x += gw
            continue
        ang = _wobble(i, n)
        rot = tile.rotate(ang, expand=True, resample=Image.BICUBIC)
        jitter = int(8 * math.sin(i * 1.7))
        py = top + jitter
        canvas.alpha_composite(rot, (x, py))
        right = x + gw
        bottom = max(bottom, py + rot.height)
        x += int(gw * 0.78)
    return left, right, bottom


def _sparkle(d: ImageDraw.ImageDraw, x: int, y: int, r: int, color=CREAM, wdt: int = 7):
    """Hand-drawn 4-point twinkle."""
    d.line([(x - r, y), (x + r, y)], fill=color, width=wdt)
    d.line([(x, y - r), (x, y + r)], fill=color, width=wdt)
    s = int(r * 0.45)
    d.line([(x - s, y - s), (x + s, y + s)], fill=color, width=max(2, wdt - 3))
    d.line([(x - s, y + s), (x + s, y - s)], fill=color, width=max(2, wdt - 3))


def _draw_centered_lines(canvas, lines, font, top, fill, gap, stroke=0,
                         stroke_fill=None, shadow=True):
    d = ImageDraw.Draw(canvas)
    y = top
    for ln in lines:
        bb = d.textbbox((0, 0), ln, font=font, stroke_width=stroke)
        lw, lh = bb[2] - bb[0], bb[3] - bb[1]
        x = (W - lw) // 2 - bb[0]
        if shadow:
            d.text((x + 3, y - bb[1] + 4), ln, font=font, fill=SHADOW, stroke_width=stroke)
        d.text((x, y - bb[1]), ln, font=font, fill=fill,
               stroke_width=stroke, stroke_fill=stroke_fill)
        y += lh + gap
    return y


def build_overlay(
    title: str = "ĐÀ LẠT",
    script_lines: tuple[str, ...] = ("Review và chấm điểm", "các quán mà anh đã đi"),
    caption: str = "anh biết các em đã tốn rất nhiều tiền",
    out_path: str = "output/hook_overlay.png",
    with_caption: bool = True,
) -> str:
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    # 1) Title — bouncy yellow, around 13% from top
    title_font = _load(TITLE_FONT, 150, weight=800)
    l, r, b = _draw_bouncy_title(canvas, title, W // 2, int(H * 0.11), title_font)

    # doodle sparkles around the title
    dd = ImageDraw.Draw(canvas)
    _sparkle(dd, l - 35, int(H * 0.115), 30)
    _sparkle(dd, r + 30, int(H * 0.16), 26)
    _sparkle(dd, r + 5, int(H * 0.10), 18, wdt=5)
    _sparkle(dd, l + 20, b - 10, 16, wdt=5)

    # 2) Handwriting script — white Caveat, just below the title
    script_font = _load(SCRIPT_FONT, 96, weight=700)
    y2 = _draw_centered_lines(canvas, list(script_lines), script_font,
                              top=b + 24, fill=WHITE, gap=4, shadow=True)

    # 3) Spoken caption — bottom third, white rounded with outline
    if with_caption and caption:
        import textwrap
        cap_font = _load(CAPTION_FONT, 60)
        cap_lines = textwrap.wrap(caption, width=24)
        # block height to anchor near 66% of frame
        line_h = cap_font.getbbox("Ay")[3] + 14
        block_top = int(H * 0.66)
        _draw_centered_lines(canvas, cap_lines, cap_font, top=block_top,
                             fill=WHITE, gap=14, stroke=6,
                             stroke_fill=(0, 0, 0, 200), shadow=False)

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out)
    return str(out)


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Render Đà Lạt hook overlay PNG")
    ap.add_argument("--title", default="ĐÀ LẠT")
    ap.add_argument("--script", default="Review và chấm điểm|các quán mà anh đã đi",
                    help="handwriting lines separated by |")
    ap.add_argument("--caption", default="anh biết các em đã tốn rất nhiều tiền")
    ap.add_argument("--no-caption", action="store_true")
    ap.add_argument("--out", default="output/hook_overlay.png")
    args = ap.parse_args()

    p = build_overlay(
        title=args.title,
        script_lines=tuple(args.script.split("|")),
        caption=args.caption,
        out_path=args.out,
        with_caption=not args.no_caption,
    )
    print("Saved:", p)
