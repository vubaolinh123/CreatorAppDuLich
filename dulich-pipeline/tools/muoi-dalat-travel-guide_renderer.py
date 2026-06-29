"""
muoi-dalat-travel-guide_renderer.py — Album renderer for the "Muối Đà Lạt Travel Guide" template.

Canvas: 1080 x 1280 px
Color palette:
    yellow   #F5C800
    white    #FFFFFF
    dark_bg  #1A1A1A
    dark_card #0D1B3E
    dark_card_alt #1A2B5A
    overlay_dark #2B2B2B
    accent_red #8B0000
    sky_blue #87CEEB

6 slides:
  1. render_cover         — full-bleed photo, gradient + dark overlay, bold yellow headline
  2. render_tip_venue_1   — heavy dark overlay, title + tip text + bullet list + 2 thumbnails
  3. render_tip_venue_2   — same base, two-column venue list, 3 thumbnails bottom row
  4. render_tip_venue_3   — same as slide 3, food/restaurant topic, inline price highlights
  5. render_tip_venue_4   — same as slide 3, café topic
  6. render_tip_venue_5   — activities topic, fewer bullets, larger thumbnails, optional hero inset
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from typing import Optional, List, Tuple
from PIL import Image, ImageDraw

from tools.render_utils import (
    load_bg,
    load_thumb,
    placeholder_thumb,
    pill,
    apply_bottom_gradient,
    save_slide,
    beviet_bold,
    noto,
    dancing,
    anton,
)

W, H = 1080, 1280

# ── Palette ───────────────────────────────────────────────────────────────────
YELLOW      = (245, 200, 0)
WHITE       = (255, 255, 255)
DARK_BG     = (26, 26, 26)
DARK_CARD   = (13, 27, 62)
DARK_CARD_ALT = (26, 43, 90)
OVERLAY_DARK = (43, 43, 43)
ACCENT_RED  = (139, 0, 0)
SKY_BLUE    = (135, 206, 235)
PIN_COLOR   = (245, 200, 0)   # yellow pin for this template

# ── Internal helpers ──────────────────────────────────────────────────────────

def _dark_overlay(canvas: Image.Image, alpha: int = 210) -> Image.Image:
    """Apply a flat dark RGBA rectangle over the full canvas and return new RGBA image."""
    ov = Image.new("RGBA", (W, H), (20, 20, 16, alpha))
    result = canvas.convert("RGBA")
    result.alpha_composite(ov)
    return result


def _title_text(draw: ImageDraw.ImageDraw, text: str, y: int,
                font, color: tuple = YELLOW,
                max_w: int = W - 80, center: bool = True) -> int:
    """Draw a single title string, optionally centered. Returns bottom y."""
    bb = draw.textbbox((0, 0), text, font=font)
    tw = bb[2] - bb[0]
    if center:
        x = (W - tw) // 2
    else:
        x = 60
    draw.text((x, y), text, font=font, fill=color)
    return y + (bb[3] - bb[1]) + 8


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font, max_w: int) -> List[str]:
    """Word-wrap text into lines that fit within max_w. Honors explicit newlines."""
    lines: List[str] = []
    for seg in text.split("\n"):
        words = seg.split()
        cur = ""
        for word in words:
            test = (cur + " " + word).strip()
            if draw.textlength(test, font=font) <= max_w:
                cur = test
            else:
                if cur:
                    lines.append(cur)
                cur = word
        lines.append(cur)
    return lines


def _draw_wrapped(draw: ImageDraw.ImageDraw, text: str, x: int, y: int,
                  font, color: tuple, max_w: int, line_h: Optional[int] = None) -> int:
    """Draw word-wrapped text. Returns bottom y."""
    lh = line_h or (font.size + 8)
    for line in _wrap_text(draw, text, font, max_w):
        draw.text((x, y), line, font=font, fill=color)
        y += lh
    return y


def _draw_section_label(draw: ImageDraw.ImageDraw, text: str, y: int,
                         font, x: int = 60) -> int:
    """Draw yellow section subheader. Returns bottom y."""
    draw.text((x, y), text, font=font, fill=YELLOW)
    bb = draw.textbbox((0, 0), text, font=font)
    return y + (bb[3] - bb[1]) + 12


def _draw_pin_prefix(draw: ImageDraw.ImageDraw, x: int, y: int, font, size: int = 18) -> int:
    """Draw a location pin character. Returns x after the pin."""
    pin_char = "●"  # filled circle as pin substitute
    draw.text((x, y), pin_char, font=font, fill=YELLOW)
    return x + int(draw.textlength(pin_char, font=font)) + 8


def _draw_bullet_list(draw: ImageDraw.ImageDraw, items: List[str],
                       x: int, y: int, font, color: tuple = WHITE,
                       pin_color: tuple = YELLOW, line_h: int = 48) -> int:
    """Draw bullet list with pin prefix. Returns final y below last item."""
    pin_font = noto(font.size)
    for item in items:
        pin_char = "  "
        pin_w = int(draw.textlength("  ", font=pin_font))
        draw.text((x, y), "●", font=pin_font, fill=pin_color)
        draw.text((x + pin_w + 4, y), item, font=font, fill=color)
        y += line_h
    return y


def _draw_two_col_list(draw: ImageDraw.ImageDraw, items: List[str],
                        x1: int, x2: int, y: int, font,
                        color: tuple = WHITE, pin_color: tuple = YELLOW,
                        line_h: int = 48) -> int:
    """Split items into two columns and draw in parallel. Returns max final y."""
    left  = items[: len(items) // 2 + len(items) % 2]
    right = items[len(items) // 2 + len(items) % 2:]
    y_left  = y
    y_right = y
    pin_char = "●"
    pin_w = int(draw.textlength(pin_char, font=font)) + 8
    for item in left:
        draw.text((x1, y_left), pin_char, font=font, fill=pin_color)
        draw.text((x1 + pin_w, y_left), item, font=font, fill=color)
        y_left += line_h
    for item in right:
        draw.text((x2, y_right), pin_char, font=font, fill=pin_color)
        draw.text((x2 + pin_w, y_right), item, font=font, fill=color)
        y_right += line_h
    return max(y_left, y_right)


def _draw_thumbnail_row(layer: Image.Image, paths: List[str], size: Tuple[int, int],
                         y_top: int, captions: List[str],
                         caption_font, caption_color: tuple = WHITE,
                         gap: int = 16) -> None:
    """Load and paste thumbnails in a centered row with captions below each."""
    draw = ImageDraw.Draw(layer)
    n = len(paths)
    if n == 0:
        return
    total_w = n * size[0] + (n - 1) * gap
    x_start = (W - total_w) // 2
    for i, path in enumerate(paths):
        px = x_start + i * (size[0] + gap)
        thumb = load_thumb(path, size)
        thumb_rgba = thumb.convert("RGBA")
        layer.paste(thumb_rgba, (px, y_top), thumb_rgba)
        if i < len(captions) and captions[i]:
            cap = captions[i]
            cw = int(draw.textlength(cap, font=caption_font))
            cx = px + (size[0] - cw) // 2
            cy = y_top + size[1] + 6
            draw.text((cx, cy), cap, font=caption_font, fill=caption_color)


def _price_segments(text: str) -> List[Tuple[str, bool]]:
    """Parse text for [price] tokens. Returns list of (chunk, is_price)."""
    import re
    parts = re.split(r"(\[[^\]]+\])", text)
    result = []
    for p in parts:
        if p.startswith("[") and p.endswith("]"):
            result.append((p[1:-1], True))
        else:
            result.append((p, False))
    return result


def _draw_price_inline(draw: ImageDraw.ImageDraw, x: int, y: int, text: str,
                        base_font, base_color: tuple,
                        price_font, price_color: tuple = YELLOW) -> Tuple[int, int]:
    """Draw text inline, rendering [price] tokens in price_color. Returns (end_x, end_y)."""
    segments = _price_segments(text)
    cx = x
    for chunk, is_price in segments:
        if not chunk:
            continue
        font  = price_font if is_price else base_font
        color = price_color if is_price else base_color
        draw.text((cx, y), chunk, font=font, fill=color)
        cx += int(draw.textlength(chunk, font=font)) + 2
    return cx, y


# ── Slide renderers ───────────────────────────────────────────────────────────

def render_cover(
    bg_path: str,
    out_path: str,
    title_lines: Optional[List[str]] = None,
    subtitle: str = "[ Hướng dẫn du lịch Đà Lạt ]",
    overlay_alpha: int = 89,
) -> str:
    """
    Slide 1 — Cover.
    Full-bleed photo with bottom gradient + dark overlay.
    Bold uppercase yellow headline at top-center, white bracketed subtitle below.
    """
    img = load_bg(bg_path, W, H)
    img_grad = apply_bottom_gradient(img, start_y_frac=0.4, max_alpha=200)
    canvas = img_grad.convert("RGBA")

    # Flat dark overlay for overall readability
    ov = Image.new("RGBA", (W, H), (0, 0, 0, overlay_alpha))
    canvas.alpha_composite(ov)

    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw  = ImageDraw.Draw(layer)

    font_title    = beviet_bold(72)
    font_subtitle = noto(32)

    lines = title_lines or ["KHÁM PHÁ", "ĐÀ LẠT", "TOÀN TẬP"]

    # Optional dark pill / badge behind title block
    total_title_h = len(lines) * (font_title.size + 12)
    pill_pad_x, pill_pad_y = 40, 20
    max_line_w = max(
        int(draw.textlength(l, font=font_title)) for l in lines
    )
    pill_w = max_line_w + pill_pad_x * 2
    pill_h = total_title_h + pill_pad_y * 2
    pill_x = (W - pill_w) // 2
    pill_y = 80
    draw.rounded_rectangle(
        [(pill_x, pill_y), (pill_x + pill_w, pill_y + pill_h)],
        radius=20,
        fill=(13, 27, 62, 200),
    )

    # Draw title lines: first word yellow, rest white
    y = pill_y + pill_pad_y
    for line in lines:
        words = line.split()
        x_cursor = pill_x + pill_pad_x
        line_w = int(draw.textlength(line, font=font_title))
        x_cursor = (W - line_w) // 2
        for wi, word in enumerate(words):
            color = YELLOW if wi == 0 else WHITE
            draw.text((x_cursor, y), word, font=font_title, fill=color)
            x_cursor += int(draw.textlength(word + " ", font=font_title))
        y += font_title.size + 12

    # Subtitle in white below the pill
    sub_y = pill_y + pill_h + 24
    sub_w = int(draw.textlength(subtitle, font=font_subtitle))
    draw.text(((W - sub_w) // 2, sub_y), subtitle, font=font_subtitle, fill=WHITE)

    return save_slide(canvas, layer, out_path)


def render_tip_venue_1(
    bg_path: str,
    out_path: str,
    title: str = "LƯU TRÚ Ở ĐÂU?",
    tip_text: str = "Đặt phòng sớm để có giá tốt, đặc biệt dịp lễ và cuối tuần. Nên chọn homestay khu trung tâm để tiện đi lại.",
    section_label: str = "MẤY CHỖ LƯU TRÚ",
    venues: Optional[List[str]] = None,
    thumb_paths: Optional[List[str]] = None,
    thumb_captions: Optional[List[str]] = None,
) -> str:
    """
    Slide 2 — Tip + venue list + 2 thumbnails bottom-right.
    Heavy dark overlay, yellow title, white body paragraph, yellow section subheader,
    single-column bullet list with pin prefix, 2 photo thumbnails bottom area.
    """
    img = load_bg(bg_path, W, H)
    img_grad = apply_bottom_gradient(img, start_y_frac=0.3, max_alpha=210)
    canvas = _dark_overlay(img_grad, alpha=210)

    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw  = ImageDraw.Draw(layer)

    font_title   = beviet_bold(68)
    font_body    = noto(30)
    font_section = beviet_bold(40)
    font_bullet  = noto(30)
    font_caption = noto(24)

    pad_x    = 60
    max_text = W - pad_x * 2

    # Title
    y = 80
    bb = draw.textbbox((0, 0), title, font=font_title)
    tw = bb[2] - bb[0]
    draw.text(((W - tw) // 2, y), title, font=font_title, fill=YELLOW)
    y += (bb[3] - bb[1]) + 28

    # Tip body
    y = _draw_wrapped(draw, tip_text, pad_x, y, font_body, WHITE, max_text, line_h=font_body.size + 10)
    y += 28

    # Section label
    y = _draw_section_label(draw, section_label, y, font_section, x=pad_x)
    y += 8

    # Bullet list
    venue_list = venues or ["Khách sạn A", "Homestay B", "Villa C"]
    thumb_size = (240, 160)
    thumb_row_h = thumb_size[1] + 40  # thumbnail + caption height
    list_bottom_limit = H - thumb_row_h - 40
    visible_venues = []
    cur_y = y
    for item in venue_list:
        if cur_y + font_bullet.size + 12 > list_bottom_limit:
            break
        visible_venues.append(item)
        cur_y += font_bullet.size + 12 + (font_bullet.size + 12 - font_bullet.size)

    y = _draw_bullet_list(draw, visible_venues, pad_x, y, font_bullet,
                          color=WHITE, pin_color=YELLOW, line_h=font_bullet.size + 14)
    y += 16

    # 2 thumbnails side by side at bottom-right
    paths = (thumb_paths or ["", ""])[:2]
    captions = (thumb_captions or ["", ""])[:2]
    thumb_w, thumb_h = thumb_size
    gap = 20
    total_w = 2 * thumb_w + gap
    x_start = W - total_w - pad_x
    thumb_y = max(y + 20, H - thumb_h - 60)

    for i, tp in enumerate(paths):
        px = x_start + i * (thumb_w + gap)
        thumb = load_thumb(tp, (thumb_w, thumb_h))
        thumb_rgba = thumb.convert("RGBA")
        layer.paste(thumb_rgba, (px, thumb_y), thumb_rgba)
        if i < len(captions) and captions[i]:
            cw = int(draw.textlength(captions[i], font=font_caption))
            cx = px + (thumb_w - cw) // 2
            draw.text((cx, thumb_y + thumb_h + 6), captions[i],
                      font=font_caption, fill=WHITE)

    return save_slide(canvas, layer, out_path)


def render_tip_venue_2(
    bg_path: str,
    out_path: str,
    title: str = "ĂN Ở ĐÂU NGON?",
    tip_text: str = "Đà Lạt có nhiều quán ăn ngon mà không đắt. Tránh xa khu chợ Đêm nếu muốn ăn no giá phải chăng.",
    section_label: str = "QUÁN ĂN GỢI Ý",
    venues: Optional[List[str]] = None,
    thumb_paths: Optional[List[str]] = None,
    thumb_captions: Optional[List[str]] = None,
) -> str:
    """
    Slide 3 — Two-column venue list + 3 thumbnail row at bottom.
    """
    img = load_bg(bg_path, W, H)
    img_grad = apply_bottom_gradient(img, start_y_frac=0.3, max_alpha=210)
    canvas = _dark_overlay(img_grad, alpha=210)

    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw  = ImageDraw.Draw(layer)

    font_title   = beviet_bold(68)
    font_body    = noto(30)
    font_section = beviet_bold(40)
    font_bullet  = noto(28)
    font_caption = noto(24)

    pad_x    = 60
    max_text = W - pad_x * 2

    # Title
    y = 80
    bb = draw.textbbox((0, 0), title, font=font_title)
    tw = bb[2] - bb[0]
    draw.text(((W - tw) // 2, y), title, font=font_title, fill=YELLOW)
    y += (bb[3] - bb[1]) + 28

    # Tip body
    y = _draw_wrapped(draw, tip_text, pad_x, y, font_body, WHITE, max_text, line_h=font_body.size + 10)
    y += 28

    # Section label
    y = _draw_section_label(draw, section_label, y, font_section, x=pad_x)
    y += 8

    # Two-column venue list
    venue_list = venues or ["Quán A", "Quán B", "Quán C", "Quán D", "Quán E", "Quán F"]
    thumb_size = (220, 150)
    thumb_row_h = thumb_size[1] + 44
    col_mid = W // 2
    x1 = pad_x
    x2 = col_mid + 20

    y = _draw_two_col_list(draw, venue_list, x1, x2, y, font_bullet,
                           color=WHITE, pin_color=YELLOW,
                           line_h=font_bullet.size + 14)
    y += 20

    # 3 thumbnails row at bottom
    paths    = (thumb_paths    or ["", "", ""])[:3]
    captions = (thumb_captions or ["", "", ""])[:3]
    _draw_thumbnail_row(layer, paths, thumb_size, max(y, H - thumb_size[1] - 60),
                        captions, font_caption, caption_color=WHITE, gap=14)

    return save_slide(canvas, layer, out_path)


def render_tip_venue_3(
    bg_path: str,
    out_path: str,
    title: str = "ĂN GÌ Ở ĐÀ LẠT?",
    tip_text: str = "Đặc sản Đà Lạt rất đa dạng. Nhớ thử bánh mì xíu mại, bơ, dâu tây và các món nướng chợ Đêm.",
    section_label: str = "QUÁN ĂN ĐẶC SẢN",
    venues: Optional[List[str]] = None,
    thumb_paths: Optional[List[str]] = None,
    thumb_captions: Optional[List[str]] = None,
    price_note: str = "",
) -> str:
    """
    Slide 4 — Food topic. Same layout as slide 3 with inline price highlights.
    Wrap [price] in the tip_text to render prices in yellow.
    """
    img = load_bg(bg_path, W, H)
    img_grad = apply_bottom_gradient(img, start_y_frac=0.3, max_alpha=210)
    canvas = _dark_overlay(img_grad, alpha=210)

    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw  = ImageDraw.Draw(layer)

    font_title   = beviet_bold(68)
    font_body    = noto(30)
    font_section = beviet_bold(40)
    font_bullet  = noto(28)
    font_caption = noto(24)
    font_price   = beviet_bold(28)

    pad_x    = 60
    max_text = W - pad_x * 2

    # Title
    y = 80
    bb = draw.textbbox((0, 0), title, font=font_title)
    tw = bb[2] - bb[0]
    draw.text(((W - tw) // 2, y), title, font=font_title, fill=YELLOW)
    y += (bb[3] - bb[1]) + 28

    # Tip body — split on price tokens to render inline
    segs = _price_segments(tip_text)
    line_h = font_body.size + 10
    # Simple multi-line: render segments without inline-wrap complexity
    current_line = ""
    for chunk, is_price in segs:
        if not chunk:
            continue
        if is_price:
            if current_line:
                _draw_wrapped(draw, current_line, pad_x, y, font_body, WHITE, max_text, line_h=line_h)
                y += line_h
                current_line = ""
            draw.text((pad_x, y), chunk, font=font_price, fill=YELLOW)
            y += line_h
        else:
            current_line += chunk
    if current_line:
        y = _draw_wrapped(draw, current_line.strip(), pad_x, y, font_body, WHITE, max_text, line_h=line_h)
    y += 28

    # Section label
    y = _draw_section_label(draw, section_label, y, font_section, x=pad_x)
    y += 8

    # Two-column venue list
    venue_list = venues or ["Quán Ăn A", "Quán Ăn B", "Quán Ăn C", "Quán Ăn D"]
    thumb_size = (220, 150)
    thumb_row_h = thumb_size[1] + 44
    x1 = pad_x
    x2 = W // 2 + 20

    y = _draw_two_col_list(draw, venue_list, x1, x2, y, font_bullet,
                           color=WHITE, pin_color=YELLOW,
                           line_h=font_bullet.size + 14)

    # Optional price note line
    if price_note:
        y += 12
        draw.text((pad_x, y), price_note, font=font_price, fill=YELLOW)
        y += font_price.size + 12

    y += 12

    # 3 thumbnails row at bottom
    paths    = (thumb_paths    or ["", "", ""])[:3]
    captions = (thumb_captions or ["", "", ""])[:3]
    _draw_thumbnail_row(layer, paths, thumb_size, max(y, H - thumb_size[1] - 60),
                        captions, font_caption, caption_color=WHITE, gap=14)

    return save_slide(canvas, layer, out_path)


def render_tip_venue_4(
    bg_path: str,
    out_path: str,
    title: str = "CAFE VIEW ĐẸP",
    tip_text: str = "Đà Lạt có hàng trăm quán cà phê view đẹp. Đến sớm để chọn bàn đẹp và tránh đông.",
    section_label: str = "QUÁN CÀ PHÊ GỢI Ý",
    venues: Optional[List[str]] = None,
    thumb_paths: Optional[List[str]] = None,
    thumb_captions: Optional[List[str]] = None,
) -> str:
    """
    Slide 5 — Café topic. Identical layout to slides 3-4.
    """
    img = load_bg(bg_path, W, H)
    img_grad = apply_bottom_gradient(img, start_y_frac=0.3, max_alpha=210)
    canvas = _dark_overlay(img_grad, alpha=210)

    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw  = ImageDraw.Draw(layer)

    font_title   = beviet_bold(68)
    font_body    = noto(30)
    font_section = beviet_bold(40)
    font_bullet  = noto(28)
    font_caption = noto(24)

    pad_x    = 60
    max_text = W - pad_x * 2

    y = 80
    bb = draw.textbbox((0, 0), title, font=font_title)
    tw = bb[2] - bb[0]
    draw.text(((W - tw) // 2, y), title, font=font_title, fill=YELLOW)
    y += (bb[3] - bb[1]) + 28

    y = _draw_wrapped(draw, tip_text, pad_x, y, font_body, WHITE, max_text, line_h=font_body.size + 10)
    y += 28

    y = _draw_section_label(draw, section_label, y, font_section, x=pad_x)
    y += 8

    venue_list = venues or ["Cafe A", "Cafe B", "Cafe C", "Cafe D", "Cafe E", "Cafe F"]
    thumb_size = (220, 150)
    x1 = pad_x
    x2 = W // 2 + 20

    y = _draw_two_col_list(draw, venue_list, x1, x2, y, font_bullet,
                           color=WHITE, pin_color=YELLOW,
                           line_h=font_bullet.size + 14)
    y += 20

    paths    = (thumb_paths    or ["", "", ""])[:3]
    captions = (thumb_captions or ["", "", ""])[:3]
    _draw_thumbnail_row(layer, paths, thumb_size, max(y, H - thumb_size[1] - 60),
                        captions, font_caption, caption_color=WHITE, gap=14)

    return save_slide(canvas, layer, out_path)


def render_tip_venue_5(
    bg_path: str,
    out_path: str,
    title: str = "VUI CHƠI GÌ?",
    tip_text: str = "Đà Lạt có rất nhiều hoạt động ngoài trời thú vị — từ trekking, chèo SUP đến cắm trại.",
    section_label: str = "ĐỊA ĐIỂM HOẠT ĐỘNG",
    venues: Optional[List[str]] = None,
    thumb_paths: Optional[List[str]] = None,
    thumb_captions: Optional[List[str]] = None,
    hero_inset_path: str = "",
    hero_inset_caption: str = "",
) -> str:
    """
    Slide 6 — Activities. Fewer text bullets so thumbnails can be larger.
    Optional hero inset thumbnail at top-right.
    Single-column bullets when count <= 4.
    """
    img = load_bg(bg_path, W, H)
    img_grad = apply_bottom_gradient(img, start_y_frac=0.3, max_alpha=210)
    canvas = _dark_overlay(img_grad, alpha=210)

    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw  = ImageDraw.Draw(layer)

    font_title   = beviet_bold(68)
    font_body    = noto(30)
    font_section = beviet_bold(40)
    font_bullet  = noto(30)
    font_caption = noto(24)

    pad_x    = 60
    max_text = W - pad_x * 2

    # Optional hero inset top-right
    if hero_inset_path:
        inset_size = (320, 200)
        inset_x = W - inset_size[0] - 32
        inset_y = 100
        inset = load_thumb(hero_inset_path, inset_size)
        inset_rgba = inset.convert("RGBA")
        layer.paste(inset_rgba, (inset_x, inset_y), inset_rgba)
        if hero_inset_caption:
            cw = int(draw.textlength(hero_inset_caption, font=font_caption))
            cx = inset_x + (inset_size[0] - cw) // 2
            draw.text((cx, inset_y + inset_size[1] + 6),
                      hero_inset_caption, font=font_caption, fill=WHITE)
        title_max_w = inset_x - pad_x - 20
    else:
        title_max_w = W - pad_x * 2

    # Title — left-aligned if inset present, else centered
    y = 80
    if hero_inset_path:
        draw.text((pad_x, y), title, font=font_title, fill=YELLOW)
        bb = draw.textbbox((0, 0), title, font=font_title)
        y += (bb[3] - bb[1]) + 28
    else:
        bb = draw.textbbox((0, 0), title, font=font_title)
        tw = bb[2] - bb[0]
        draw.text(((W - tw) // 2, y), title, font=font_title, fill=YELLOW)
        y += (bb[3] - bb[1]) + 28

    # Tip body
    y = _draw_wrapped(draw, tip_text, pad_x, y, font_body, WHITE,
                      title_max_w if hero_inset_path else max_text,
                      line_h=font_body.size + 10)
    y += 28

    # Section label
    y = _draw_section_label(draw, section_label, y, font_section, x=pad_x)
    y += 8

    # Single-column bullets for activities (short list)
    venue_list = venues or ["Trekking Langbiang", "Chèo SUP hồ Tuyền Lâm", "Cắm trại"]
    thumb_size = (300, 200)  # larger thumbnails for activities
    thumb_row_h = thumb_size[1] + 44

    # Clamp list to avoid overlapping thumbnails
    max_bullets = 4
    visible = venue_list[:max_bullets]

    y = _draw_bullet_list(draw, visible, pad_x, y, font_bullet,
                          color=WHITE, pin_color=YELLOW, line_h=font_bullet.size + 16)
    y += 20

    # 3 large thumbnails bottom half
    paths    = (thumb_paths    or ["", "", ""])[:3]
    captions = (thumb_captions or ["", "", ""])[:3]
    thumb_y  = max(y, H - thumb_size[1] - 60)
    _draw_thumbnail_row(layer, paths, thumb_size, thumb_y,
                        captions, font_caption, caption_color=WHITE, gap=12)

    return save_slide(canvas, layer, out_path)
