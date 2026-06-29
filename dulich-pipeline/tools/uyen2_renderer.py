# -*- coding: utf-8 -*-
"""
uyen2_renderer.py — Template "Review diary" personal restaurant reviews.
Canvas: 1080x1390px.

Slides:
  0  Cover   : full-bleed venue photo
  1  Intro   : photo bg + white overlay + handwritten title
  2-4 Review : photo bg + white overlay + speech bubble (pin + venue + review)
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from PIL import Image, ImageDraw
from tools.render_utils import load_font, load_bg, save_slide, draw_pin_icon

W, H = 1080, 1390

NAVY = (30, 40, 80)

# (bubble_x, bubble_y, bubble_width) for slides 2, 3, 4
BUBBLE_POSITIONS = [
    (55,  148, 680),   # slide 2: upper-left
    (205, 162, 670),   # slide 3: center
    (362, 1040, 680),  # slide 4: lower-right
]

INTRO_TEXT = "Đà Lạt 3n2d\nĂn theo review gg maps\nvà cái kết :))))"


def _ufont(size):
    return load_font("FCDKCoolCrayon.otf", size)


def _photo_bg(photo_path):
    """venue photo + heavy white overlay -> near-gray bg."""
    img = load_bg(photo_path, W, H)
    canvas = img.convert("RGBA")
    overlay = Image.new("RGBA", (W, H), (255, 255, 255, 235))
    canvas.alpha_composite(overlay)
    return canvas


# ---- Slide 0: Cover ----------------------------------------------------------

def render_cover(bg_path, out_path):
    img = load_bg(bg_path, W, H)
    canvas = img.convert("RGBA")
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    return save_slide(canvas, layer, out_path)


# ---- Slide 1: Intro ----------------------------------------------------------

def render_intro(bg_path, out_path):
    img = load_bg(bg_path, W, H)
    canvas = img.convert("RGBA")
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    font = _ufont(52)
    lines = INTRO_TEXT.split("\n")
    lh = font.size + 14
    y = 58
    for line in lines:
        tw = int(draw.textlength(line, font=font))
        x = (W - tw) // 2
        draw.text((x, y), line, font=font, fill=(255, 255, 255, 255),
                  stroke_width=3, stroke_fill=(20, 20, 20, 255))
        y += lh

    return save_slide(canvas, layer, out_path)


# ---- Slides 2-4: Review slides -----------------------------------------------

def render_review(bg_path, venue, bubble_idx, out_path):
    """
    Photo bg + white overlay + speech bubble containing:
      - red pin icon + venue name
      - review text from venue["signature"] (fallback: address)
    bubble_idx: 0, 1, or 2 -> selects position from BUBBLE_POSITIONS
    """
    img = load_bg(bg_path, W, H)
    canvas = img.convert("RGBA")
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    bx, by, bw = BUBBLE_POSITIONS[bubble_idx % len(BUBBLE_POSITIONS)]
    pad = 22
    name_font = _ufont(30)
    review_font = _ufont(26)

    name = (venue.get("name") or "")[:40]
    review_raw = venue.get("signature") or venue.get("address") or ""
    review_raw = review_raw[:120]

    # Word-wrap review text
    max_line_w = bw - pad * 2 - 32
    words = review_raw.split()
    lines, cur = [], ""
    for word in words:
        test = (cur + " " + word).strip()
        if int(draw.textlength(test, font=review_font)) <= max_line_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)

    # Compute bubble height
    name_h = name_font.size + 8
    review_h = len(lines) * (review_font.size + 7)
    bh = pad + name_h + 10 + review_h + pad

    # Shadow
    draw.rounded_rectangle(
        [(bx + 3, by + 4), (bx + bw + 3, by + bh + 4)],
        radius=22,
        fill=(160, 160, 160, 70),
    )
    # Bubble body
    draw.rounded_rectangle(
        [(bx, by), (bx + bw, by + bh)],
        radius=22,
        fill=(255, 255, 255, 240),
    )

    # Pin icon + venue name
    name_y = by + pad
    draw_pin_icon(draw, bx + pad, name_y + 4, size=18, color=(232, 60, 74))
    draw.text((bx + pad + 26, name_y), name, font=name_font,
              fill=(*NAVY, 255))

    # Review text lines
    text_y = name_y + name_h + 10
    for line in lines:
        draw.text((bx + pad, text_y), line, font=review_font,
                  fill=(*NAVY, 255))
        text_y += review_font.size + 7

    return save_slide(canvas, layer, out_path)
