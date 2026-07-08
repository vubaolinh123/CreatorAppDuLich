"""
hien25111_renderer.py — Renderer cho template T6 "Cập nhật tình hình đèo Đà Lạt".
Canvas: 1080 × 1480px (confirmed from Canva DOM).

Pages:
  0 – Cover (background photo + badge + title)
  1 – Road status list (dark bg, text sections)
  2 – Inside Dalat update (light bg, split layout)
  3-5 – Venue grid (white bg, 3×3 photo grid)

Fonts (all in assets/fonts/):
  MTDSummerShow.otf       → MTD Summer Show (cover title)
  MTDSummerShow-Badge.otf → MTD Cheese Sauce (badge + section headers)
  MTDSummerShow2.otf      → MTD Quaver (decorative accent)
  Alata-Regular.ttf       → Alata Regular (body text)

Measurements from Canva DOM (SCALE=2.4, canvas 1080x1480):
  Page 0 badge:      x=399 y=372 w=280 h=79, MTD Cheese Sauce 59px, yellow
  Page 0 title line1: x=95 y=506 w=888, MTD Summer Show 104px, stroke 4px
  Page 0 title line2: same x/w, y=624
  Page 1 title:       y=267, Alata 38px white
  Page 1 sections:    y=[366,648,882], items step 47px
  Pages 3-5 title:    y=96, MTD Cheese Sauce 70px, dark red
  Pages 3-5 photo:    cols=[48,412,776], rows=[180,560,980], 274×330px
  Pages 3-5 text:     name at y=[525,907,1330], addr at y=[566,948,1371]
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw

from tools.render_utils import (
    mtd_summer_show as _mtd, mtd_cheese_sauce as _mcs, mtd_quaver as _mtq,
    alata as _alata,
    load_bg as _load_bg_util,
    load_thumb as _load_thumb, rounded_thumb as _rounded_thumb,
)

W, H = 1080, 1480

YELLOW     = (255, 233, 142)
DARK_OLIVE = (77, 63, 8)
DARK_RED   = (142, 12, 17)
WHITE      = (255, 255, 255)
BLACK      = (0, 0, 0)
BADGE_BG   = (40, 33, 6)


def _load_bg(path: str, blur: bool = False, alpha: int = 0) -> Image.Image:
    return _load_bg_util(path, W, H, blur, alpha)


def _draw_centered(draw: ImageDraw.Draw, text: str, y: int, font,
                   color: tuple, x0: int = 0, w: int = W,
                   stroke_w: int = 0, stroke_col: tuple = BLACK) -> None:
    bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_w)
    tw = bbox[2] - bbox[0]
    tx = x0 + (w - tw) // 2
    draw.text((tx, y), text, font=font, fill=color,
              stroke_width=stroke_w, stroke_fill=stroke_col)


def _composite(canvas: Image.Image, layer: Image.Image, out_path: str) -> str:
    canvas.alpha_composite(layer)
    rgb = canvas.convert("RGB")
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    rgb.save(out_path, "PNG")
    return out_path


# ── Page 0: Cover ─────────────────────────────────────────────────────────────

def render_cover(bg_path: str, title_line1: str, title_line2: str,
                 out_path: str, location: str = "Đà Lạt") -> str:
    """Cover: full-bleed photo + badge + 2-line title."""
    img = _load_bg(bg_path, blur=False, alpha=40)
    canvas = img.convert("RGBA")
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    # Badge background — dark pill at (399, 372, 280×79)
    BX, BY, BW, BH = 399, 372, 280, 79
    draw.rounded_rectangle([(BX, BY), (BX + BW, BY + BH)],
                            radius=39, fill=(*BADGE_BG, 220))

    # Badge text
    font_badge = _mcs(59)
    bbox = draw.textbbox((0, 0), location, font=font_badge)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text((BX + (BW - tw) // 2 - bbox[0], BY + (BH - th) // 2 - bbox[1]),
              location, font=font_badge, fill=YELLOW)

    # Title — 2 lines at y=506 and y=624, auto-shrink cho vừa khung
    for i, line in enumerate([title_line1, title_line2]):
        fs = 104
        while fs > 48 and draw.textlength(line, font=_mtd(fs)) > 888:
            fs -= 4
        y = 506 + i * 118
        _draw_centered(draw, line, y, _mtd(fs), YELLOW,
                       x0=95, w=888, stroke_w=4, stroke_col=BLACK)

    return _composite(canvas, layer, out_path)


# ── Page 1: Road status ────────────────────────────────────────────────────────

@dataclass
class RoadSection:
    header: str
    items: list[str] = field(default_factory=list)


def render_road_status(bg_path: str, title: str,
                       sections: list[RoadSection],
                       footer_note: str,
                       out_path: str) -> str:
    """Road status: dark photo bg + title + 3 sections with bullet items."""
    img = _load_bg(bg_path, blur=False, alpha=180)
    canvas = img.convert("RGBA")
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    font_title  = _alata(38)
    font_header = _alata(34)
    font_item   = _alata(34)
    STROKE = 1

    _draw_centered(draw, title, 267, font_title, WHITE, stroke_w=STROKE)

    section_ys = [366, 648, 882]
    for sec, sy in zip(sections, section_ys):
        _draw_centered(draw, sec.header, sy, font_header, WHITE, stroke_w=STROKE)
        iy = sy + 47
        for item_text in sec.items:
            _draw_centered(draw, item_text, iy, font_item, WHITE, stroke_w=STROKE)
            iy += 47

    if footer_note:
        _draw_centered(draw, footer_note, 1070, font_item, WHITE, stroke_w=STROKE)

    return _composite(canvas, layer, out_path)


# ── Page 2: Inside Dalat update ───────────────────────────────────────────────

@dataclass
class SeasonalItem:
    name: str
    description: str
    location: str = ""


def render_inside_update(header: str, weather_lines: list[str],
                          signature_text: str,
                          seasonal_items: list[SeasonalItem],
                          out_path: str) -> str:
    """Inside Dalat: cream bg + header + weather + decorative text + seasonal items."""
    canvas = Image.new("RGBA", (W, H), (255, 252, 240, 255))
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    font_header = _mcs(43)
    font_weather = _alata(32)
    font_sig = _mtq(104)
    font_sec = _mcs(32)
    font_body = _alata(24)

    # Header at y=106
    _draw_centered(draw, header, 106, font_header, DARK_OLIVE)

    # Left weather column at x=102
    y = 253
    for line in weather_lines[:4]:
        draw.text((102, y), line, font=font_weather, fill=BLACK)
        y += 44

    # Signature decorative text at y=545 (centered in x=179..971)
    bbox = draw.textbbox((0, 0), signature_text, font=font_sig)
    tw = bbox[2] - bbox[0]
    sx = 179 + (792 - tw) // 2
    draw.text((sx, 545), signature_text, font=font_sig, fill=DARK_RED)

    # Right column seasonal items
    right_x = 370
    item_ys = [660, 893, 1134]
    for i, item in enumerate(seasonal_items[:3]):
        y0 = item_ys[i]
        draw.text((right_x, y0), item.name, font=font_sec, fill=YELLOW)
        draw.text((right_x, y0 + 44), item.description, font=font_body, fill=BLACK)
        if item.location:
            draw.text((right_x, y0 + 44 + 35), f"📍{item.location}", font=font_body, fill=BLACK)

    return _composite(canvas, layer, out_path)


# ── Pages 3-5: Venue grid (3×3) ───────────────────────────────────────────────

GRID_COL_X  = [48, 412, 776]      # photo left-x
GRID_ROW_Y  = [182, 572, 962]     # photo top-y (no overlap with text below)
PHOTO_W     = 274
PHOTO_H     = 295                  # reduced: fits 3 rows + text within 1480px
NAME_ROW_Y  = [492, 882, 1272]    # name text top-y (= row_y + PHOTO_H + 15)
ADDR_ROW_Y  = [524, 914, 1304]    # address text top-y (= name_y + 32)


def _fit_title(draw: ImageDraw.Draw, text: str, max_w: int,
               font_factory, start_size: int):
    """Return font at the largest size where text fits within max_w."""
    size = start_size
    while size > 24:
        font = font_factory(size)
        if draw.textlength(text, font=font) <= max_w:
            return font
        size -= 2
    return font_factory(size)


def render_venue_grid(section_title: str, venues: list[dict],
                      out_path: str) -> str:
    """
    Venue grid (3×3): white bg + title + 9 venue cells (photo + name + address).
    venues: list of up to 9 dicts with keys: name, address, image_path.
    """
    canvas = Image.new("RGBA", (W, H), (255, 255, 255, 255))
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    font_title = _fit_title(draw, section_title, W - 60, _mcs, 62)
    font_name  = _alata(21)
    font_addr  = _alata(19)

    _draw_centered(draw, section_title, 96, font_title, DARK_RED)

    for idx in range(min(9, len(venues))):
        row, col = divmod(idx, 3)
        v = venues[idx]

        # Photo — rounded corners via alpha_composite (preserves transparency)
        thumb = _load_thumb(v.get("image_path", ""), (PHOTO_W, PHOTO_H))
        thumb_r = _rounded_thumb(thumb, radius=16)
        px = GRID_COL_X[col]
        py = GRID_ROW_Y[row]
        canvas.alpha_composite(thumb_r.convert("RGBA"), dest=(px, py))

        # Name and address — centered within photo column width
        cell_cx = GRID_COL_X[col] + PHOTO_W // 2
        col_max_w = PHOTO_W - 4  # stay within photo column

        name = v.get("name", "")
        # Truncate only if too wide at current font size
        while len(name) > 4 and draw.textlength(name, font=font_name) > col_max_w:
            name = name[:-2] + "…"
        bbox = draw.textbbox((0, 0), name, font=font_name)
        draw.text((cell_cx - (bbox[2] - bbox[0]) // 2, NAME_ROW_Y[row]),
                  name, font=font_name, fill=DARK_OLIVE)

        addr = v.get("address", "").split(",")[0].strip()
        while len(addr) > 4 and draw.textlength(addr, font=font_addr) > col_max_w:
            addr = addr[:-2] + "…"
        bbox = draw.textbbox((0, 0), addr, font=font_addr)
        draw.text((cell_cx - (bbox[2] - bbox[0]) // 2, ADDR_ROW_Y[row]),
                  addr, font=font_addr, fill=DARK_OLIVE)

    return _composite(canvas, layer, out_path)
