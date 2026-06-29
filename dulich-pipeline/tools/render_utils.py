"""
render_utils.py — Shared rendering helpers cho tất cả template renderers.

Import pattern:
    from tools.render_utils import (
        load_bg, load_thumb, rounded_thumb, placeholder_thumb,
        pill, draw_pin_icon, draw_text_in_box, load_font,
        anton, noto, beviet_bold, dancing,
        apply_bottom_gradient, draw_venue_card_bottom,
        draw_venue_text_row, save_slide,
    )
"""

from __future__ import annotations

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter

ASSETS_FONTS = Path(__file__).parent.parent / "assets" / "fonts"


# ── Font loading ──────────────────────────────────────────────────────────────

def load_font(name: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    local = ASSETS_FONTS / name
    if local.exists():
        try:
            return ImageFont.truetype(str(local), size)
        except Exception:
            pass
    win = Path("C:/Windows/Fonts")
    stem = Path(name).stem.lower()
    for f in win.glob("*.ttf"):
        if stem in f.name.lower():
            try:
                return ImageFont.truetype(str(f), size)
            except Exception:
                pass
    return ImageFont.load_default()


def anton(size: int):
    return load_font("Anton-Regular.ttf", size)


def noto(size: int):
    for name in ("NotoSans-VF.ttf", "NotoSans-Regular.ttf"):
        local = ASSETS_FONTS / name
        if local.exists():
            try:
                return ImageFont.truetype(str(local), size)
            except Exception:
                pass
    return load_font("NotoSans-Regular.ttf", size)


def beviet_bold(size: int):
    return load_font("BeVietnamPro-Bold-full.ttf", size)


def dancing(size: int):
    return load_font("DancingScript-VF.ttf", size)


def alata(size: int):
    return load_font("Alata-Regular.ttf", size)


def mtd_summer_show(size: int):
    return load_font("MTDSummerShow.otf", size)


def mtd_cheese_sauce(size: int):
    return load_font("MTDSummerShow-Badge.otf", size)


def mtd_quaver(size: int):
    return load_font("MTDSummerShow2.otf", size)


# ── Background & thumbnail loading ────────────────────────────────────────────

def load_bg(path: str, canvas_w: int = 1080, canvas_h: int = 1280,
            blur: bool = False, overlay_alpha: int = 0) -> Image.Image:
    """Load + center-crop + resize image to (canvas_w, canvas_h)."""
    if path and os.path.exists(path):
        img = Image.open(path).convert("RGB")
    else:
        img = Image.new("RGB", (canvas_w, canvas_h), (50, 50, 50))

    iw, ih = img.size
    target_ratio = canvas_w / canvas_h
    if iw / ih > target_ratio:
        new_w = int(ih * target_ratio)
        img = img.crop(((iw - new_w) // 2, 0, (iw + new_w) // 2, ih))
    else:
        new_h = int(iw / target_ratio)
        img = img.crop((0, (ih - new_h) // 2, iw, (ih + new_h) // 2))
    img = img.resize((canvas_w, canvas_h), Image.Resampling.LANCZOS)

    if blur:
        img = img.filter(ImageFilter.GaussianBlur(radius=8))
    if overlay_alpha > 0:
        ov = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, overlay_alpha))
        img = img.convert("RGBA")
        img.alpha_composite(ov)
        img = img.convert("RGB")
    return img


def placeholder_thumb(size: tuple) -> Image.Image:
    img = Image.new("RGB", size, (210, 210, 210))
    d = ImageDraw.Draw(img)
    cx, cy = size[0] // 2, size[1] // 2
    r = min(size) // 5
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(160, 160, 160), width=2)
    return img


def load_thumb(path: str, size: tuple) -> Image.Image:
    """Center-crop + resize to `size`."""
    if path and os.path.exists(path):
        img = Image.open(path).convert("RGB")
        iw, ih = img.size
        target_ratio = size[0] / size[1]
        if iw / ih > target_ratio:
            new_w = int(ih * target_ratio)
            img = img.crop(((iw - new_w) // 2, 0, (iw + new_w) // 2, ih))
        else:
            new_h = int(iw / target_ratio)
            img = img.crop((0, (ih - new_h) // 2, iw, (ih + new_h) // 2))
        return img.resize(size, Image.Resampling.LANCZOS)
    return placeholder_thumb(size)


def rounded_thumb(thumb: Image.Image, radius: int = 10) -> Image.Image:
    mask = Image.new("L", thumb.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, thumb.size[0], thumb.size[1]],
                                           radius=radius, fill=255)
    out = thumb.convert("RGBA")
    out.putalpha(mask)
    return out


# ── Drawing primitives ────────────────────────────────────────────────────────

def pill(draw: ImageDraw.Draw, x: int, y: int, w: int, h: int,
         text: str, bg: tuple, fg: tuple, font,
         radius: int = 15) -> None:
    draw.rounded_rectangle([(x, y), (x + w, y + h)], radius=radius, fill=bg)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    tx = x + (w - tw) // 2 - bbox[0]
    ty = y + (h - th) // 2 - bbox[1]
    draw.text((tx, ty), text, font=font, fill=fg)


def draw_pin_icon(draw: ImageDraw.Draw, x: int, y: int, size: int = 14,
                  color: tuple = (232, 60, 74)) -> None:
    r = size // 2
    cx = x + r
    draw.ellipse([x, y, x + size, y + size], fill=color)
    dot_r = max(2, r // 3)
    draw.ellipse([cx - dot_r, y + r - dot_r, cx + dot_r, y + r + dot_r],
                 fill=(255, 255, 255))
    tail_h = size // 2
    draw.polygon([
        (cx - r // 2, y + size - 3),
        (cx + r // 2, y + size - 3),
        (cx, y + size + tail_h),
    ], fill=color)


def draw_text_in_box(draw: ImageDraw.Draw, text: str, x: int, y: int,
                     max_w: int, font, color: tuple) -> int:
    """Word-wrap with explicit \\n. Returns bottom y."""
    segments = text.split("\n")
    lines = []
    for seg in segments:
        words = seg.split()
        cur = ""
        for word in words:
            test = (cur + " " + word).strip()
            if int(draw.textlength(test, font=font)) <= max_w:
                cur = test
            else:
                if cur:
                    lines.append(cur)
                cur = word
        lines.append(cur)
    line_h = font.size + 4
    for line in lines:
        draw.text((x, y), line, font=font, fill=color)
        y += line_h
    return y


# ── New shared helpers ────────────────────────────────────────────────────────

def apply_bottom_gradient(img: Image.Image, start_y_frac: float = 0.55,
                          max_alpha: int = 200) -> Image.Image:
    """Alpha-composite a vertical gradient (transparent→black) over img.

    start_y_frac: fraction of height where gradient starts (0.0 = top, 1.0 = bottom).
    max_alpha: opacity at the very bottom edge.
    Returns a new RGBA image.
    """
    w, h = img.size
    gradient = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    pix = gradient.load()
    start_y = int(h * start_y_frac)
    fade_h = h - start_y
    for y in range(start_y, h):
        alpha = int(max_alpha * (y - start_y) / max(fade_h, 1))
        for x in range(w):
            pix[x, y] = (0, 0, 0, alpha)
    base = img.convert("RGBA")
    base.alpha_composite(gradient)
    return base


def draw_venue_card_bottom(draw: ImageDraw.Draw, x: int, y: int, w: int, h: int,
                           venue: dict, fonts: dict) -> None:
    """Draw venue info block (name + badge + address + signature) in a region.

    fonts dict keys: name_font, badge_font, addr_font, sig_font.
    """
    name_font  = fonts.get("name_font",  noto(20))
    badge_font = fonts.get("badge_font", noto(15))
    addr_font  = fonts.get("addr_font",  noto(16))
    sig_font   = fonts.get("sig_font",   noto(16))

    pad = 20
    cy = y + 20

    # Venue name (bold white)
    name = venue.get("name", "")
    draw_text_in_box(draw, name, x + pad, cy, w - pad * 2 - 100, name_font, (255, 255, 255))
    cy += name_font.size + 8

    # Address with pin icon (red)
    addr = venue.get("address", "")
    if len(addr) > 45:
        addr = addr.split(",")[0]
    draw_pin_icon(draw, x + pad, cy + 2, size=13, color=(232, 60, 74))
    draw.text((x + pad + 18, cy), addr, font=addr_font, fill=(200, 200, 200))
    cy += addr_font.size + 8

    # Signature (yellow)
    sig = venue.get("signature", "")
    if sig:
        draw_text_in_box(draw, sig, x + pad, cy, w - pad * 2, sig_font, (245, 208, 32))
        cy += sig_font.size + 6

    # Category badge (top-right of region)
    cat = venue.get("loai_quan", "")
    if cat:
        bw = int(draw.textlength(cat, font=badge_font)) + 20
        bh = badge_font.size + 10
        bx = x + w - bw - 16
        by = y + 16
        draw.rounded_rectangle([(bx, by), (bx + bw, by + bh)], radius=8,
                                fill=(43, 71, 33, 200))
        draw.text((bx + 10, by + 5), cat, font=badge_font, fill=(255, 255, 255))


def draw_venue_text_row(draw: ImageDraw.Draw, x: int, y: int, max_w: int,
                        venue: dict, fonts: dict) -> int:
    """Draw a 3-line venue text row (name / signature / address+pin).
    Returns the new y below the row.
    """
    name_font = fonts.get("name_font",  beviet_bold(22))
    sig_font  = fonts.get("sig_font",   noto(17))
    addr_font = fonts.get("addr_font",  noto(15))

    name = venue.get("name", "")
    sig  = venue.get("signature", "")
    addr = venue.get("address", "")
    if len(addr) > 50:
        addr = addr.split(",")[0]

    draw.text((x, y), name, font=name_font, fill=(255, 255, 255))
    y += name_font.size + 4

    if sig:
        draw.text((x, y), sig, font=sig_font, fill=(200, 230, 200))
        y += sig_font.size + 3

    draw_pin_icon(draw, x, y + 2, size=12, color=(200, 80, 80))
    draw.text((x + 18, y), addr, font=addr_font, fill=(180, 200, 180))
    y += addr_font.size + 12

    return y


def save_slide(canvas: Image.Image, layer: Image.Image, out_path: str) -> str:
    """Alpha-composite layer onto canvas, convert to RGB, save to out_path."""
    canvas.alpha_composite(layer)
    out = canvas.convert("RGB")
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    out.save(out_path, "PNG")
    return out_path
