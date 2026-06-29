# -*- coding: utf-8 -*-
"""
hien21113_renderer.py — Template hiền 21113: minimalist venue spotlight.
Slide 0: POV cover text centered on full-bleed photo.
Slides 1-N: Venue name + pin + address at varied positions — NO BOX, text only.
Canvas: 1080 × 1390px. Font: DancingScript.
"""
from __future__ import annotations
from PIL import Image, ImageDraw
from tools.render_utils import load_bg, dancing, draw_pin_icon, save_slide

W, H = 1080, 1390

HOOK_TEXTS = [
    "POV:\nBạn vừa trải qua mối tình toxic và đang\nđi Đà Lạt để tự chữa lành vết thương ấy",
    "POV:\nBạn vừa được tăng lương và muốn\nthưởng cho mình một chuyến Đà Lạt",
    "POV:\nBạn đặt vé Đà Lạt lúc 2 giờ sáng\nvì không biết làm gì nữa cả",
    "POV:\nBạn và cả nhóm vừa đồng ý\ntuần sau lên Đà Lạt chơi",
]

# (tx, ty) — varied positions per slide index, NO BOX ever
VENUE_POSITIONS = [
    (80,  175),   # upper-left
    (80,  240),   # upper-left, slightly lower
    (530, 400),   # center-right
    (80,  700),   # lower-left
]


def render_cover(bg_path: str, pov_text: str, out_path: str) -> str:
    img = load_bg(bg_path, W, H)
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 60))
    canvas = img.convert("RGBA")
    canvas.alpha_composite(overlay)

    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    font = dancing(64)
    lines = pov_text.split("\n")
    line_h = font.size + 10
    total_h = len(lines) * line_h - 10
    y = H // 2 - total_h // 2 - 40

    for line in lines:
        tw = int(draw.textlength(line, font=font))
        x = (W - tw) // 2
        for ox, oy in [(-2, 0), (2, 0), (0, -2), (0, 2)]:
            draw.text((x + ox, y + oy), line, font=font, fill=(0, 0, 0, 160))
        draw.text((x, y), line, font=font, fill=(255, 255, 255))
        y += line_h

    return save_slide(canvas, layer, out_path)


def render_venue_slide(bg_path: str, name: str, address: str,
                       out_path: str, tx: int = 80, ty: int = 175) -> str:
    """Venue photo + text overlay. NO box/rectangle behind text."""
    img = load_bg(bg_path, W, H)
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 30))
    canvas = img.convert("RGBA")
    canvas.alpha_composite(overlay)

    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    font_name = dancing(50)
    font_addr = dancing(38)

    draw.text((tx, ty), name, font=font_name, fill=(255, 255, 255))
    ty += font_name.size + 12
    pin_size = 16
    draw_pin_icon(draw, tx, ty + (font_addr.size - pin_size) // 2, size=pin_size)
    draw.text((tx + pin_size + 8, ty), address, font=font_addr, fill=(255, 255, 255))

    return save_slide(canvas, layer, out_path)
