"""
hook_overlay.py — Render the "Đà Lạt review" hook as a transparent PNG overlay (1080x1920).

Reproduces the reference style with three text layers:
  1. Title  — bouncy yellow bubble (Baloo 2), per-letter rotation + hand-drawn sparkle doodles.
  2. Script — white handwriting (Caveat), centered, soft shadow.
  3. Caption — white rounded sans (Be Vietnam Pro) with outline (the spoken subtitle line).

The PNG is meant to be composited over vertical video via FFmpeg overlay.
"""

from __future__ import annotations

import math
import unicodedata
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
TITLE_FONT = FONT_DIR / "Baloo2-VF.ttf"           # variable, use wght=800
SCRIPT_FONT = FONT_DIR / "DancingScript-VF.ttf"   # variable, use wght=700
CAPTION_FONT = FONT_DIR / "BeVietnamPro-Bold-full.ttf"

W, H = 1080, 1920

# Palette tuned to the reference frame
YELLOW = (251, 201, 53, 255)        # warm golden title
CREAM = (255, 248, 231, 255)        # thin outline around title
WHITE = (255, 255, 255, 255)
SHADOW = (0, 0, 0, 110)


def _load(path: Path, size: int, weight: int | None = None) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(str(path), size)
    if weight is not None:
        try:
            f.set_variation_by_axes([weight])
        except Exception:
            pass
    return f


def _wobble(i: int, n: int) -> float:
    """Alternating tilt per letter so the title reads hand-placed, not rigid."""
    base = -7 if i % 2 == 0 else 7
    # nudge the ends inward a touch
    return base * (0.7 + 0.3 * math.cos(math.pi * i / max(n - 1, 1)))


def _draw_bouncy_title(canvas: Image.Image, text: str, cx: int, top: int,
                       font: ImageFont.FreeTypeFont) -> tuple[int, int, int]:
    """Render each glyph on its own layer, rotate, and lay out left-to-right.
    Returns (left, right, bottom) bounding box of the placed title."""
    text = unicodedata.normalize("NFC", text)
    chars = list(text)
    n = len(chars)

    glyphs = []
    total_w = 0
    max_h = 0
    for ch in chars:
        if ch == " ":
            glyphs.append((" ", None, int(font.size * 0.32), 0))
            total_w += int(font.size * 0.32)
            continue
        bb = font.getbbox(ch, stroke_width=10)
        gw, gh = bb[2] - bb[0], bb[3] - bb[1]
        pad = 30
        tile = Image.new("RGBA", (gw + pad * 2, gh + pad * 2), (0, 0, 0, 0))
        d = ImageDraw.Draw(tile)
        # soft drop shadow first
        d.text((pad - bb[0] + 5, pad - bb[1] + 6), ch, font=font, fill=(120, 80, 0, 90),
               stroke_width=10, stroke_fill=(120, 80, 0, 90))
        # cream outline + yellow fill
        d.text((pad - bb[0], pad - bb[1]), ch, font=font, fill=YELLOW,
               stroke_width=10, stroke_fill=CREAM)
        glyphs.append((ch, tile, gw + pad * 2, gh + pad * 2))
        total_w += int(gw + pad * 1.2)
        max_h = max(max_h, gh)

    x = cx - total_w // 2
    left, right, bottom = x, x, top
    for i, (ch, tile, gw, gh) in enumerate(glyphs):
        if tile is None:
            x += gw
            continue
        ang = _wobble(i, n)
        rot = tile.rotate(ang, expand=True, resample=Image.BICUBIC)
        jitter = int(8 * math.sin(i * 1.7))
        py = top + jitter
        canvas.alpha_composite(rot, (x, py))
        right = x + gw
        bottom = max(bottom, py + rot.height)
        x += int(gw * 0.78)
    return left, right, bottom


def _sparkle(d: ImageDraw.ImageDraw, x: int, y: int, r: int, color=CREAM, wdt: int = 7):
    """Hand-drawn 4-point twinkle."""
    d.line([(x - r, y), (x + r, y)], fill=color, width=wdt)
    d.line([(x, y - r), (x, y + r)], fill=color, width=wdt)
    s = int(r * 0.45)
    d.line([(x - s, y - s), (x + s, y + s)], fill=color, width=max(2, wdt - 3))
    d.line([(x - s, y + s), (x + s, y - s)], fill=color, width=max(2, wdt - 3))


def _draw_centered_lines(canvas, lines, font, top, fill, gap, stroke=0,
                         stroke_fill=None, shadow=True):
    d = ImageDraw.Draw(canvas)
    y = top
    for ln in lines:
        bb = d.textbbox((0, 0), ln, font=font, stroke_width=stroke)
        lw, lh = bb[2] - bb[0], bb[3] - bb[1]
        x = (W - lw) // 2 - bb[0]
        if shadow:
            d.text((x + 3, y - bb[1] + 4), ln, font=font, fill=SHADOW, stroke_width=stroke)
        d.text((x, y - bb[1]), ln, font=font, fill=fill,
               stroke_width=stroke, stroke_fill=stroke_fill)
        y += lh + gap
    return y


def _wrap_lines(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """Wrap a line of text to fit within max_width pixels using the given font.
    Uses PIL's getbbox to measure actual rendered width for accurate wrapping."""
    if font.getbbox(text)[2] <= max_width:
        return [text]

    import textwrap
    # Estimate chars per line from average char width of the Latin alphabet
    sample = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    avg_char_w = font.getbbox(sample)[2] / len(sample)
    est_chars = max(1, int(max_width / avg_char_w))

    wrapped = textwrap.wrap(text, width=est_chars)
    # Refine: merge short adjacent lines if they fit together
    refined: list[str] = []
    for part in wrapped:
        if refined and font.getbbox(refined[-1] + " " + part)[2] <= max_width:
            refined[-1] += " " + part
        else:
            refined.append(part)
    return refined


def _bouncy_width(text: str, font: ImageFont.FreeTypeFont) -> int:
    """Measure the ACTUAL rendered width of the bouncy title by drawing it on a temp
    canvas (same layout path as _draw_bouncy_title) and reading the alpha bbox."""
    tmp = Image.new("RGBA", (2600, 700), (0, 0, 0, 0))
    _draw_bouncy_title(tmp, text, 1300, 60, font)
    bb = tmp.split()[3].getbbox()
    return (bb[2] - bb[0]) if bb else 0


def _fit_bouncy_font(text: str, max_w: int, start: int = 150, min_sz: int = 56) -> ImageFont.FreeTypeFont:
    """Pick the largest Baloo2 title size whose rendered bouncy title fits within max_w."""
    size = start
    while size > min_sz:
        f = _load(TITLE_FONT, size, weight=800)
        if _bouncy_width(text, f) <= max_w:
            return f
        size -= 5
    return _load(TITLE_FONT, min_sz, weight=800)


def build_overlay(
    title: str = "ĐÀ LẠT",
    script_lines: tuple[str, ...] = ("Review và chấm điểm", "các quán mà anh đã đi"),
    caption: str = "anh biết các em đã tốn rất nhiều tiền",
    out_path: str = "output/hook_overlay.png",
    with_caption: bool = True,
) -> str:
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    # 1) Title — bouncy yellow, around 11% from top. Auto-fit + true-center so long
    #    titles ("ĐÀ LẠT NƯỚNG") never clip on either edge.
    title_font = _fit_bouncy_font(title, max_w=W - 120, start=150, min_sz=56)
    top0 = int(H * 0.11)
    tmp = Image.new("RGBA", (2600, 800), (0, 0, 0, 0))
    _draw_bouncy_title(tmp, title, 1300, 80, title_font)
    tbb = tmp.split()[3].getbbox()
    crop = tmp.crop(tbb)
    px = (W - crop.width) // 2
    canvas.alpha_composite(crop, (px, top0))
    l, r, b = px, px + crop.width, top0 + crop.height

    # doodle sparkles around the title
    dd = ImageDraw.Draw(canvas)
    _sparkle(dd, l - 35, int(H * 0.115), 30)
    _sparkle(dd, r + 30, int(H * 0.16), 26)
    _sparkle(dd, r + 5, int(H * 0.10), 18, wdt=5)
    _sparkle(dd, l + 20, b - 10, 16, wdt=5)

    # 2) Handwriting script — white Caveat, just below the title, with wrapping
    script_font = _load(SCRIPT_FONT, 80, weight=700)
    script_margin = 80
    script_max_w = W - 2 * script_margin
    wrapped_script: list[str] = []
    for line in list(script_lines):
        wrapped_script.extend(_wrap_lines(line, script_font, script_max_w))
    y2 = _draw_centered_lines(canvas, wrapped_script, script_font,
                              top=b + 24, fill=WHITE, gap=4, shadow=True)

    # 3) Spoken caption — bottom third, white rounded with outline
    if with_caption and caption:
        import textwrap
        cap_font = _load(CAPTION_FONT, 60)
        cap_lines = textwrap.wrap(caption, width=24)
        # block height to anchor near 66% of frame
        line_h = cap_font.getbbox("Ay")[3] + 14
        block_top = int(H * 0.66)
        _draw_centered_lines(canvas, cap_lines, cap_font, top=block_top,
                             fill=WHITE, gap=14, stroke=6,
                             stroke_fill=(0, 0, 0, 200), shadow=False)

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out)
    return str(out)


# ── Main hooks (5 designs — overlay the user's blank frames, draw text only) ──
# The blank frame PNGs already contain the box + tag + cat/icon, so we only draw
# the user's title (+ subtitle) into the measured box region with the right font.

FRAME_DIR = Path(__file__).resolve().parent.parent / "assets" / "hook_frames"


def _ff(name: str, fallback: Path) -> Path:
    """Return the VN foundry font if the user dropped it in assets/fonts, else a free fallback."""
    p = FONT_DIR / name
    return p if p.exists() else fallback


# Free fonts (downloaded)
ASAP_FONT = FONT_DIR / "Asap-VF.ttf"
MAVEN_FONT = FONT_DIR / "MavenPro-VF.ttf"
ANTON_FONT = FONT_DIR / "Anton-Regular.ttf"
DEJAVU_FONT = FONT_DIR / "DejaVuSerif-Bold.ttf"
NOTO_FONT = FONT_DIR / "NotoSans-VF.ttf"
# VN foundry fonts (use real .ttf if present, else closest free fallback)
FOREST_FONT = _ff("Forest.ttf", SCRIPT_FONT)        # green subtitle
MJGLAMOUR_FONT = _ff("MJGlamour.ttf", FONT_DIR / "PlayfairDisplay-VF.ttf")  # brown serif title
UTMFUTURA_FONT = _ff("UTMFutura.ttf", FONT_DIR / "Montserrat-VF.ttf")       # brown subtitle
SVNMANGO_FONT = _ff("SVN-Mango.ttf", TITLE_FONT)    # cat title (Baloo2 fallback)

# kind always "png_frame": overlay the blank frame + draw text in `region` (x0,y0,x1,y1).
HOOK_DESIGNS = {
    "hook_red": {
        "frame": "red.png", "region": (235, 470, 872, 690),
        "title": {"font": ASAP_FONT, "wght": 700, "color": (139, 26, 26, 255), "max": 92, "min": 38},
        "subtitle": {"font": MAVEN_FONT, "wght": 600, "color": (150, 42, 42, 255), "max": 46, "min": 24, "gap": 12},
    },
    "hook_green": {
        "frame": "green.png", "region": (245, 472, 872, 762),
        "title": {"font": ANTON_FONT, "wght": None, "color": (255, 255, 255, 255), "max": 104, "min": 42},
        "subtitle": {"font": FOREST_FONT, "wght": None, "color": (233, 211, 90, 255), "max": 58, "min": 28, "gap": 6},
    },
    "hook_brown": {
        "frame": "brown.png", "region": (170, 495, 912, 695),
        "title": {"font": MJGLAMOUR_FONT, "wght": 700, "color": (243, 234, 217, 255), "max": 104, "min": 40},
        "subtitle": {"font": UTMFUTURA_FONT, "wght": None, "color": (224, 213, 195, 255), "max": 42, "min": 22, "gap": 8},
    },
    "hook_serif": {  # "Khung vuông cơ bản" — title only
        "frame": "serif.png", "region": (148, 458, 936, 548), "no_subtitle": True,
        "title": {"font": DEJAVU_FONT, "wght": None, "color": (15, 15, 15, 255), "max": 58, "min": 26},
    },
    "hook_meo": {  # title only, black outline
        "frame": "meo.png", "region": (240, 648, 892, 858), "no_subtitle": True,
        "title": {"font": SVNMANGO_FONT, "wght": 700, "color": (40, 40, 40, 255), "max": 70, "min": 30,
                  "stroke_w": 5, "stroke_fill": (0, 0, 0, 255)},
    },
}


def _fit_lines(font_path, wght, text, max_w, max_h, start, min_sz, stroke_w=0):
    """Largest size (of font_path at weight wght) whose wrapped lines fit (max_w, max_h)."""
    text = unicodedata.normalize("NFC", (text or "").strip())
    size = start
    while size >= min_sz:
        f = _load(font_path, size, weight=wght)
        lines = _wrap_lines(text, f, max_w)
        line_h = f.getbbox("Ày", stroke_width=stroke_w)[3] + max(4, size // 6)
        widest = max((f.getbbox(ln, stroke_width=stroke_w)[2] for ln in lines), default=0)
        if line_h * len(lines) <= max_h and widest <= max_w:
            return f, lines, line_h
        size -= 3
    f = _load(font_path, min_sz, weight=wght)
    return f, _wrap_lines(text, f, max_w), f.getbbox("Ày", stroke_width=stroke_w)[3] + 6


def _draw_lines_block(d, lines, font, line_h, color, cx, top, stroke_w=0, stroke_fill=None):
    """Draw centered lines starting at y=top, centered on cx. Returns bottom y."""
    y = top
    for ln in lines:
        bb = d.textbbox((0, 0), ln, font=font, stroke_width=stroke_w)
        lw = bb[2] - bb[0]
        d.text((cx - lw // 2 - bb[0], y - bb[1]), ln, font=font, fill=color,
               stroke_width=stroke_w, stroke_fill=stroke_fill)
        y += line_h
    return y


# Màu LỚP TINT phủ nền (3 biến thể) — KHÔNG phải màu pill.
NEWS_LAYER_COLORS = {
    "pink":   (228, 74, 128),
    "green":  (54, 150, 92),
    "purple": (120, 72, 200),
}
# Pill hashtag CỐ ĐỊNH: gradient xanh → hồng (không đổi theo màu layer).
PILL_GRAD = [(79, 140, 255), (239, 93, 168)]


def _grad_pill(size, c1, c2, radius):
    """Horizontal 2-stop gradient rounded pill (RGBA)."""
    w, h = size
    base = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    grad = Image.new("RGBA", (w, h))
    for x in range(w):
        t = x / max(1, w - 1)
        r = int(c1[0] + (c2[0] - c1[0]) * t)
        g = int(c1[1] + (c2[1] - c1[1]) * t)
        b = int(c1[2] + (c2[2] - c1[2]) * t)
        for y in range(h):
            grad.putpixel((x, y), (r, g, b, 255))
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, fill=255)
    base.paste(grad, (0, 0), mask)
    return base


def build_news_hook(caption: str, out_path: str, color: str = "pink",
                    hashtag: str = "#dalatnow", username: str = "dalatnow",
                    tags: str = "#dalatnow #dalat #checkin #dalattrip #dalatfood") -> str:
    """Full-frame news overlay: 'ĐÀ LẠT' title top + bottom COLOR TINT layer (3 màu) with a
    FIXED blue→pink hashtag pill, big uppercase caption, footer. color = màu lớp tint."""
    caption = unicodedata.normalize("NFC", (caption or "").strip()).upper()
    tint = NEWS_LAYER_COLORS.get(color, NEWS_LAYER_COLORS["pink"])
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(canvas)

    # bottom COLOR tint layer (theme màu) — đậm dưới đáy, fade lên; pha chút tối cho chữ trắng rõ
    gh = int(H * 0.40)
    grad = Image.new("RGBA", (W, gh))
    tr, tg, tb = tint
    for y in range(gh):
        f = (y / gh) ** 1.25
        a = int(225 * f)
        # tối nhẹ về đáy để chữ trắng nổi
        r = int(tr * (1 - 0.25 * f)); g = int(tg * (1 - 0.25 * f)); b = int(tb * (1 - 0.25 * f))
        for x in range(0, W, 4):
            grad.paste((r, g, b, a), (x, y, min(x + 4, W), y + 1))
    canvas.alpha_composite(grad, (0, H - gh))

    # 1) Title "ĐÀ LẠT" top (script) + small subtitle
    tf = _fit_bouncy_font("ĐÀ LẠT", max_w=W - 200, start=140, min_sz=90)
    # reuse handwriting-ish: use DancingScript for elegance
    title_font = _load(SCRIPT_FONT, 150, weight=700)
    bb = d.textbbox((0, 0), "ĐÀ LẠT", font=title_font)
    d.text(((W - (bb[2] - bb[0])) // 2 - bb[0], int(H * 0.045)), "ĐÀ LẠT", font=title_font,
           fill=(255, 255, 255, 255), stroke_width=3, stroke_fill=(0, 0, 0, 90))
    sub_font = _load(SCRIPT_FONT, 50, weight=600)
    sbb = d.textbbox((0, 0), "Đi thôi nào", font=sub_font)
    d.text(((W - (sbb[2] - sbb[0])) // 2 - sbb[0], int(H * 0.045) + 150), "Đi thôi nào",
           font=sub_font, fill=(255, 255, 255, 220))

    # 2) Hashtag pill (gradient) — bottom area, left-aligned
    pill_font = _load(NOTO_FONT, 40, weight=700)
    pbb = d.textbbox((0, 0), hashtag, font=pill_font)
    ptw, pth = pbb[2] - pbb[0], pbb[3] - pbb[1]
    padx, pady = 30, 16
    pill = _grad_pill((ptw + 2 * padx, pth + 2 * pady), PILL_GRAD[0], PILL_GRAD[1], (pth + 2 * pady) // 2)
    px, py = 70, int(H * 0.70)
    canvas.alpha_composite(pill, (px, py))
    ImageDraw.Draw(canvas).text((px + padx - pbb[0], py + pady - pbb[1]), hashtag,
                                font=pill_font, fill=(255, 255, 255, 255))

    # 3) Big caption (uppercase, 2-3 lines) white bold
    d = ImageDraw.Draw(canvas)
    cap_font, cap_lines, cap_lh = _fit_lines(CAPTION_FONT, None, caption, W - 140, 360, 76, 40)
    y = py + pth + 2 * pady + 24
    for ln in cap_lines:
        lbb = d.textbbox((0, 0), ln, font=cap_font)
        d.text((70, y - lbb[1]), ln, font=cap_font, fill=(255, 255, 255, 255),
               stroke_width=2, stroke_fill=(0, 0, 0, 120))
        y += cap_lh

    # 4) Footer: username + hashtags
    foot_font = _load(NOTO_FONT, 30, weight=600)
    d.text((70, H - 110), f"{username} · 5-31", font=foot_font, fill=(255, 255, 255, 235))
    tag_font = _load(NOTO_FONT, 26, weight=500)
    d.text((70, H - 66), tags, font=tag_font, fill=(255, 255, 255, 200))

    out = Path(out_path); out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out)
    return str(out)


def build_hook(style: str, title: str, subtitle: str, out_path: str) -> str:
    """Overlay the blank frame for `style` and draw the user's title (+subtitle)
    centered in its box region. Returns the output PNG path."""
    cfg = HOOK_DESIGNS[style]
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    frame = Image.open(FRAME_DIR / cfg["frame"]).convert("RGBA")
    if frame.size != (W, H):
        frame = frame.resize((W, H), Image.LANCZOS)
    canvas.alpha_composite(frame, (0, 0))

    title = unicodedata.normalize("NFC", (title or "").strip())
    subtitle = "" if cfg.get("no_subtitle") else unicodedata.normalize("NFC", (subtitle or "").strip())
    tcfg = cfg["title"]
    scfg = cfg.get("subtitle")

    x0, y0, x1, y1 = cfg["region"]
    box_w, box_h = x1 - x0, y1 - y0
    cx = (x0 + x1) // 2
    d = ImageDraw.Draw(canvas)

    sw = tcfg.get("stroke_w", 0)
    title_h_share = box_h * (0.62 if subtitle else 1.0)
    tf, tlines, tlh = _fit_lines(tcfg["font"], tcfg["wght"], title, box_w, title_h_share,
                                 tcfg["max"], tcfg["min"], stroke_w=sw)
    blocks = [(tf, tlines, tlh, tcfg["color"], sw, tcfg.get("stroke_fill"))]
    gap = 0
    if subtitle and scfg:
        sf, slines, slh = _fit_lines(scfg["font"], scfg["wght"], subtitle, box_w, box_h * 0.38,
                                     scfg["max"], scfg["min"])
        gap = scfg.get("gap", 8)
        blocks.append((sf, slines, slh, scfg["color"], 0, None))

    total_h = sum(lh * len(ls) for _, ls, lh, _, _, _ in blocks) + gap
    y = y0 + (box_h - total_h) // 2
    for i, (f, ls, lh, col, s_w, s_fill) in enumerate(blocks):
        if i == 1:
            y += gap
        y = _draw_lines_block(d, ls, f, lh, col, cx, y, stroke_w=s_w, stroke_fill=s_fill)

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out)
    return str(out)


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Render Đà Lạt hook overlay PNG")
    ap.add_argument("--title", default="ĐÀ LẠT")
    ap.add_argument("--script", default="Review và chấm điểm|các quán mà anh đã đi",
                    help="handwriting lines separated by |")
    ap.add_argument("--caption", default="anh biết các em đã tốn rất nhiều tiền")
    ap.add_argument("--no-caption", action="store_true")
    ap.add_argument("--out", default="output/hook_overlay.png")
    args = ap.parse_args()

    p = build_overlay(
        title=args.title,
        script_lines=tuple(args.script.split("|")),
        caption=args.caption,
        out_path=args.out,
        with_caption=not args.no_caption,
    )
    print("Saved:", p)
