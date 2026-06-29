"""
mye26_renderer.py — Album renderer cho format lịch trình du lịch kiểu Mye26.
Canvas: 1080 × 1280px (Canva measurements).
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from PIL import Image, ImageDraw, ImageFont, ImageFilter
from tools.render_utils import (
    load_font as _load_font,
    anton as _anton, noto as _noto, beviet_bold as _beviet_bold,
    load_bg as _load_bg_util,
    pill as _pill, draw_pin_icon as _draw_pin_icon,
    placeholder_thumb as _placeholder_thumb, load_thumb as _load_thumb,
    rounded_thumb as _rounded_thumb, draw_text_in_box as _draw_text_in_box,
    save_slide as _save_slide,
)

W, H = 1080, 1280

ASSETS_FONTS = Path(__file__).parent.parent / "assets" / "fonts"


def _load_bg(path: str, blur: bool = False, overlay_alpha: int = 0) -> Image.Image:
    return _load_bg_util(path, W, H, blur, overlay_alpha)


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class CoverData:
    background_path: str
    month_tag: str = "Tháng 6"
    handle_tag: str = "@dalat"
    location_tag: str = "Đà Lạt"
    title: str = ""
    subtitle: str = ""


@dataclass
class ActivityItem:
    time: str
    activity: str
    venue: str
    address: str
    thumbnail_path: str = ""


@dataclass
class ItinerarySlide:
    background_path: str
    day_number: int
    activities: list


@dataclass
class VenueItem:
    name: str
    address: str
    category: str
    signature: str = ""
    thumbnail_path: str = ""


@dataclass
class ReferenceListSlide:
    background_path: str
    title: str
    venues: list


# ── Slide renderers ───────────────────────────────────────────────────────────

def render_cover(data: CoverData, out_path: str) -> str:
    """
    Cover slide:
    - Pills (month / handle / location) auto-sized, centered horizontally as group
    - Green card: X=272, Y=213, W=536, H=251, fill=#2b4721, stroke white, radius=35
    - Title: Anton 45px, white, word-wrap + centered in card
    - Subtitle: NotoSans 27px, yellow, immediately below title
    """
    img = _load_bg(data.background_path, blur=False, overlay_alpha=0)
    canvas = img.convert("RGBA")
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    font_pill     = _noto(18)
    font_title    = _anton(45)
    font_subtitle = _noto(27)

    # Pills: auto-size each pill to content, then center the group
    PAD_X = 20
    GAP   = 8
    PILL_H = 30

    month_tw  = int(draw.textlength(data.month_tag, font=font_pill))
    handle_tw = int(draw.textlength(data.handle_tag, font=font_pill))
    loc_tw    = int(draw.textlength(data.location_tag, font=font_pill))

    month_w  = month_tw  + PAD_X * 2
    handle_w = handle_tw + PAD_X * 2
    loc_w    = loc_tw    + PAD_X * 2

    total_pill_w = month_w + handle_w + loc_w + GAP * 2
    pill_x0 = (W - total_pill_w) // 2
    pill_y  = 174

    _pill(draw, x=pill_x0,                                  y=pill_y, w=month_w,  h=PILL_H,
          text=data.month_tag,    bg=(245, 208, 32), fg=(43, 71, 33),    font=font_pill)
    _pill(draw, x=pill_x0 + month_w + GAP,                  y=pill_y, w=handle_w, h=PILL_H,
          text=data.handle_tag,   bg=(217, 119, 6),  fg=(255, 255, 255), font=font_pill)
    _pill(draw, x=pill_x0 + month_w + GAP + handle_w + GAP, y=pill_y, w=loc_w,   h=PILL_H,
          text=data.location_tag, bg=(111, 13, 13),  fg=(255, 255, 255), font=font_pill)

    # Green card — from Canva measurements
    card_x, card_y = 272, 213
    card_w, card_h = 536, 251
    card_cx = card_x + card_w // 2
    draw.rounded_rectangle(
        [(card_x, card_y), (card_x + card_w, card_y + card_h)],
        radius=35,
        fill=(43, 71, 33, 235),
        outline=(255, 255, 255),
        width=2,
    )

    # Title: word-wrap then CENTER each line in the card
    title_max = card_w - 60
    segs = data.title.split("\n")
    lines = []
    for seg in segs:
        words = seg.split()
        cur = ""
        for word in words:
            test = (cur + " " + word).strip()
            if int(draw.textlength(test, font=font_title)) <= title_max:
                cur = test
            else:
                if cur:
                    lines.append(cur)
                cur = word
        lines.append(cur)

    y = card_y + 32
    for line in lines:
        if line:
            tw = int(draw.textlength(line, font=font_title))
            draw.text((card_cx - tw // 2, y), line, font=font_title, fill=(255, 255, 255))
        y += font_title.size + 6

    # Subtitle: 10px below last title line, centered
    sub_tw = int(draw.textlength(data.subtitle, font=font_subtitle))
    draw.text((card_cx - sub_tw // 2, y + 10), data.subtitle,
              font=font_subtitle, fill=(245, 208, 32))

    canvas.alpha_composite(layer)
    out = canvas.convert("RGB")
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    out.save(out_path, "PNG")
    print(f"[mye26] Cover -> {out_path}")
    return out_path


def render_itinerary(data: ItinerarySlide, out_path: str) -> str:
    """
    Itinerary slide:
    - White card: X=151, Y=73, W=795, H=1167, radius=40, subtle drop shadow
    - Day title: Anton 50px centered
    - Up to 8 activity rows, dynamic height
    - Each row: thumbnail (left) + 3-line text (time·activity / venue bold / pin+address)
    """
    img = _load_bg(data.background_path, blur=False, overlay_alpha=60)
    canvas = img.convert("RGBA")
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    card_x, card_y = 151, 73
    card_w, card_h = 795, 1167

    # Subtle drop shadow
    sh = 8
    draw.rounded_rectangle(
        [(card_x + sh, card_y + sh), (card_x + card_w + sh, card_y + card_h + sh)],
        radius=40, fill=(0, 0, 0, 35),
    )
    # White card
    draw.rounded_rectangle(
        [(card_x, card_y), (card_x + card_w, card_y + card_h)],
        radius=40, fill=(255, 255, 255, 245),
    )

    font_day   = _anton(50)
    font_time  = _noto(17)
    font_venue = _beviet_bold(20)
    font_addr  = _noto(16)

    # Day title centered
    day_text = f"NGÀY {data.day_number}"
    day_tw   = int(draw.textlength(day_text, font=font_day))
    draw.text((card_x + (card_w - day_tw) // 2, card_y + 22), day_text,
              font=font_day, fill=(61, 43, 31))

    # Row layout — dynamic
    activities  = data.activities[:8]
    n           = len(activities)
    row_start_y = card_y + 22 + font_day.size + 18
    available_h = (card_y + card_h) - row_start_y - 16
    row_h       = available_h // max(n, 1)
    thumb_size  = min(108, row_h - 20)

    thumb_x = card_x + 22
    text_x  = thumb_x + thumb_size + 14

    # Pre-calc text block height for vertical centering
    TEXT_H = font_time.size + 4 + font_venue.size + 5 + font_addr.size

    for i, item in enumerate(activities):
        row_y = row_start_y + i * row_h

        # Thumbnail — vertically centered in row
        thumb = _load_thumb(item.thumbnail_path, (thumb_size, thumb_size))
        thumb_r = _rounded_thumb(thumb, radius=10)
        ty = row_y + (row_h - thumb_size) // 2
        layer.paste(thumb_r, (thumb_x, ty), thumb_r)

        # Text block — vertically centered against thumbnail
        text_top = ty + (thumb_size - TEXT_H) // 2

        # Line 1: time + activity type (small, muted brown)
        if item.time:
            t_line = item.time + (f"  ·  {item.activity}" if item.activity else "")
            draw.text((text_x, text_top), t_line, font=font_time, fill=(120, 95, 70))
        text_top += font_time.size + 4

        # Line 2: venue name (bold, dark)
        draw.text((text_x, text_top), item.venue, font=font_venue, fill=(35, 25, 15))
        text_top += font_venue.size + 5

        # Line 3: pin icon + address (red)
        _draw_pin_icon(draw, text_x, text_top + 1, size=13, color=(232, 60, 74))
        draw.text((text_x + 18, text_top), item.address, font=font_addr, fill=(220, 50, 65))

        # Divider (except last row)
        if i < n - 1:
            div_y = row_y + row_h - 1
            draw.line([(card_x + 20, div_y), (card_x + card_w - 20, div_y)],
                      fill=(220, 215, 210, 180), width=1)

    canvas.alpha_composite(layer)
    out = canvas.convert("RGB")
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    out.save(out_path, "PNG")
    print(f"[mye26] Day {data.day_number} -> {out_path}")
    return out_path


def render_reference_list(data: ReferenceListSlide, out_path: str) -> str:
    img = _load_bg(data.background_path, blur=True, overlay_alpha=120)
    canvas = img.convert("RGBA")
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    font_title  = _anton(46)
    font_name   = _beviet_bold(22)
    font_detail = _noto(17)
    font_badge  = _noto(15)

    tw = int(draw.textlength(data.title, font=font_title))
    draw.text(((W - tw) // 2, 60), data.title, font=font_title, fill=(255, 255, 255))

    line_y = 60 + font_title.size + 16
    draw.line([(60, line_y), (W - 60, line_y)], fill=(255, 255, 255, 60), width=2)

    n = len(data.venues)
    available_h = H - line_y - 30
    row_h = min(155, available_h // max(n, 1))
    thumb_w, thumb_h = 110, 80
    pad_left = 40
    current_y = line_y + 16

    for venue in data.venues:
        cy = current_y + (row_h - thumb_h) // 2
        thumb = _load_thumb(venue.thumbnail_path if hasattr(venue, "thumbnail_path") else "",
                            (thumb_w, thumb_h))
        thumb_r = _rounded_thumb(thumb, radius=8)
        layer.paste(thumb_r, (pad_left, cy), thumb_r)

        tx = pad_left + thumb_w + 16
        text_y = current_y + (row_h - font_name.size - font_detail.size - 10) // 2
        draw.text((tx, text_y), venue.name, font=font_name, fill=(255, 255, 255))
        text_y += font_name.size + 6

        _draw_pin_icon(draw, tx, text_y + 2, size=13, color=(232, 60, 74))
        draw.text((tx + 18, text_y), venue.address, font=font_detail, fill=(200, 205, 210))

        if venue.signature:
            text_y += font_detail.size + 4
            draw.text((tx, text_y), venue.signature, font=font_detail, fill=(245, 208, 32))

        badge_text = venue.category
        bw = int(draw.textlength(badge_text, font=font_badge)) + 20
        bh = font_badge.size + 10
        bx = W - pad_left - bw
        by = current_y + (row_h - bh) // 2
        draw.rounded_rectangle([(bx, by), (bx + bw, by + bh)], radius=6,
                                fill=(43, 71, 33, 200))
        draw.text((bx + 10, by + 5), badge_text, font=font_badge, fill=(255, 255, 255))

        draw.line([(pad_left, current_y + row_h - 1), (W - pad_left, current_y + row_h - 1)],
                  fill=(255, 255, 255, 35), width=1)
        current_y += row_h

    canvas.alpha_composite(layer)
    out = canvas.convert("RGB")
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    out.save(out_path, "PNG")
    print(f"[mye26] Ref list -> {out_path}")
    return out_path


def render_album(cover: CoverData, slides: list, output_dir: str, album_name: str = "album") -> list:
    out_dir = Path(output_dir)
    paths = []
    paths.append(render_cover(cover, str(out_dir / f"{album_name}_00_cover.png")))
    for i, slide in enumerate(slides, 1):
        if isinstance(slide, ItinerarySlide):
            fname = str(out_dir / f"{album_name}_{i:02d}_day.png")
            paths.append(render_itinerary(slide, fname))
        elif isinstance(slide, ReferenceListSlide):
            fname = str(out_dir / f"{album_name}_{i:02d}_ref.png")
            paths.append(render_reference_list(slide, fname))
    return paths
