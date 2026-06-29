# -*- coding: utf-8 -*-
"""
uyen1tip_renderer.py — Template "Travel Tips" infographic style.
Canvas: 1080x1390px.

Slides:
  0  Cover   : full-bleed venue photo
  1  Intro   : photo bg + white overlay + handwritten caption
  2-6 Tips   : 5 tip slides with header + photo frame + bullets + venue list
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from PIL import Image, ImageDraw
from tools.render_utils import (
    load_font, load_bg, load_thumb, save_slide,
    draw_pin_icon, rounded_thumb, beviet_bold,
)

W, H = 1080, 1390


def _ufont(size):
    return load_font("FCDKCoolCrayon.otf", size)


def _afont(size):
    return load_font("Anton-Regular.ttf", size)


def _photo_bg(photo_path):
    """venue photo + heavy white overlay -> near-gray bg with subtle photo texture."""
    img = load_bg(photo_path, W, H)
    canvas = img.convert("RGBA")
    overlay = Image.new("RGBA", (W, H), (255, 255, 255, 235))
    canvas.alpha_composite(overlay)
    return canvas


def _stroke_text(draw, pos, text, font, fill=(20, 20, 20), stroke_w=3):
    draw.text(pos, text, font=font, fill=fill,
              stroke_width=stroke_w, stroke_fill=(255, 255, 255))


def _wrapped_stroke(draw, x, y, text, font, max_w,
                    fill=(20, 20, 20), stroke_w=3):
    """Word-wrap + stroke-draw. Returns y below last line."""
    words = text.split()
    lines, cur = [], ""
    for word in words:
        test = (cur + " " + word).strip()
        if int(draw.textlength(test, font=font)) <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    lh = font.size + 6
    for line in lines:
        _stroke_text(draw, (x, y), line, font, fill, stroke_w)
        y += lh
    return y


def _fit_header_font(draw, text, max_w):
    """Return largest Anton font where text fits in max_w on one line."""
    for size in range(60, 33, -2):
        f = _afont(size)
        if int(draw.textlength(text, font=f)) <= max_w:
            return f
    return _afont(34)


def _draw_x_icon(draw, x=30, y=22):
    """Green rounded square with white X — replaces emoji."""
    bx2, by2 = x + 85, y + 85
    draw.rounded_rectangle([(x, y), (bx2, by2)], radius=14,
                            fill=(34, 186, 34, 255))
    pad, lw = 18, 9
    draw.line([(x + pad, y + pad), (bx2 - pad, by2 - pad)],
              fill=(255, 255, 255, 255), width=lw)
    draw.line([(bx2 - pad, y + pad), (x + pad, by2 - pad)],
              fill=(255, 255, 255, 255), width=lw)


def _draw_arrow(draw, x, y, size=16):
    """Small yellow right-pointing triangle -> replaces pointing hand emoji."""
    pts = [(x, y), (x + size, y + size // 2), (x, y + size)]
    draw.polygon(pts, fill=(255, 195, 0, 255))


# ---- Slide 0: Cover ----------------------------------------------------------

def render_cover(bg_path, out_path):
    img = load_bg(bg_path, W, H)
    canvas = img.convert("RGBA")
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    return save_slide(canvas, layer, out_path)


# ---- Slide 1: Intro ----------------------------------------------------------

INTRO_TEXT = "Di Da Lat nhieu r nhung gio ce tui moi nhan ra may dieu nay :))))"
INTRO_TEXT_VN = "Đi Đà Lạt nhiều r nhưng giờ ce tụi mới nhận ra mấy điều này :))))"


def render_intro(bg_path, out_path):
    img = load_bg(bg_path, W, H)
    canvas = img.convert("RGBA")
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    font = _ufont(48)
    for size in range(58, 26, -2):
        font = _ufont(size)
        if int(draw.textlength(INTRO_TEXT_VN, font=font)) <= W - 80:
            break

    tw = int(draw.textlength(INTRO_TEXT_VN, font=font))
    x = (W - tw) // 2
    draw.text((x, 160), INTRO_TEXT_VN, font=font,
              fill=(255, 255, 255, 255),
              stroke_width=3, stroke_fill=(20, 20, 20, 255))

    return save_slide(canvas, layer, out_path)


# ---- Slides 2-6: Tip slides --------------------------------------------------

def render_tip(bg_path, photo_path, slide_def, venues, out_path):
    """
    slide_def keys:
      title       str       header title (all caps)
      bullets     list[str] tip bullet points
      section     str       bottom section heading
      n_cols      int       1 or 2
      static_items list[str]  optional static list items (checklist)
      extra_section dict    optional {label, items} for 2nd sub-section
    venues: list of venue dicts from VenuePicker (may be empty for static slides)
    """
    img = load_bg(bg_path, W, H)
    canvas = img.convert("RGBA")
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    # --- Header: X icon + title ---
    _draw_x_icon(draw, x=30, y=22)
    title_max_w = W - 130 - 15
    title_font = _fit_header_font(draw, slide_def["title"], title_max_w)
    title_y_end = _wrapped_stroke(draw, 130, 28, slide_def["title"],
                                  title_font, title_max_w)

    # --- Left photo frame ---
    frame_y = max(138, title_y_end + 12)
    thumb = load_thumb(photo_path, (420, 420))
    rthumb = rounded_thumb(thumb, radius=28)
    canvas.alpha_composite(rthumb, dest=(35, frame_y))

    # --- Right bullet points ---
    bfont = _afont(40)
    bx, by = 490, frame_y
    bmax_w = W - bx - 22
    for bullet in slide_def["bullets"]:
        by = _wrapped_stroke(draw, bx, by, "• " + bullet, bfont, bmax_w, stroke_w=2)
        by += 10

    # --- Bottom box ---
    box_top = frame_y + 420 + 30
    box_top = max(box_top, 635)

    # Pre-calculate items + estimate box height before drawing
    if venues:
        items = [v["name"] for v in venues]
    else:
        items = slide_def.get("static_items") or []
    n_cols = slide_def.get("n_cols", 1)
    extra = slide_def.get("extra_section")

    if n_cols == 2:
        items_h = ((len(items) + 1) // 2) * 52
    else:
        items_h = len(items) * 52
    box_content_h = 24 + 64 + items_h
    if extra:
        box_content_h += 64 + len(extra["items"]) * 52
    box_bottom = min(box_top + box_content_h + 32, H - 40)

    draw.rounded_rectangle(
        [(35, box_top), (1045, box_bottom)],
        radius=24,
        fill=(248, 248, 248, 252),
        outline=(55, 55, 55, 255),
        width=2,
    )

    # Section heading
    hfont = _afont(44)
    hx, hy = 62, box_top + 24
    _draw_arrow(draw, hx, hy + 10, size=18)
    _stroke_text(draw, (hx + 28, hy), slide_def["section"], hfont)

    # Items list
    ifont = _afont(36)
    item_y = hy + hfont.size + 20

    if n_cols == 2:
        mid = (len(items) + 1) // 2
        col_a, col_b = items[:mid], items[mid:]
        for i in range(max(len(col_a), len(col_b))):
            if i < len(col_a):
                _stroke_text(draw, (62, item_y + i * 48),
                             "• " + col_a[i], ifont, stroke_w=2)
            if i < len(col_b):
                _stroke_text(draw, (555, item_y + i * 48),
                             "• " + col_b[i], ifont, stroke_w=2)
        item_y += max(len(col_a), len(col_b)) * 48
    else:
        for item in items:
            item_y = _wrapped_stroke(draw, 62, item_y, "• " + item, ifont, 960,
                                     stroke_w=2)
            item_y += 6

    # Optional extra sub-section (e.g., transport info after accommodation)
    if extra and item_y + 60 < box_bottom:
        item_y += 22
        _draw_arrow(draw, hx, item_y + 10, size=18)
        _stroke_text(draw, (hx + 28, item_y), extra["label"], hfont)
        item_y += hfont.size + 16
        for item in extra["items"]:
            item_y = _wrapped_stroke(draw, 62, item_y, "• " + item, ifont, 960,
                                     stroke_w=2)
            item_y += 6

    return save_slide(canvas, layer, out_path)
