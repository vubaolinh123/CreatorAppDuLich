"""
uyn1311_renderer.py — Template T4 "Nếu chỉ có 48h ở Đà Lạt" (UYN 13/11).
Canvas: 1080×1390px (7 pages).

Pages:
  0 – Cover (full-bleed photo, no text)
  1 – Title (full-bleed photo + "Nếu chỉ có 48h ở Đà Lạt" text)
  2 – Check-in grid  (Đi check-in free ✩°𓏲⋆ 🌿)
  3 – Café grid      (Đi cafe vibe ĐL ✩°𓏲⋆ 🍵)
  4 – Activities grid (Đi chơi ✩°𓏲⋆ 🌳)
  5 – Food grid      (Đi ănggg ✩°𓏲⋆ 😋)
  6 – Dessert grid   (Đi tráng miệng ✩°𓏲⋆ 🧋)

Fonts:
  FCDKCoolCrayon.otf — FC DK Cool Crayon Regular (ID: YAG0j0qVSfU_0)

Measurements from Canva DOM (SCALE ≈ 1.827, canvas 1080×1390px):
  Title text:
    Line 1 "Nếu chỉ có 48h ở":  cx=59,  cy=311, size=40px, white
    Line 2 "Đà Lạt 🏕️ ⋆⭒˚. 🌿 ⚘.⋆": cx=42, cy=367, size=40px, white
  Grid section header: cy=669, size=33px, white
  Location labels: size=33px, white on dark photos or navy on light photos
  Grid layout:
    Upper-left photo:      x=0,   y=0,   w=537, h=649
    Upper-right-top photo: x=549, y=0,   w=531, h=314
    Upper-right-bot photo: x=549, y=326, w=531, h=323
    Section bar:           y=649, h=44
    Lower-left-top photo:  x=0,   y=693, w=537, h=344
    Lower-left-bot photo:  x=0,   y=1049,w=537, h=341
    Lower-right photo:     x=549, y=693, w=531, h=697
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw

from tools.render_utils import (
    load_bg as _load_bg_util,
    load_thumb as _load_thumb,
    load_font,
    draw_pin_icon,
)

W, H = 1080, 1390

WHITE      = (255, 255, 255)
DARK_NAVY  = (5, 10, 48)
BLACK      = (0, 0, 0)

# Grid layout constants
UPPER_H          = 649
HEADER_Y         = UPPER_H       # 649
HEADER_H         = 44
LOWER_Y          = HEADER_Y + HEADER_H  # 693
LOWER_H          = H - LOWER_Y          # 697
GAP              = 12
COL_A            = 537
COL_B            = W - COL_A - GAP      # 531
UPPER_RIGHT_TOP  = 314
UPPER_RIGHT_BOT  = UPPER_H - UPPER_RIGHT_TOP - GAP  # 323
LOWER_LEFT_TOP   = 344
LOWER_LEFT_BOT   = LOWER_H - LOWER_LEFT_TOP - GAP   # 341


def _fccdk(size: int):
    return load_font("FCDKCoolCrayon.otf", size)


def _emoji_font(size: int):
    """Segoe UI Emoji — hỗ trợ Vietnamese + emoji + Unicode symbols."""
    for path in (
        "C:/Windows/Fonts/seguiemj.ttf",
        "C:/Windows/Fonts/seguisym.ttf",
    ):
        try:
            from PIL import ImageFont as _IF
            return _IF.truetype(path, size)
        except Exception:
            pass
    return _fccdk(size)


def _load_bg(path: str, blur: bool = False, alpha: int = 0) -> Image.Image:
    return _load_bg_util(path, W, H, blur, alpha)


def _label(draw: ImageDraw.Draw, text: str, x: int, y: int, dark: bool = False) -> None:
    font = _fccdk(33)
    color = DARK_NAVY if dark else WHITE
    pin_color = DARK_NAVY if dark else WHITE
    # Draw pin icon then text
    pin_size = 20
    draw_pin_icon(draw, x, y + 6, size=pin_size, color=pin_color)
    tx = x + pin_size + 6
    if not dark:
        draw.text((tx + 2, y + 2), text, font=font, fill=(0, 0, 0, 120))
    draw.text((tx, y), text, font=font, fill=color)


# ── Page 0: Cover ─────────────────────────────────────────────────────────────

def render_cover(bg_path: str, out_path: str) -> str:
    img = _load_bg(bg_path)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG")
    return out_path


# ── Page 1: Title ─────────────────────────────────────────────────────────────

def render_title(bg_path: str, out_path: str) -> str:
    img = _load_bg(bg_path, alpha=30)
    canvas = img.convert("RGBA")
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    font = _fccdk(40)
    line1 = "Nếu chỉ có 48h ở"
    line2 = "Da Lat ~ . ~ . ~"
    for txt, xy in [(line1, (59, 311)), (line2, (42, 367))]:
        draw.text((xy[0] + 2, xy[1] + 2), txt, font=font, fill=(0, 0, 0, 140))
        draw.text(xy, txt, font=font, fill=WHITE)

    canvas.alpha_composite(layer)
    rgb = canvas.convert("RGB")
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    rgb.save(out_path, "PNG")
    return out_path


# ── Pages 2-6: Grid pages ─────────────────────────────────────────────────────

# Photo slot definitions: (x, y, w, h, label_x_offset, label_y_offset, dark_label)
_SLOTS = [
    # Upper section
    (0,           0,           COL_A, UPPER_H,         40,  70,  False),  # 0: upper-left tall
    (COL_A + GAP, 0,           COL_B, UPPER_RIGHT_TOP, 560, 70,  False),  # 1: upper-right-top
    (COL_A + GAP, UPPER_RIGHT_TOP + GAP, COL_B, UPPER_RIGHT_BOT, 560, UPPER_RIGHT_TOP + GAP + 50, False),  # 2: upper-right-bot
    # Lower section
    (0,           LOWER_Y,                    COL_A, LOWER_LEFT_TOP, 40,  LOWER_Y + 60, False),  # 3: lower-left-top
    (0,           LOWER_Y + LOWER_LEFT_TOP + GAP, COL_A, LOWER_LEFT_BOT, 40, LOWER_Y + LOWER_LEFT_TOP + GAP + 60, True),  # 4: lower-left-bot (often light bg)
    (COL_A + GAP, LOWER_Y,                   COL_B, LOWER_H,         560, LOWER_Y + 60, False),  # 5: lower-right tall
]


@dataclass
class GridVenue:
    name: str
    photo_path: str
    slot: int = -1  # auto-assign if -1


def render_grid_page(section_header: str, venues: list[GridVenue],
                     out_path: str) -> str:
    """
    Render a 6-slot photo mosaic page.
    venues: list of up to 6 GridVenue objects (auto-distributed across slots 0-5).
    section_header: e.g. "Đi check-in free ✩°𓏲⋆ 🌿"
    """
    canvas = Image.new("RGB", (W, H), (240, 235, 225))
    draw_base = ImageDraw.Draw(canvas)

    # Place photos
    for i, slot in enumerate(_SLOTS):
        sx, sy, sw, sh, lx, ly, dark = slot
        if i < len(venues):
            v = venues[i]
            thumb = _load_thumb(v.photo_path, (sw, sh))
            canvas.paste(thumb, (sx, sy))

    # Section header bar
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.rectangle([(0, HEADER_Y), (W, HEADER_Y + HEADER_H)],
                           fill=(10, 10, 10, 200))

    font_hdr = _emoji_font(28)
    bbox = overlay_draw.textbbox((0, 0), section_header, font=font_hdr)
    tw = bbox[2] - bbox[0]
    hdr_x = (W - tw) // 2
    hdr_y = HEADER_Y + (HEADER_H - (bbox[3] - bbox[1])) // 2
    overlay_draw.text((hdr_x, hdr_y), section_header, font=font_hdr, fill=WHITE)

    rgba_canvas = canvas.convert("RGBA")
    rgba_canvas.alpha_composite(overlay)
    canvas = rgba_canvas.convert("RGB")

    # Draw location labels on top of photos
    draw = ImageDraw.Draw(canvas)
    for i, slot in enumerate(_SLOTS):
        sx, sy, sw, sh, lx, ly, dark = slot
        if i < len(venues):
            v = venues[i]
            _label(draw, v.name, lx, ly, dark=dark)

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, "PNG")
    return out_path
