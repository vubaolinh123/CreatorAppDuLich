"""
uyn_renderer.py — Template UYN: photo-first 2x2 grid carousel.
7-slide format: cover photo → intro hook → 5x 2x2 grid slides.
Aesthetic: DancingScript section banner at grid center, red pin labels per cell.
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from PIL import Image, ImageDraw
from tools.render_utils import (
    load_bg, load_thumb, dancing, noto, beviet_bold,
    draw_pin_icon, draw_text_in_box, save_slide,
)

W, H = 1080, 1280

HOOK_TEXTS = [
    "Nếu chỉ có 48h\nở Đà Lạt",
    "48h ở Đà Lạt\nbạn sẽ làm gì?",
    "Đà Lạt 2 ngày\nnên đi đâu?",
]


def render_cover(bg_path: str, out_path: str) -> str:
    """Slide 1: pure photo, no text."""
    img = load_bg(bg_path, W, H)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG")
    return out_path


def render_intro_hook(bg_path: str, hook_text: str, out_path: str) -> str:
    """Slide 2: photo + mild dark overlay + DancingScript sticker top-left."""
    img = load_bg(bg_path, W, H)
    canvas = img.convert("RGBA")
    canvas.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, 90)))

    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    font = dancing(60)
    draw_text_in_box(draw, hook_text, 60, 90, W - 120, font, (255, 255, 255))

    canvas.alpha_composite(layer)
    out_img = canvas.convert("RGB")
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    out_img.save(out_path, "PNG")
    return out_path


def _pin_label(draw: ImageDraw.Draw, x: int, y: int, text: str, font) -> None:
    """Draw red pin icon + venue name text."""
    draw_pin_icon(draw, x, y + 2, size=16, color=(232, 60, 74))
    draw.text((x + 22, y), text, font=font, fill=(255, 255, 255))


def render_grid_slide(venues_4: list, section_title: str, out_path: str) -> str:
    """Slides 3-7: 2x2 photo grid + white center banner + red pin labels."""
    CW, CH = W // 2, H // 2
    gap = 4
    cell_w = CW - gap // 2
    cell_h = CH - gap // 2

    canvas = Image.new("RGB", (W, H), (20, 20, 20))
    positions = [
        (0, 0),
        (CW + gap // 2, 0),
        (0, CH + gap // 2),
        (CW + gap // 2, CH + gap // 2),
    ]
    for vn, (px, py) in zip(venues_4, positions):
        thumb = load_thumb(vn.get("_resolved_path", ""), (cell_w, cell_h))
        canvas.paste(thumb, (px, py))

    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    # Dark gradients: top 70px and bottom 70px of every cell
    for px, py in positions:
        for i in range(70):
            a_top = int(170 * (1.0 - i / 70))
            draw.line([(px, py + i), (px + cell_w, py + i)], fill=(0, 0, 0, a_top))
            a_bot = int(150 * i / 70)
            draw.line([(px, py + cell_h - 1 - i), (px + cell_w, py + cell_h - 1 - i)],
                      fill=(0, 0, 0, a_bot))

    # Center pill banner — width = text + padding, NOT full width
    font_banner = dancing(52)
    tw = int(draw.textlength(section_title, font=font_banner))
    banner_h = 60
    banner_w = tw + 72
    bx = (W - banner_w) // 2
    by = CH - banner_h // 2 - gap // 2
    draw.rounded_rectangle([(bx, by), (bx + banner_w, by + banner_h)],
                           radius=30, fill=(255, 255, 255, 230))
    draw.text((bx + 36, by + (banner_h - font_banner.size) // 2),
              section_title, font=font_banner, fill=(26, 26, 26))

    # Varied pin label positions per cell (not all top-left)
    # cell 0 top-left: top of cell
    # cell 1 top-right: bottom of cell (near center banner)
    # cell 2 bottom-left: top of cell (just below center)
    # cell 3 bottom-right: bottom of cell
    pad = 14
    Y_OFFSETS = [
        pad,                     # cell 0: near top
        cell_h - 52,             # cell 1: near bottom of top-right cell
        pad + 4,                 # cell 2: near top of bottom-left cell
        cell_h - 52,             # cell 3: near bottom of bottom-right cell
    ]
    font_pin = noto(22)
    for i, (vn, (px, py)) in enumerate(zip(venues_4, positions)):
        name = vn.get("name", "")
        _pin_label(draw, px + pad, py + Y_OFFSETS[i], name, font_pin)

    canvas = canvas.convert("RGBA")
    canvas.alpha_composite(layer)
    out_img = canvas.convert("RGB")
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    out_img.save(out_path, "PNG")
    return out_path
