"""
uyn711_renderer.py — Template T5 "7 điều đừng làm ở Đà Lạt" (UYN 7/11).
Canvas: 1080×1390px (7 pages).

Pages:
  0 – Cover (full-bleed photo)
  1 – Title (photo + hook text top-right)
  2 – "❎ KO QUÁ TIN VÀO ẢNH MẠNG 100%"
  3 – "❎ KO PHẢI LÚC NÀO CŨNG SĂN DC MÂY"
  4 – "❎ KO DC QUÊN MẤY DỊCH VỤ NÀY"
  5 – "❎ KO DC QUÊN ĐỒ DÙNG CẦN THIẾT"
  6 – "❎ KO ĂN UỐNG KHI CHƯA HỎI GIÁ"

Fonts:
  SuaserifBold.otf — page 1 title text (YAGzbIdqPiY_0)
  BeVietnamPro-Bold-full.ttf — pages 2-6 content (YADK30bC6HQ_0 approximation)

Layout (canvas coords, 1080×1390):
  Title text (pages 2-6):  y=97, 60px, centered, white+5px black stroke
  Content photo (left):    x=0, y=66, w=476, h=672
  Tips text (right):       x=516, y=266, 40px, white+4px black stroke
  White box bottom:        y=849 to 1390
  Bottom header:           cx=131, cy=849–910, 40px, black
  Bottom list left col:    cx=199, from cy=901, spacing=56
  Bottom list right col:   cx=615, from cy=901, spacing=56
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFilter

from tools.render_utils import (
    load_bg as _load_bg_util,
    load_thumb as _load_thumb,
    load_font,
    beviet_bold,
    dancing,
)

W, H = 1080, 1390
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
DARK_OVERLAY = (0, 0, 0, 160)

# Layout constants
WHITE_BOX_Y = 849
PHOTO_X, PHOTO_Y = 0, 66
PHOTO_W, PHOTO_H = 476, 672

TITLE_Y = 97
TITLE_SIZE = 48
TIPS_X = 516
TIPS_Y = 266
TIPS_SIZE = 34
TIPS_LINE_H = 56

BTM_HEADER_X = 131
BTM_ITEM_X_L = 199
BTM_ITEM_X_R = 615
BTM_ITEM_Y = 901
BTM_ITEM_SPACING = 56


def _suaserif(size: int):
    return load_font("SuaserifBold.otf", size)


def _content_font(size: int):
    return beviet_bold(size)


def _load_bg(path: str, blur: bool = False, alpha: int = 0) -> Image.Image:
    return _load_bg_util(path, W, H, blur, alpha)


def _stroke_text(draw: ImageDraw.Draw, xy: tuple, text: str, font,
                 fill=WHITE, stroke_w: int = 5, stroke_fill=BLACK,
                 anchor: str = "la") -> None:
    """Draw text with stroke. anchor='mm' for center, 'la' for top-left."""
    draw.text(xy, text, font=font, fill=fill,
              stroke_width=stroke_w, stroke_fill=stroke_fill,
              anchor=anchor)


def _multiline_stroke(draw: ImageDraw.Draw, x: int, y: int,
                      text: str, font, fill=WHITE,
                      stroke_w: int = 4, spacing: int = 8) -> None:
    """Draw multiline text block with stroke, left-aligned."""
    for line in text.split("\n"):
        if line.strip():
            draw.text((x, y), line, font=font, fill=fill,
                      stroke_width=stroke_w, stroke_fill=BLACK)
            bbox = font.getbbox(line)
            line_h = bbox[3] - bbox[1]
            y += line_h + spacing
        else:
            y += TIPS_LINE_H  # blank line = paragraph break


# ── Page 0: Cover ─────────────────────────────────────────────────────────────

def render_cover(bg_path: str, out_path: str) -> str:
    img = _load_bg(bg_path)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG")
    return out_path


# ── Page 1: Title ─────────────────────────────────────────────────────────────

def render_title(bg_path: str, out_path: str) -> str:
    img = _load_bg(bg_path, alpha=20)
    canvas = img.convert("RGBA")
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # DancingScript: handwriting style, full Vietnamese coverage
    font = dancing(38)
    line1 = "Đi Đà Lạt nhiều r nhưng giờ ce tui"
    line2 = "mới nhận ra mấy điều này :))))"
    x, y = 448, 164
    for line in (line1, line2):
        draw.text((x + 2, y + 2), line, font=font, fill=(0, 0, 0, 100))
        draw.text((x, y), line, font=font, fill=WHITE)
        bbox = font.getbbox(line)
        y += (bbox[3] - bbox[1]) + 10

    canvas.alpha_composite(overlay)
    out = canvas.convert("RGB")
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    out.save(out_path, "PNG")
    return out_path


# ── Pages 2-6: Tip slides ─────────────────────────────────────────────────────

# Static content per slide (indexed 0-4 = pages 2-6)
_SLIDES = [
    {   # slide 0 = page 2
        "title": "KO QUÁ TIN VÀO ẢNH MẠNG 100%",
        "tips": (
            "1 SỐ ĐIỂM CHECK-IN NỔI\n"
            "TIẾNG TRÊN MẠNG NHƯNG\n"
            "NGOÀI ĐỜI NHỎ HOẶC KO\n"
            "NHƯ MONG ĐỢI\n"
            "\n"
            "NÊN XEM REVIEW THỰC TẾ\n"
            "TỪ NHIỀU NGUỒN, CÓ VID\n"
            "CÀNG TỐT"
        ),
        "btm_header": "ĐỊA ĐIỂM CHECK-IN HOT HIT DẠO NÀY",
        "btm_left":  ["CHẠNG VẠNG", "NHÀ BÊN SUỐI", "NHÀ BÊN RỪNG", "MIỀN DU MỤC", "HOÀNG HÔN CHIỀU", "DỐC THỊ"],
        "btm_right": ["SUỐI BÌNH YÊN", "CHEO VEO", "THUNG MƠ", "OLLIN CAFE", "ĐỢI MỘT NGƯỜI", "THÔN 13"],
        "two_col": True,
    },
    {   # slide 1 = page 3
        "title": "KO PHẢI LÚC NÀO CŨNG SĂN DC MÂY",
        "tips": (
            "KO CHECK THỜI TIẾT MÀ CỨ\n"
            "THẾ ĐI, ĐẾN NƠI KO CÓ MÂY\n"
            "VỪA TỐN SỨC, TỐN TGIAN\n"
            "\n"
            "XEM KĨ THỜI TIẾT, CHỌN\n"
            "NGÀY NẮNG SAU MƯA MÂY\n"
            "SẼ DÀY HƠN. ĐI MẤY QUÁN\n"
            "SĂN MÂY GẦN TRUNG TÂM LÀ\n"
            "OKI, KO CẦN ĐI QUÁ XA"
        ),
        "btm_header": "ĐỊA ĐIỂM SĂN MÂY ĐẸP, GẦN TRUNG TÂM",
        "btm_left":  ["CAFE HOÀNG HÔN CHIỀU", "TRÊN ĐỒI CÓ MÂY", "BÌNH MINH ƠI", "THUNG LŨNG KHÓI XANH", "ĐỒI ĐA PHÚ", "ĐỒI MĂNG LIN"],
        "btm_right": [],
        "two_col": False,
    },
    {   # slide 2 = page 4
        "title": "KO DC QUÊN MẤY DỊCH VỤ NÀY",
        "tips": (
            "NÊN BOOK PHÒNG TRƯỚC\n"
            "NHẤT LÀ MÙA CAO ĐIỂM LỄ,\n"
            "TẾT NẾU KO DỄ\n"
            "TÌNH TRẠNG LỪA ĐẢO NHÌU\n"
            "NÊN MNG BOOK QUA APP\n"
            "CHO CHẮC, BOOK TRƯỚC CỠ\n"
            "2 TUẦN LÀ HỢP LÍ"
        ),
        "btm_sections": [
            ("CHỖ Ở", ["COZY GARDEN", "AN MAI BOUTIQUE", "600K/ ĐÊM/ 2 NGƯỜI"]),
            ("DI CHUYỂN", ["HL: 03345 SÁU BẢY HAI 571", "XE GA 150K/ 24H. GIAO NHẬN TẬN NƠI"]),
        ],
        "two_col": False,
    },
    {   # slide 3 = page 5
        "title": "KO DC QUÊN ĐỒ DÙNG CẦN THIẾT",
        "tips": (
            "ĐÀ LẠT DẠO NÀY NẮNG MƯA\n"
            "THẤT THƯỜNG\n"
            "\n"
            "SÁNG SỚM VÀ BAN ĐÊM KHÁ\n"
            "LẠNH ĐÂU ĐÓ CHỈ 17°C\n"
            "\n"
            "NHIỆT ĐỘ TB TRONG NGÀY\n"
            "TẦM 23-25°C\n"
            "\n"
            "CHECK THỜI TIẾT TRƯỚC ĐỂ\n"
            "CBI QUẦN ÁO PHÙ HỢP"
        ),
        "btm_header": "CHECK LIST ĐỒ DÙNG CẦN THIẾT",
        "btm_lines": [
            "QUẦN ÁO ẤM, PHỤ KIỆN: KHĂN CHOÀNG,",
            "MŨ, TÚI, MẮT KÍNH, BOOTS,...",
            "ĐỒ CÁ NHÂN: KCN, THUỐC SAY XE, ĐAU",
            "BỤNG, TÚI NILONG ĐỰNG ĐỒ...",
            "SẠC ĐT, SẠC DỰ PHÒNG, TRIPOD,...",
            "CCCD, BLXM, 1 ÍT TIỀN MẶT,...",
        ],
        "two_col": False,
    },
    {   # slide 4 = page 6
        "title": "KO ĂN UỐNG KHI CHƯA HỎI GIÁ",
        "tips": (
            "KO RIÊNG GÌ Ở ĐÀ LẠT, TUI\n"
            "THẤY Ở ĐÂU CŨNG Z HẾT Á\n"
            "NÊN MNG PHẢI HỎI GIÁ CẢ\n"
            "TRƯỚC\n"
            "\n"
            "CHỌN QUÁN CÓ MENU RÕ\n"
            "RÀNG, ĐỌC KĨ REVIEW Ở GG\n"
            "MAPS, CÓ ĐÁNH GIÁ TỐT\n"
            "\n"
            "HẠN CHẾ ĂN UỐNG Ở CHỢ"
        ),
        "btm_header": "MÍ QUÁN MÀ TUI MUỐN RCM CHO MNG",
        "btm_left":  ["TRẠM NẮNG BBQ", "BẾP KHÓI", "OH MI VEGAN", "CƠM GÀ HẢI NAM"],
        "btm_right": ["BBQ GARDEN", "LẨU BÒ BA TOA", "BÚN BÒ HƯƠNG", "BÁNH CĂN VÂN"],
        "two_col": True,
    },
]


def _draw_bottom_2col(draw: ImageDraw.Draw, font, header: str,
                      left_items: list, right_items: list,
                      header_y: int = BTM_ITEM_Y - BTM_ITEM_SPACING - 10) -> None:
    """Draw 2-column venue list in white box."""
    f_header = _content_font(38)
    # Header with 👉
    _draw_bottom_header(draw, f_header, "👉 " + header, BTM_HEADER_X, header_y)

    for i, item in enumerate(left_items):
        y = BTM_ITEM_Y + i * BTM_ITEM_SPACING
        draw.text((BTM_ITEM_X_L, y), item, font=font, fill=BLACK)
    for i, item in enumerate(right_items):
        y = BTM_ITEM_Y + i * BTM_ITEM_SPACING
        draw.text((BTM_ITEM_X_R, y), item, font=font, fill=BLACK)


def _draw_bottom_header(draw: ImageDraw.Draw, font, text: str, x: int, y: int) -> None:
    draw.text((x, y), text, font=font, fill=BLACK)


def _draw_bottom_sections(draw: ImageDraw.Draw, font, sections: list) -> None:
    """Draw sections like {CHỖ Ở: [...], DI CHUYỂN: [...]}."""
    f_hdr = _content_font(40)
    y = BTM_ITEM_Y - BTM_ITEM_SPACING
    for (sec_title, items) in sections:
        # Section header with emoji prefix
        draw.text((BTM_HEADER_X, y), sec_title, font=f_hdr, fill=BLACK)
        y += BTM_ITEM_SPACING + 5
        for item in items:
            draw.text((BTM_ITEM_X_L, y), item, font=font, fill=BLACK)
            y += BTM_ITEM_SPACING
        y += 10


def _draw_bottom_list(draw: ImageDraw.Draw, font, header: str, lines: list,
                      header_emoji: str = "👉") -> None:
    """Single-column list with header."""
    f_hdr = _content_font(38)
    hdr_y = BTM_ITEM_Y - BTM_ITEM_SPACING - 10
    _draw_bottom_header(draw, f_hdr, f"{header_emoji} {header}", BTM_HEADER_X, hdr_y)
    for i, line in enumerate(lines):
        y = BTM_ITEM_Y + i * BTM_ITEM_SPACING
        draw.text((BTM_ITEM_X_L, y), line, font=font, fill=BLACK)


def render_tip(slide_idx: int, bg_path: str, content_path: str, out_path: str,
               venues_left: Optional[list] = None,
               venues_right: Optional[list] = None) -> str:
    """
    Render a tip slide (pages 2-6).
    slide_idx: 0-4 (maps to pages 2-6)
    bg_path: full-bleed background photo
    content_path: small photo shown on left side
    venues_left/right: override the default venue list for dynamic slides
    """
    slide = _SLIDES[slide_idx]

    # ── Background ──────────────────────────────────────────────────────────────
    bg = _load_bg(bg_path, blur=True, alpha=120)
    canvas = bg.convert("RGBA")

    # ── Content photo (left side) ────────────────────────────────────────────────
    if content_path:
        photo = _load_thumb(content_path, (PHOTO_W, PHOTO_H))
        canvas.paste(photo.convert("RGBA"), (PHOTO_X, PHOTO_Y))

    # ── White box (bottom) ───────────────────────────────────────────────────────
    white_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    white_draw = ImageDraw.Draw(white_layer)
    white_draw.rectangle([(0, WHITE_BOX_Y), (W, H)], fill=(255, 255, 255, 255))
    canvas.alpha_composite(white_layer)

    draw = ImageDraw.Draw(canvas)

    # ── Title (top, full width) ───────────────────────────────────────────────────
    font_title = _content_font(TITLE_SIZE)
    title = "❎ " + slide["title"]
    bbox = draw.textbbox((0, 0), title, font=font_title)
    tw = bbox[2] - bbox[0]
    tx = max(20, (W - tw) // 2)
    _stroke_text(draw, (tx, TITLE_Y), title, font_title,
                 fill=WHITE, stroke_w=5, stroke_fill=BLACK)

    # ── Tips text (right side) ────────────────────────────────────────────────────
    font_tips = _content_font(TIPS_SIZE)
    _multiline_stroke(draw, TIPS_X, TIPS_Y, slide["tips"], font_tips,
                      fill=WHITE, stroke_w=4, spacing=6)

    # ── Bottom section content ────────────────────────────────────────────────────
    font_btm = _content_font(36)

    if "btm_sections" in slide:
        _draw_bottom_sections(draw, font_btm, slide["btm_sections"])
    elif "btm_lines" in slide:
        _draw_bottom_list(draw, font_btm, slide["btm_header"], slide["btm_lines"])
    else:
        # Two-col or single-col venue list
        left = venues_left if venues_left is not None else slide.get("btm_left", [])
        right = venues_right if venues_right is not None else slide.get("btm_right", [])
        header = slide.get("btm_header", "")
        if slide.get("two_col") and right:
            _draw_bottom_2col(draw, font_btm, header, left, right)
        else:
            _draw_bottom_list(draw, font_btm, header, left)

    out = canvas.convert("RGB")
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    out.save(out_path, "PNG")
    return out_path
