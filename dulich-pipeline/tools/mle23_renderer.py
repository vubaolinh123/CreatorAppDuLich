"""
mle23_renderer.py — T1 "99% khách du lịch" (1080×1280px, 5 slides).

  render_cover(bg_path, out_path)
  render_ggmaps_tip(bg_path, out_path)
  render_oneway(bg_path, out_path)
  render_activities(bg_path, out_path)
  render_food(bg_path, out_path, food_photos=[])
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from tools.render_utils import load_bg, load_thumb, placeholder_thumb, anton, beviet_bold, dancing, load_font

def baloo2(size: int):
    return load_font("Baloo2-VF.ttf", size)

def _skew_text(text: str, font, fill: tuple, skew: float = 0.25) -> Image.Image:
    """Render text then apply horizontal shear to simulate italic/cursive."""
    PAD = 60  # generous padding so below-baseline marks (ị dot) aren't clipped
    tmp = Image.new("RGBA", (1800, 600), (0, 0, 0, 0))
    d = ImageDraw.Draw(tmp)
    d.text((10, PAD), text, fill=fill, font=font)
    bb = d.textbbox((10, PAD), text, font=font)
    tw = bb[2] - bb[0] + 40
    th = bb[3] - bb[1] + PAD * 2  # keep room above AND below
    src_w = tw + int(th * abs(skew)) + 20
    src_h = th
    crop = tmp.crop((0, 0, src_w, src_h))
    data = (1, -skew, 0,   0, 1, 0)
    sheared = crop.transform(crop.size, Image.Transform.AFFINE, data,
                             resample=Image.Resampling.BICUBIC)
    # Trim transparent rows/cols
    bbox = sheared.getbbox()
    if bbox:
        sheared = sheared.crop(bbox)
    return sheared

W, H = 1080, 1280
YELLOW  = (245, 198, 24)
DARK_RED = (115, 22, 22)
WHITE   = (255, 255, 255)
BLACK   = (20, 20, 20)

CARD_X     = 46
CARD_W     = 988
CARD_R     = 18
CARD_PAD_X = 46
CARD_PAD_T = 30
PILL_H     = 58
LINE_H     = 46


# ── Helpers ───────────────────────────────────────────────────────────────────

def _save(img: Image.Image, out_path: str) -> str:
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    img.save(out_path)
    return out_path


def _card(draw: ImageDraw.ImageDraw, x, y, w, h):
    draw.rounded_rectangle([x, y, x + w, y + h], radius=CARD_R, fill=WHITE)


def _pill(draw: ImageDraw.ImageDraw, text: str, cx: int, y: int,
          font_size: int = 30) -> int:
    f = beviet_bold(font_size)
    bb = draw.textbbox((0, 0), text, font=f)
    tw = bb[2] - bb[0]
    pw = tw + 60
    ph = PILL_H
    px = cx - pw // 2
    draw.rounded_rectangle([px, y, px + pw, y + ph], radius=ph // 2, fill=DARK_RED)
    draw.text((cx - tw // 2, y + (ph - (bb[3] - bb[1])) // 2),
              text, fill=WHITE, font=f)
    return y + ph


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_w: int) -> list[str]:
    words, lines, cur = text.split(" "), [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if draw.textlength(test, font=font) <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines or [""]


def _body(draw: ImageDraw.ImageDraw, items: list, x: int, y: int,
          max_w: int, base_font, line_h: int = LINE_H) -> int:
    """Draw (type, text) list. Returns bottom y.
    types: 'para', 'header', 'bullet'
    """
    for typ, text in items:
        if typ == "header":
            f, c = beviet_bold(28), DARK_RED
        else:
            f, c = base_font, BLACK
        if typ == "bullet":
            text = "• " + text

        for i, line in enumerate(_wrap(draw, text, f, max_w)):
            xi = x + (28 if (typ == "bullet" and i > 0) else 0)
            draw.text((xi, y), line, fill=c, font=f)
            y += line_h
    return y


ORANGE = (210, 85, 0)

def _badge(draw: ImageDraw.ImageDraw, text: str, cx: int, cy: int,
           fs: int = 24, bg: tuple = (158, 26, 26), text_color: tuple = None):
    if text_color is None:
        text_color = WHITE
    f = beviet_bold(fs)
    bb = draw.textbbox((0, 0), text, font=f)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    pw, ph = tw + 26, th + 18
    px, py = cx - pw // 2, cy - ph // 2
    draw.rounded_rectangle([px, py, px + pw, py + ph],
                           radius=ph // 2, fill=bg)
    draw.text((cx - tw // 2, cy - th // 2), text, fill=text_color, font=f)


# ── Page 0: Cover ─────────────────────────────────────────────────────────────

GREEN = (43, 71, 33)  # olive green for Tháng 5 / @ badges


def render_cover(bg_path: str, out_path: str, spec: dict | None = None) -> str:
    s = spec or {}
    month_tag  = s.get("month_tag",  "Tháng 6")
    handle_tag = s.get("handle_tag", "@thamhiemdalat")

    img = load_bg(bg_path, W, H)
    draw = ImageDraw.Draw(img, "RGBA")

    # Top gradient
    for i in range(560):
        a = int(170 * max(0, 1 - i / 560))
        draw.line([(0, i), (W, i)], fill=(0, 0, 0, a))

    # ── "99%" top-left ──────────────────────────────────────────────────────
    draw.text((50, 25), "99%", fill=YELLOW, font=anton(160))

    # (badges moved down near oval — drawn after oval is composited)

    # ── "khách du lịch" — Baloo2, BELOW 99%, auto-sized ────────────────────
    _fs = 175
    while _fs > 60:
        if draw.textlength("khách du lịch", font=baloo2(_fs)) < W - 40:
            break
        _fs -= 5
    _f_title = baloo2(_fs)
    _tw = draw.textlength("khách du lịch", font=_f_title)
    _top99 = 25 + int(160 * 0.82)
    _title_y = _top99 + 10
    draw.text(((W - _tw) // 2, _title_y), "khách du lịch",
              fill=YELLOW, font=_f_title)

    # ── Dark oval with centered subtitle ────────────────────────────────────
    f_ov = beviet_bold(30)
    line1 = "/chưa biết những điều này"
    line2 = "hoặc chưa từng trải nghiệm /"
    bb1 = draw.textbbox((0, 0), line1, font=f_ov)
    bb2 = draw.textbbox((0, 0), line2, font=f_ov)
    max_tw = max(bb1[2] - bb1[0], bb2[2] - bb2[0])
    ow = max_tw + 80
    oh = 118
    ox = (W - ow) // 2

    _bb_title = draw.textbbox(((W - _tw) // 2, _title_y), "khách du lịch", font=_f_title)
    oy = _bb_title[3] + 28

    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ov = ImageDraw.Draw(overlay)
    ov.rounded_rectangle([ox, oy, ox + ow, oy + oh], radius=oh // 2,
                         fill=(28, 24, 24, 210))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(img)

    lh = (bb1[3] - bb1[1])
    gap = 10
    block_h = lh * 2 + gap
    y1 = oy + (oh - block_h) // 2
    y2 = y1 + lh + gap
    draw.text((W // 2, y1), line1, fill=WHITE, font=f_ov, anchor="mt")
    draw.text((W // 2, y2), line2, fill=WHITE, font=f_ov, anchor="mt")

    # ── Badges: bottom-left corner — Dalat trên, @handle dưới ─────────────
    f_h = beviet_bold(20)
    bb_h = draw.textbbox((0, 0), handle_tag, font=f_h)
    hw = bb_h[2] - bb_h[0] + 26
    handle_ph = (bb_h[3] - bb_h[1]) + 18

    f_d = beviet_bold(22)
    bb_d = draw.textbbox((0, 0), "Dalat", font=f_d)
    dw = bb_d[2] - bb_d[0] + 26
    dalat_ph = (bb_d[3] - bb_d[1]) + 18

    TAG_PAD = 28
    BETWEEN = 10
    # Tính y từ đáy lên: @handle ở dưới cùng, Dalat ngay trên
    handle_cy = H - TAG_PAD - handle_ph // 2
    dalat_cy  = handle_cy - handle_ph // 2 - BETWEEN - dalat_ph // 2
    _badge(draw, "Dalat",     CARD_X + dw // 2, dalat_cy,  fs=22, bg=DARK_RED)
    _badge(draw, handle_tag,  CARD_X + hw // 2, handle_cy, fs=20, bg=WHITE, text_color=ORANGE)

    return _save(img, out_path)


# ── Page 1: Google Maps tip ────────────────────────────────────────────────────

_GGMAPS_TEXT = (
    "Bạn có biết vì sao Google hay dẫn bạn đi đường nhỏ, hẹp khó đi không? "
    "Vì bạn đang bật chế độ xe máy hoặc đi bộ, nên Google sẽ ưu tiên đường "
    "như này. Nếu chuyển sang chế độ ô tô, Google sẽ chọn đường dễ đi hơn. ›"
)


def render_ggmaps_tip(bg_path: str, out_path: str) -> str:
    img = load_bg(bg_path, W, H, overlay_alpha=55)
    draw = ImageDraw.Draw(img)

    f = beviet_bold(28)
    max_tw = CARD_W - CARD_PAD_X * 2
    lines = _wrap(draw, _GGMAPS_TEXT, f, max_tw)

    card_h = 50 + len(lines) * LINE_H + 50
    card_y = 28
    _card(draw, CARD_X, card_y, CARD_W, card_h)

    ty = card_y + 50
    for line in lines:
        draw.text((CARD_X + CARD_PAD_X, ty), line, fill=BLACK, font=f)
        ty += LINE_H

    return _save(img, out_path)


# ── Page 2: Đường một chiều ───────────────────────────────────────────────────

_ONEWAY = [
    "Nguyễn Văn Trỗi",
    "Trương Công Định (hướng Khu Hòa Bình)",
    "Rạp chiếu phim ngay Khu Hòa Bình",
    "Phan Bội Châu (đến rạp chiếu phim 3/4)",
    "Yagout",
    "Trần Nhật Duật",
    "Thống Thiên Học (ngã ba Tình Đội)",
]


def render_oneway(bg_path: str, out_path: str) -> str:
    img = load_bg(bg_path, W, H, overlay_alpha=55)
    draw = ImageDraw.Draw(img)

    f = beviet_bold(28)
    max_tw = CARD_W - CARD_PAD_X * 2 - 30

    total_h = sum(len(_wrap(draw, "• " + s, f, max_tw)) for s in _ONEWAY)
    card_h = CARD_PAD_T + PILL_H + 28 + total_h * LINE_H + CARD_PAD_T
    card_y = 28

    _card(draw, CARD_X, card_y, CARD_W, card_h)
    pill_bot = _pill(draw, "ĐÀ LẠT CÓ NHIỀU ĐƯỜNG MỘT CHIỀU",
                     W // 2, card_y + CARD_PAD_T, font_size=30)

    ty = pill_bot + 28
    tx = CARD_X + CARD_PAD_X
    for s in _ONEWAY:
        text = "• " + s
        for i, line in enumerate(_wrap(draw, text, f, max_tw)):
            draw.text((tx + (28 if i > 0 else 0), ty), line, fill=BLACK, font=f)
            ty += LINE_H

    return _save(img, out_path)


# ── Page 3: Điểm vui chơi ─────────────────────────────────────────────────────

_ACT_ITEMS = [
    ("para",   "Đà Lạt sở hữu nhiều điểm vui chơi đa dạng, từ những nơi check-in sống ảo đến các trải nghiệm cảm giác mạnh đây."),
    ("header", "Điểm check-in miễn phí:"),
    ("bullet", "Tháp Vinaphone, Dinh tỉnh trường, Chứng viên Minh Hòa, Biệt thự cô Giang, các con dốc"),
    ("header", "Quán cà phê đẹp để sống ảo:"),
    ("bullet", "Chang vang (119 Huỳnh tấn Phát), JJU Coffee, Hidden Land (Lâm Văn Thanh), Nook Café (Hẻm Dã Chiến)"),
    ("header", "Khu vui chơi:"),
    ("bullet", "Langbiang Farm, chèo SUP hồ Tuyền Lâm, Chika Farm, The Florest, Puppy Farm, Mongo Land (Tà Nung)."),
]


def render_activities(bg_path: str, out_path: str) -> str:
    img = load_bg(bg_path, W, H, overlay_alpha=55)
    draw = ImageDraw.Draw(img)

    f = beviet_bold(27)
    max_tw = CARD_W - CARD_PAD_X * 2 - 20

    total_h = 0
    for typ, text in _ACT_ITEMS:
        fnt = beviet_bold(28) if typ == "header" else f
        t2 = ("• " + text) if typ == "bullet" else text
        total_h += len(_wrap(draw, t2, fnt, max_tw))

    card_h = CARD_PAD_T + PILL_H + 28 + total_h * LINE_H + CARD_PAD_T
    card_y = 28

    _card(draw, CARD_X, card_y, CARD_W, card_h)
    pill_bot = _pill(draw, "ĐÀ LẠT NHỎ THẾ, CÓ GÌ CHƠI ĐÂU?",
                     W // 2, card_y + CARD_PAD_T, font_size=30)

    _body(draw, _ACT_ITEMS, CARD_X + CARD_PAD_X, pill_bot + 28, max_tw, f)
    return _save(img, out_path)


# ── Page 4: Ăn uống ngon ──────────────────────────────────────────────────────

_FOOD_INTRO = (
    "Đà Lạt là thành phố du lịch nên nhiều người nghĩ đồ ăn không ngon mà "
    "lại mắc. Thực tế thì không hẳn, vẫn có nhiều quán ngon, view đẹp ngay "
    "trung tâm, không phải đi xa."
)

_FOOD_ITEMS = [
    ("para",   _FOOD_INTRO),
    ("header", "Quán ăn ngon nên thử"),
    ("bullet", "Yod Thong - quán Thái : 04 Đoàn Thị Điểm"),
    ("bullet", "Sườn Cay Không Lồ : 42 Phan Chu Trinh"),
    ("bullet", "Trạm Nắng BBQ : 18 Đồng Đa"),
    ("bullet", "Lẩu Bò Gia Lâm - 30 Ngô Quyền"),
    ("bullet", "Há Cảo Trần Lê - 15 Phạm Ngũ Lão"),
    ("bullet", "Túi Mơ To Garden - hẻm Sào Nam"),
    ("bullet", "Cơm Linh - 23 Sương Nguyệt Anh"),
]

GRID_H = 320


def render_food(bg_path: str, out_path: str,
                food_photos: Optional[list[str]] = None) -> str:
    img = load_bg(bg_path, W, H, overlay_alpha=55)
    draw = ImageDraw.Draw(img)

    f = beviet_bold(27)
    max_tw = CARD_W - CARD_PAD_X * 2 - 20

    total_h = 0
    for typ, text in _FOOD_ITEMS:
        fnt = beviet_bold(28) if typ == "header" else f
        t2 = ("• " + text) if typ == "bullet" else text
        total_h += len(_wrap(draw, t2, fnt, max_tw))

    text_block_h = CARD_PAD_T + PILL_H + 28 + total_h * LINE_H + 20
    card_h = text_block_h + GRID_H + CARD_PAD_T
    card_y = 28

    _card(draw, CARD_X, card_y, CARD_W, card_h)
    pill_bot = _pill(draw, "ĂN UỐNG Ở ĐÂU NGON",
                     W // 2, card_y + CARD_PAD_T, font_size=30)

    ty = _body(draw, _FOOD_ITEMS, CARD_X + CARD_PAD_X, pill_bot + 28, max_tw, f)

    # 3-photo grid
    ty += 16
    photos = ((food_photos or []) + ["", "", ""])[:3]
    gap = 12
    pw = (CARD_W - CARD_PAD_X * 2 - gap * 2) // 3
    for i, pp in enumerate(photos):
        px = CARD_X + CARD_PAD_X + i * (pw + gap)
        if pp and os.path.exists(pp):
            thumb = load_thumb(pp, (pw, GRID_H))
        else:
            thumb = placeholder_thumb((pw, GRID_H))
        img.paste(thumb, (px, ty))

    return _save(img, out_path)


# ── Generic: Venue list slide ──────────────────────────────────────────────────

def render_venue_list(bg_path: str, pill_text: str, venues: list, out_path: str) -> str:
    """
    Generic slide: photo BG + white card + red pill header + venue bullet list.
    venues: list of dicts with keys name, signature (opt), address (opt)
    """
    img = load_bg(bg_path, W, H, overlay_alpha=55)
    draw = ImageDraw.Draw(img)

    f = beviet_bold(27)
    max_tw = CARD_W - CARD_PAD_X * 2 - 30

    def _venue_line(v):
        name = v.get("name", "")
        sig  = v.get("signature", "")
        addr = v.get("address", "")
        if len(addr) > 45:
            addr = addr.split(",")[0].strip()
        if sig:
            return f"{name} — {sig}"
        if addr:
            return f"{name} : {addr}"
        return name

    lines_per_item = [len(_wrap(draw, "• " + _venue_line(v), f, max_tw)) for v in venues]
    total_lines = sum(lines_per_item)
    card_h = CARD_PAD_T + PILL_H + 28 + total_lines * LINE_H + CARD_PAD_T
    card_h = min(card_h, H - 56)
    card_y = 28

    _card(draw, CARD_X, card_y, CARD_W, card_h)
    pill_bot = _pill(draw, pill_text, W // 2, card_y + CARD_PAD_T, font_size=30)

    ty = pill_bot + 28
    tx = CARD_X + CARD_PAD_X
    max_y = card_y + card_h - CARD_PAD_T
    for v in venues:
        text = "• " + _venue_line(v)
        for i, line in enumerate(_wrap(draw, text, f, max_tw)):
            if ty + LINE_H > max_y:
                break
            draw.text((tx + (28 if i > 0 else 0), ty), line, fill=BLACK, font=f)
            ty += LINE_H

    return _save(img, out_path)
