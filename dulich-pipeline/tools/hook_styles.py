"""
hook_styles.py — Four reference hook templates rendered as transparent 1080x1920 PNG overlays.

Styles:
  A sticker_tilt — arched uppercase yellow + thick black outline + 3D shadow, cat & thumbs-up stickers.
  B marker_highlight — dark text on hand-drawn yellow brush highlight + bow/flower emoji stickers.
  C starburst — white+black text on a red spiky explosion star.
  D quote_card — white quote text, big quotation mark, corner-bracket frame (minimal).

Fonts (assets/fonts): Montserrat (heavy display), Baloo 2 (rounded), Be Vietnam Pro — all full Vietnamese.
Stickers (assets/stickers): Noto emoji PNGs. Drop a real cutout as cat.png to override the meme cat.
"""

from __future__ import annotations

import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
FONT_DIR = ROOT / "assets" / "fonts"
STK_DIR = ROOT / "assets" / "stickers"
MONT = FONT_DIR / "Montserrat-VF.ttf"
BALOO = FONT_DIR / "Baloo2-VF.ttf"
BEVN = FONT_DIR / "BeVietnamPro-Bold-full.ttf"

W, H = 1080, 1920


def _blank() -> Image.Image:
    return Image.new("RGBA", (W, H), (0, 0, 0, 0))


def _load(path: Path, size: int, weight: int | None = None) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(str(path), size)
    if weight is not None:
        try:
            f.set_variation_by_axes([weight])
        except Exception:
            pass
    return f


def _fit_font(path, lines, maxw, start=160, weight=None, stroke_w=0, mins=40):
    d = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    for sz in range(start, mins, -3):
        f = _load(path, sz, weight)
        w = max(d.textbbox((0, 0), ln, font=f, stroke_width=stroke_w)[2] for ln in lines)
        if w <= maxw:
            return f
    return _load(path, mins, weight)


# ── Stickers ──────────────────────────────────────────────────────────────────

def _sticker(name: str, size: int, angle: float = 0) -> Image.Image | None:
    """Load a sticker by friendly name or raw filename; scale to `size` (long edge)."""
    alias = {
        "cat": "cat.png", "thumbsup": "emoji_1f44d.png", "bow": "emoji_1f380.png",
        "flower": "emoji_1f33c.png", "blossom": "emoji_1f338.png",
        "catemoji": "emoji_1f431.png", "sparkle": "emoji_2728.png", "money": "emoji_1f4b8.png",
    }
    fn = alias.get(name, name)
    p = STK_DIR / fn
    if not p.exists():
        if name == "cat":                       # fall back to emoji cat until a cutout is provided
            p = STK_DIR / "emoji_1f431.png"
        if not p.exists():
            return None
    img = Image.open(p).convert("RGBA")
    s = size / max(img.size)
    img = img.resize((int(img.width * s), int(img.height * s)), Image.LANCZOS)
    if angle:
        img = img.rotate(angle, expand=True, resample=Image.BICUBIC)
    return img


def _paste(canvas, img, cx, cy):
    if img is None:
        return
    canvas.alpha_composite(img, (int(cx - img.width / 2), int(cy - img.height / 2)))


# ── Text layers ───────────────────────────────────────────────────────────────

def _text_layer(lines, font, fill, stroke_w=0, stroke_fill=None, gap=8,
                shadow_fill=None, shadow_off=(0, 0)) -> Image.Image:
    big = Image.new("RGBA", (2200, 1500), (0, 0, 0, 0))
    d = ImageDraw.Draw(big)
    sizes = [d.textbbox((0, 0), ln, font=font, stroke_width=stroke_w) for ln in lines]
    lws = [s[2] - s[0] for s in sizes]
    lhs = [s[3] - s[1] for s in sizes]
    maxw = max(lws)
    ox, oy = 250, 220
    if shadow_fill:
        yy = oy
        for ln, s, lw, lh in zip(lines, sizes, lws, lhs):
            x = ox + (maxw - lw) // 2 - s[0]
            d.text((x + shadow_off[0], yy - s[1] + shadow_off[1]), ln, font=font,
                   fill=shadow_fill, stroke_width=stroke_w, stroke_fill=shadow_fill)
            yy += lh + gap
    yy = oy
    for ln, s, lw, lh in zip(lines, sizes, lws, lhs):
        x = ox + (maxw - lw) // 2 - s[0]
        d.text((x, yy - s[1]), ln, font=font, fill=fill,
               stroke_width=stroke_w, stroke_fill=stroke_fill)
        yy += lh + gap
    return big.crop(big.getbbox())


def _arc_line(text, font, fill, stroke_w, stroke_fill, curve,
              shadow_fill=None, shadow_off=(0, 0)) -> Image.Image:
    """Render one line with a parabolic (dome) warp + per-glyph tangent rotation."""
    d0 = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    chars = list(text)
    advs = [d0.textlength(c, font=font) for c in chars]
    total = sum(advs) or 1
    half = total / 2
    pad = stroke_w + max(abs(shadow_off[0]), abs(shadow_off[1])) + 8

    cw = int(total) + 300
    chh = int(font.size * 1.8 + abs(curve) * 2 + 300)
    layer = Image.new("RGBA", (cw, chh), (0, 0, 0, 0))
    midy = chh // 2
    x = 150
    for ch, adv in zip(chars, advs):
        bb = font.getbbox(ch, stroke_width=stroke_w)
        w, h = bb[2] - bb[0], bb[3] - bb[1]
        tile = Image.new("RGBA", (int(w) + pad * 2, int(h) + pad * 2), (0, 0, 0, 0))
        dd = ImageDraw.Draw(tile)
        if shadow_fill:
            dd.text((pad - bb[0] + shadow_off[0], pad - bb[1] + shadow_off[1]), ch,
                    font=font, fill=shadow_fill, stroke_width=stroke_w, stroke_fill=shadow_fill)
        dd.text((pad - bb[0], pad - bb[1]), ch, font=font, fill=fill,
                stroke_width=stroke_w, stroke_fill=stroke_fill)
        cx = x + adv / 2
        t = (cx - (150 + half)) / half               # -1 .. 1
        yoff = curve * (t * t)                        # center high, ends low (dome)
        rot = -math.degrees(math.atan(2 * curve * t / half))
        rt = tile.rotate(rot, expand=True, resample=Image.BICUBIC)
        layer.alpha_composite(rt, (int(cx - rt.width / 2), int(midy + yoff - rt.height / 2)))
        x += adv
    return layer.crop(layer.getbbox())


# ── Decorations ───────────────────────────────────────────────────────────────

def _starburst(canvas, cx, cy, R, fill, outline, points=15, inner=0.72, seed=7):
    rnd = random.Random(seed)
    pts = []
    for i in range(points * 2):
        ang = math.pi / points * i - math.pi / 2
        rad = R if i % 2 == 0 else R * inner
        rad *= 1 + rnd.uniform(-0.05, 0.05)
        pts.append((cx + rad * math.cos(ang), cy + rad * math.sin(ang)))
    d = ImageDraw.Draw(canvas)
    d.polygon(pts, fill=outline)
    pts2 = [(cx + (x - cx) * 0.9, cy + (y - cy) * 0.9) for x, y in pts]
    d.polygon(pts2, fill=fill)


def _brush(canvas, cx, cy, w, h, color, angle=-2.0, seed=3):
    rnd = random.Random(seed)
    pad = 90
    layer = Image.new("RGBA", (w + pad * 2, h + pad), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    x0, y0, x1, y1 = pad, pad // 2, pad + w, pad // 2 + h
    d.rounded_rectangle([x0, y0, x1, y1], radius=h // 2, fill=color)
    for end_x, sign in ((x0, -1), (x1, 1)):
        for _ in range(7):
            yy = rnd.uniform(y0, y1)
            ln = rnd.uniform(h * 0.25, h * 0.7)
            d.line([(end_x, yy), (end_x + sign * ln, yy)], fill=color, width=int(h * 0.16))
    layer = layer.rotate(angle, expand=True, resample=Image.BICUBIC)
    canvas.alpha_composite(layer, (cx - layer.width // 2, cy - layer.height // 2))


def _caption(canvas, text, font, top_frac=0.70):
    import textwrap
    d = ImageDraw.Draw(canvas)
    y = int(H * top_frac)
    for ln in textwrap.wrap(text, width=22):
        bb = d.textbbox((0, 0), ln, font=font, stroke_width=6)
        x = (W - (bb[2] - bb[0])) // 2 - bb[0]
        d.text((x, y - bb[1]), ln, font=font, fill=(255, 255, 255, 255),
               stroke_width=6, stroke_fill=(0, 0, 0, 210))
        y += (bb[3] - bb[1]) + 16


# ── Styles ────────────────────────────────────────────────────────────────────

def style_sticker_tilt(lines=("NGƯỜI MỚI ĐI ĐÀ LẠT VỀ", "KHUYÊN NGƯỜI SẮP ĐI")) -> Image.Image:
    canvas = _blank()
    up = [l.upper() for l in lines]
    font = _fit_font(MONT, up, maxw=900, start=96, weight=900, stroke_w=16)

    # arched lines stacked
    line_imgs = [_arc_line(ln, font, fill=(255, 209, 0, 255), stroke_w=16,
                           stroke_fill=(0, 0, 0, 255), curve=42,
                           shadow_fill=(0, 0, 0, 140), shadow_off=(0, 12)) for ln in up]
    block_h = sum(im.height for im in line_imgs) + 6 * (len(line_imgs) - 1)
    block = Image.new("RGBA", (max(im.width for im in line_imgs), block_h), (0, 0, 0, 0))
    yy = 0
    for im in line_imgs:
        block.alpha_composite(im, ((block.width - im.width) // 2, yy))
        yy += im.height + 6
    block = block.rotate(4, expand=True, resample=Image.BICUBIC)

    text_cy = int(H * 0.27)
    canvas.alpha_composite(block, ((W - block.width) // 2, int(text_cy - block.height / 2)))

    # cat + thumbs-up sticker above the text
    cat = _sticker("cat", 300, angle=0)
    _paste(canvas, cat, W // 2 + 20, int(H * 0.135))
    thumb = _sticker("thumbsup", 150)
    _paste(canvas, thumb, W // 2 - 90, int(H * 0.155))
    return canvas


def style_marker_highlight(lines=("Cập nhật tình hình", "Đà lạt tháng 5")) -> Image.Image:
    canvas = _blank()
    font = _fit_font(BALOO, lines, maxw=760, start=110, weight=700)
    d0 = ImageDraw.Draw(canvas)
    yc = int(H * 0.17)
    rendered = []
    for ln in lines:
        bb = d0.textbbox((0, 0), ln, font=font)
        rendered.append((ln, bb, bb[2] - bb[0], bb[3] - bb[1]))
    line_h = max(r[3] for r in rendered)
    gap = int(line_h * 0.5)
    for i, (ln, bb, lw, lh) in enumerate(rendered):
        cy = yc + i * (line_h + gap)
        _brush(canvas, W // 2, cy, lw + 60, int(line_h * 1.25),
               color=(255, 214, 64, 235), angle=-2.5 + i, seed=3 + i)
    yy = yc - line_h // 2
    d = ImageDraw.Draw(canvas)
    for ln, bb, lw, lh in rendered:
        x = (W - lw) // 2 - bb[0]
        d.text((x, yy - bb[1]), ln, font=font, fill=(54, 42, 30, 255))
        yy += line_h + gap
    # emoji stickers: bow top-left, flower right
    _paste(canvas, _sticker("bow", 110, angle=10), int(W * 0.15), int(H * 0.145))
    _paste(canvas, _sticker("flower", 95), int(W * 0.87), int(H * 0.205))
    return canvas


def style_starburst(lines=("Những sai lầm", "mà ai cũng từng", "gặp phải")) -> Image.Image:
    canvas = _blank()
    font = _fit_font(BALOO, lines, maxw=620, start=92, weight=700, stroke_w=8)
    layer = _text_layer(lines, font, fill=(255, 255, 255, 255), stroke_w=8,
                        stroke_fill=(0, 0, 0, 255), gap=2)
    cx, cy = W // 2, int(H * 0.55)
    R = max(layer.width, layer.height) // 2 + 150
    _starburst(canvas, cx, cy, R, fill=(232, 34, 42, 255), outline=(150, 16, 22, 255))
    _paste(canvas, layer, cx, cy)
    return canvas


def style_quote_card(lines=("Có nên đi Đà Lạt cuối tháng 5", "đầu tháng 6 không"),
                     caption="Có nên đi Đà Lạt cuối tháng 5 đầu tháng 6 không") -> Image.Image:
    canvas = _blank()
    d = ImageDraw.Draw(canvas)
    cx, cy = W // 2, int(H * 0.34)
    qfont = _load(BALOO, 200, weight=700)
    qb = d.textbbox((0, 0), "“", font=qfont)
    d.text((cx - (qb[2] - qb[0]) // 2 - qb[0], int(H * 0.20) - qb[1]), "“",
           font=qfont, fill=(255, 255, 255, 255))
    font = _fit_font(BEVN, lines, maxw=720, start=58)
    layer = _text_layer(lines, font, fill=(255, 255, 255, 240), gap=14,
                        shadow_fill=(0, 0, 0, 90), shadow_off=(2, 3))
    _paste(canvas, layer, cx, cy)
    half_w = layer.width // 2 + 90
    half_h = layer.height // 2 + 150
    L, wdt, col = 95, 7, (255, 255, 255, 235)
    tr = (cx + half_w, cy - half_h)
    d.line([(tr[0] - L, tr[1]), tr], fill=col, width=wdt)
    d.line([tr, (tr[0], tr[1] + L)], fill=col, width=wdt)
    bl = (cx - half_w, cy + half_h)
    d.line([(bl[0], bl[1] - L), bl], fill=col, width=wdt)
    d.line([bl, (bl[0] + L, bl[1])], fill=col, width=wdt)
    if caption:
        _caption(canvas, caption, _load(BEVN, 58), top_frac=0.72)
    return canvas


STYLES = {
    "A": ("sticker_tilt", style_sticker_tilt),
    "B": ("marker_highlight", style_marker_highlight),
    "C": ("starburst", style_starburst),
    "D": ("quote_card", style_quote_card),
}


def build(style: str, out_path: str) -> str:
    _, fn = STYLES[style.upper()]
    img = fn()
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return str(out)


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Render hook style overlay (A/B/C/D)")
    ap.add_argument("style", choices=list(STYLES) + [s.lower() for s in STYLES])
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    name = STYLES[args.style.upper()][0]
    out = args.out or f"output/hook_{name}.png"
    print("Saved:", build(args.style, out))
