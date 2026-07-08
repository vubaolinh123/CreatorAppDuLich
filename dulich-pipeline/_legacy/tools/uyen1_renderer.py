# -*- coding: utf-8 -*-
"""
uyen1_renderer.py — Template "48h ở Đà Lạt": handwritten cute travel carousel.
Canvas: 1080 × 1390px.

Slides:
  0 – Cover      : full-bleed venue photo, no text
  1 – Title      : light grey bg, handwritten "Nếu chỉ có 48h ở / Đà Lạt ★" upper-left
  2 – Map        : illustrated sky + clouds + hills + 4 venue pins + central banner
  3 – Check-in   : 2×2 venue photos (tham quan) + per-photo label + central banner
  4 – Food       : 2×2 venue photos (quán ăn)   + per-photo label + central banner
"""
from __future__ import annotations
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from PIL import Image, ImageDraw
from tools.render_utils import load_font, load_bg, load_thumb, save_slide, draw_pin_icon

W, H = 1080, 1390

# ── Palette ───────────────────────────────────────────────────────────────────
GREY_BG    = (211, 211, 211)
SKY_BLUE   = (185, 225, 248)
HILL_DARK  = (95,  142,  45)
HILL_LIGHT = (155, 205,  70)
BANNER_BG  = (25,  22,   28)
WHITE      = (255, 255, 255)
PIN_RED    = (232,  60,  74)


def _ufont(size: int):
    return load_font("FCDKCoolCrayon.otf", size)


# ── Drawing helpers ───────────────────────────────────────────────────────────

def _draw_cloud(draw: ImageDraw.Draw, cx: int, cy: int, w: int, h: int) -> None:
    """Fluffy cloud: 3 round bumps + wide flat base."""
    fill = (255, 255, 255, 255)
    # Base body
    draw.ellipse([(cx - w // 2, cy - h // 4), (cx + w // 2, cy + h // 2)], fill=fill)
    # Left bump
    lw = int(w * 0.40)
    draw.ellipse([(cx - w // 2 + 6, cy - int(h * 0.88)),
                  (cx - w // 2 + 6 + lw * 2, cy + h // 5)], fill=fill)
    # Center bump (tallest)
    cw = int(w * 0.46)
    draw.ellipse([(cx - cw // 2, cy - int(h * 1.12)),
                  (cx + cw // 2, cy + h // 5)], fill=fill)
    # Right bump
    rw = int(w * 0.38)
    draw.ellipse([(cx + w // 2 - rw * 2 - 6, cy - int(h * 0.85)),
                  (cx + w // 2 - 6, cy + h // 5)], fill=fill)


def _draw_hills_band(draw: ImageDraw.Draw, y_wave: int, y_fill: int,
                     color: tuple, amplitude: int = 38,
                     num_peaks: int = 3, phase_offset: float = 0.0) -> None:
    """Wavy hill polygon: fills from sine-wave top edge down to y_fill."""
    pts = [(0, y_fill)]
    for x in range(0, W + 1, 3):
        phase = phase_offset + (x / W) * math.pi * num_peaks
        y = y_wave + int(math.sin(phase) * amplitude)
        pts.append((x, y))
    pts.append((W, y_fill))
    draw.polygon(pts, fill=(*color, 255))


def _draw_pin_label(draw: ImageDraw.Draw, x: int, y: int, name: str,
                    size: int = 30, color: tuple = WHITE, pin_size: int = 13) -> None:
    """Red location pin + handwritten venue name with 1px drop shadow."""
    font = _ufont(size)
    text_x_offset = pin_size + 7
    # Shadow
    draw_pin_icon(draw, x + 1, y + 2, size=pin_size, color=(0, 0, 0))
    draw.text((x + text_x_offset, y + 1), name, font=font, fill=(0, 0, 0))
    # Foreground
    draw_pin_icon(draw, x, y, size=pin_size, color=PIN_RED)
    draw.text((x + text_x_offset, y), name, font=font, fill=color)


def _draw_star(draw: ImageDraw.Draw, cx: int, cy: int,
               outer_r: int = 8, inner_r: int = 3, color: tuple = WHITE) -> None:
    """4-pointed star drawn as a polygon (no font needed)."""
    pts = []
    for i in range(8):
        angle = math.pi / 4 * i - math.pi / 2
        r = outer_r if i % 2 == 0 else inner_r
        pts.append((cx + int(r * math.cos(angle)), cy + int(r * math.sin(angle))))
    draw.polygon(pts, fill=(*color, 255))


def _draw_banner_pill(draw: ImageDraw.Draw, y_center: int, text: str,
                      font_size: int = 34) -> None:
    """Centered dark rounded pill with white handwritten text + small star decorations."""
    font  = _ufont(font_size)
    tw    = int(draw.textlength(text, font=font))
    star_pad = 54   # extra width for 3 stars on the right
    px, py = 44, 16
    bw = tw + px * 2 + star_pad
    bh = font.size + py * 2
    bx = (W - bw) // 2
    by = y_center - bh // 2
    draw.rounded_rectangle([(bx, by), (bx + bw, by + bh)],
                            radius=bh // 2, fill=(*BANNER_BG, 252))
    text_x = bx + px
    draw.text((text_x, by + py), text, font=font, fill=WHITE)
    # Small star decorations after text
    sx = text_x + tw + 14
    sy = y_center
    _draw_star(draw, sx,      sy,     6, 2, WHITE)
    _draw_star(draw, sx + 20, sy - 5, 4, 1, WHITE)
    _draw_star(draw, sx + 36, sy + 4, 5, 2, WHITE)


# ── Slide 0: Cover ────────────────────────────────────────────────────────────

def render_cover(bg_path: str, out_path: str) -> str:
    """Full-bleed venue photo, no text."""
    img    = load_bg(bg_path, W, H)
    canvas = img.convert("RGBA")
    layer  = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    return save_slide(canvas, layer, out_path)


# ── Slide 1: Title ────────────────────────────────────────────────────────────

def render_title(out_path: str, city: str = "Đà Lạt") -> str:
    """Solid light-grey bg + 2-line handwritten title in upper-left."""
    canvas = Image.new("RGBA", (W, H), (*GREY_BG, 255))
    layer  = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw   = ImageDraw.Draw(layer)

    font  = _ufont(60)
    x, y0 = 55, 310
    draw.text((x, y0),                    "Nếu chỉ có 48h ở", font=font, fill=WHITE)
    draw.text((x, y0 + font.size + 10),   city,               font=font, fill=WHITE)

    # Drawn star decorations after city name (replaces emoji — font doesn't support them)
    city_w = int(draw.textlength(city, font=font))
    sx = x + city_w + 22
    sy = y0 + font.size + 10 + font.size // 2
    _draw_star(draw, sx,      sy - 2,  9, 3, WHITE)
    _draw_star(draw, sx + 28, sy - 10, 5, 2, WHITE)
    _draw_star(draw, sx + 48, sy + 5,  7, 2, WHITE)

    return save_slide(canvas, layer, out_path)


# ── Slide 2: Illustrated Map ──────────────────────────────────────────────────

_MAP_LABEL_XY     = [(115, 102), (505, 300), (715, 672), (42, 1236)]
_MAP_LABEL_COLORS = [WHITE, WHITE, WHITE, WHITE]  # all white including bottom-left on green hill


def render_map(venues: list, out_path: str,
               banner_text: str = "Đi check-in free") -> str:
    """Sky-blue illustrated map with clouds, wavy hills, venue pins, central banner."""
    canvas = Image.new("RGBA", (W, H), (*SKY_BLUE, 255))

    # Subtle vertical gradient on sky
    bg = ImageDraw.Draw(canvas)
    for row in range(H):
        t = row / (H - 1)
        b = min(255, int(SKY_BLUE[2] + (255 - SKY_BLUE[2]) * t * 0.10))
        bg.line([(0, row), (W, row)], fill=(SKY_BLUE[0], SKY_BLUE[1], b, 255))

    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw  = ImageDraw.Draw(layer)

    # Upper hills band
    _draw_hills_band(draw, 443, 622, HILL_DARK,  amplitude=42, num_peaks=3, phase_offset=0.0)
    _draw_hills_band(draw, 464, 622, HILL_LIGHT, amplitude=40, num_peaks=4, phase_offset=1.2)

    # Lower hills band
    _draw_hills_band(draw, 1020, H, HILL_DARK,  amplitude=36, num_peaks=3, phase_offset=0.5)
    _draw_hills_band(draw, 1045, H, HILL_LIGHT, amplitude=24, num_peaks=4, phase_offset=1.8)

    # 4 clouds: TL, TR, BL, BR
    _draw_cloud(draw, 200,  98, 268, 90)
    _draw_cloud(draw, 800,  86, 234, 82)
    _draw_cloud(draw, 195, 700, 248, 88)
    _draw_cloud(draw, 820, 690, 232, 85)

    # Venue pin labels (4 positions across map)
    for i, v in enumerate(venues[:4]):
        lx, ly = _MAP_LABEL_XY[i]
        name   = (v.get("name") or "")[:22]
        _draw_pin_label(draw, lx, ly, name, size=30, color=_MAP_LABEL_COLORS[i], pin_size=24)

    # Central banner pill sitting on upper hills
    _draw_banner_pill(draw, y_center=555, text=banner_text, font_size=34)

    return save_slide(canvas, layer, out_path)


# ── Slides 3 & 4: 2×2 Photo Grid ─────────────────────────────────────────────

_GRID_XY = [(0, 0), (540, 0), (0, 695), (540, 695)]
_PH_W, _PH_H = 540, 695


def render_photo_grid(venues: list, banner_text: str, out_path: str) -> str:
    """2×2 venue photo grid — sharp cuts, per-photo pin label, central banner."""
    canvas = Image.new("RGBA", (W, H), (30, 30, 30, 255))
    layer  = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw   = ImageDraw.Draw(layer)

    for i, v in enumerate(venues[:4]):
        gx, gy   = _GRID_XY[i]
        img_path = v.get("image_path", "")
        thumb    = load_thumb(img_path, (_PH_W, _PH_H))
        canvas.alpha_composite(thumb.convert("RGBA"), dest=(gx, gy))

        name = (v.get("name") or "")[:24]
        _draw_pin_label(draw, gx + 18, gy + 30, name, size=32)

    # Central banner at the horizontal midpoint
    _draw_banner_pill(draw, y_center=695, text=banner_text, font_size=32)

    return save_slide(canvas, layer, out_path)
