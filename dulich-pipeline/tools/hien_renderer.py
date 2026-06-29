"""
hien_renderer.py — Template Hiền: teal cover + photo venue-list slides.
7-slide format: solid teal cover + 6 photo-overlay venue-list slides.
Aesthetic: DancingScript gold title top-left, white bullet list, dark overlay.
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from PIL import Image, ImageDraw
from tools.render_utils import (
    load_bg, dancing, beviet_bold, noto,
    draw_text_in_box, save_slide,
)

W, H = 1080, 1280
TEAL     = (126, 200, 200)   # #7EC8C8
GOLD     = (200, 168, 75)    # #C8A84B
DK_GREEN = (26, 74, 58)      # #1A4A3A
CREAM    = (245, 240, 232)

HOOK_HEADLINES = [
    "Đà Lạt 72h\nCó đủ không?",
    "Đà Lạt sẽ không\nphụ lòng bạn",
    "Trọn vẹn Đà Lạt\ntrong 72 giờ",
    "Bỏ túi ngay\ncẩm nang Đà Lạt",
]

SLIDE_OVERLAYS = [
    (45,  59, 42, 165),   # slide 2: dark forest green (cafe sáng)
    (180, 80, 20, 145),   # slide 3: warm orange       (cafe check-in)
    (13,  13, 26, 170),   # slide 4: dark navy          (quán ăn)
    (80,  50, 30, 170),   # slide 5: dark warm brown    (ăn vặt)
    (26,  13,  8, 170),   # slide 6: very dark warm     (khách sạn)
    (26,  26, 26, 165),   # slide 7: dark mono          (tham quan)
]


def render_cover(hook: str, out_path: str) -> str:
    canvas = Image.new("RGB", (W, H), TEAL)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    # Notebook decoration at bottom
    nb_y = H - 250
    draw.rounded_rectangle([(0, nb_y), (W, H)], radius=30, fill=(*CREAM, 255))
    draw.line([(60, nb_y + 90), (W - 60, nb_y + 90)], fill=(*GOLD, 190), width=2)
    draw.line([(60, nb_y + 160), (W - 60, nb_y + 160)], fill=(*GOLD, 190), width=2)

    # Title — centered above notebook, beviet_bold dark green
    font_title = beviet_bold(72)
    lines = hook.split("\n")
    line_gap = 14
    total_h = len(lines) * font_title.size + (len(lines) - 1) * line_gap
    y = max(120, (nb_y - total_h) // 2)
    for line in lines:
        tw = int(draw.textlength(line, font=font_title))
        draw.text(((W - tw) // 2, y), line, font=font_title, fill=DK_GREEN)
        y += font_title.size + line_gap

    canvas = canvas.convert("RGBA")
    canvas.alpha_composite(layer)
    out = canvas.convert("RGB")
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    out.save(out_path, "PNG")
    return out_path


def render_venue_list_slide(bg_path: str, title: str, subtitle: str,
                             venues: list, out_path: str,
                             overlay: tuple = (26, 26, 26, 160)) -> str:
    """Photo bg + dark overlay + DancingScript gold title + white bullet list."""
    img = load_bg(bg_path, W, H)
    canvas = img.convert("RGBA")
    canvas.alpha_composite(Image.new("RGBA", (W, H), overlay))

    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    y = 80
    font_title = dancing(64)
    y = draw_text_in_box(draw, title, 60, y, W - 100, font_title, GOLD) + 18

    if subtitle:
        font_sub = noto(26)
        draw.text((60, y), subtitle, font=font_sub, fill=CREAM)
        y += font_sub.size + 22

    font_item = noto(28)
    for v in venues[:16]:
        name = v.get("name", "")
        addr = v.get("address", "")
        if len(addr) > 40:
            addr = addr.split(",")[0]
        line = f"• {name} – {addr}" if addr else f"• {name}"
        y = draw_text_in_box(draw, line, 60, y, W - 80, font_item, (255, 255, 255)) + 6
        if y > H - 60:
            break

    canvas.alpha_composite(layer)
    out_img = canvas.convert("RGB")
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    out_img.save(out_path, "PNG")
    return out_path
