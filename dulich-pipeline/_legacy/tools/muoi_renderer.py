"""
muoi_renderer.py — Template Muối: dark photo + yellow bold tips + thumbnails.
6-slide format: cover + 5 tip-with-venue slides.
Aesthetic: heavy dark overlay, beviet_bold yellow title, white bullet tips,
           yellow section sub-header, venue list, 2-3 thumb photos at bottom.
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from PIL import Image, ImageDraw
from tools.render_utils import (
    load_bg, load_thumb, beviet_bold, noto,
    draw_pin_icon, draw_text_in_box, save_slide,
)

W, H = 1080, 1280
YELLOW  = (245, 200, 0)     # #F5C800
WHITE   = (255, 255, 255)
DARK_OV = (20, 20, 16, 210) # very dark overlay for tip slides

HOOK_HEADLINES = [
    "LỜI KHUYÊN DÀNH CHO\nNHỮNG AI SẮP ĐI ĐÀ LẠT",
    "ĐÀ LẠT MÙNG LỄ\nĐỌC TRƯỚC KHI ĐI",
    "GHI NHỚ NHỮNG ĐIỀU NÀY\nTRƯỚC KHI ĐẾN ĐÀ LẠT",
]


def _draw_multicolor_title(draw: ImageDraw.Draw, text: str, font,
                            x: int, y: int, key_words: list | None = None) -> int:
    """Draw uppercase title; words in key_words list are yellow, rest white."""
    key_words = key_words or []
    lines = text.split("\n")
    for line in lines:
        words = line.split()
        cur_x = x
        for i, word in enumerate(words):
            clean = word.strip(".,!?")
            color = YELLOW if any(kw.upper() in clean.upper() for kw in key_words) else WHITE
            space_before = "" if i == 0 else " "
            w_text = space_before + word
            draw.text((cur_x, y), w_text, font=font, fill=color)
            cur_x += int(draw.textlength(w_text, font=font))
        y += font.size + 10
    return y


def render_cover(bg_path: str, hook: str, out_path: str,
                 key_words: list | None = None) -> str:
    img = load_bg(bg_path, W, H)
    canvas = img.convert("RGBA")
    canvas.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, 130)))

    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    font_title = beviet_bold(68)
    y = 100
    # Dark pill behind title
    lines = hook.split("\n")
    total_h = len(lines) * (font_title.size + 10)
    max_w = max(int(draw.textlength(l, font=font_title)) for l in lines)
    pad_x, pad_y = 40, 16
    draw.rounded_rectangle(
        [(W // 2 - max_w // 2 - pad_x, y - pad_y),
         (W // 2 + max_w // 2 + pad_x, y + total_h + pad_y)],
        radius=16, fill=(10, 15, 35, 200)
    )

    # Center each line
    for line in lines:
        lw = int(draw.textlength(line, font=font_title))
        col = YELLOW if (key_words and any(k.upper() in line.upper() for k in key_words)) else YELLOW
        draw.text(((W - lw) // 2, y), line, font=font_title, fill=col)
        y += font_title.size + 10

    canvas.alpha_composite(layer)
    out_img = canvas.convert("RGB")
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    out_img.save(out_path, "PNG")
    return out_path


def render_tip_slide(bg_path: str, title: str, body_tips: list,
                     subheader: str, venues: list, thumb_venues: list,
                     out_path: str) -> str:
    """
    bg_path: background photo
    title: bold yellow uppercase headline
    body_tips: list of tip strings (white)
    subheader: yellow sub-section label
    venues: list of venue dicts for bullet list
    thumb_venues: 2-3 venue dicts with _resolved_path for bottom thumbnails
    """
    THUMB_H = 200
    THUMB_Y = H - THUMB_H - 8

    img = load_bg(bg_path, W, H)
    canvas = img.convert("RGBA")
    canvas.alpha_composite(Image.new("RGBA", (W, H), DARK_OV))

    # Bottom thumbnails
    n = min(len(thumb_venues), 3)
    if n > 0:
        tw = (W - (n - 1) * 8) // n
        for i, vn in enumerate(thumb_venues[:n]):
            thumb = load_thumb(vn.get("_resolved_path", ""), (tw, THUMB_H))
            canvas.paste(thumb, (i * (tw + 8), THUMB_Y))

    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    # Title
    y = 80
    font_title = beviet_bold(60)
    y = draw_text_in_box(draw, title, 54, y, W - 100, font_title, YELLOW) + 20

    # Body tips (white)
    font_body = noto(28)
    for tip in body_tips:
        y = draw_text_in_box(draw, f"• {tip}", 54, y, W - 90, font_body, WHITE) + 8
        if y > THUMB_Y - 160:
            break

    # Sub-header in yellow
    if subheader:
        y += 12
        font_sub = beviet_bold(36)
        draw.text((54, y), subheader, font=font_sub, fill=YELLOW)
        y += font_sub.size + 14

    # Venue bullet list (white, with pin icons)
    font_venue = noto(26)
    for vn in venues[:10]:
        name = vn.get("name", "")
        addr = vn.get("address", "")
        if len(addr) > 38:
            addr = addr.split(",")[0]
        draw_pin_icon(draw, 54, y + 4, size=14, color=(232, 60, 74))
        text = f"{name} – {addr}" if addr else name
        y = draw_text_in_box(draw, text, 76, y, W - 100, font_venue, WHITE) + 6
        if y > THUMB_Y - 60:
            break

    # Caption labels under thumbnails
    if n > 0:
        font_cap = noto(20)
        tw_each = (W - (n - 1) * 8) // n
        for i, vn in enumerate(thumb_venues[:n]):
            name = vn.get("name", "")
            cx = i * (tw_each + 8)
            cap_x = cx + 6
            cap_y = THUMB_Y + THUMB_H - font_cap.size - 6
            # dark strip behind caption
            draw.rectangle([(cx, cap_y - 4), (cx + tw_each, THUMB_Y + THUMB_H)],
                           fill=(0, 0, 0, 160))
            draw.text((cap_x, cap_y), name, font=font_cap, fill=WHITE)

    canvas.alpha_composite(layer)
    out_img = canvas.convert("RGB")
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    out_img.save(out_path, "PNG")
    return out_path
