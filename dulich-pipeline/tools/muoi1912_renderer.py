# -*- coding: utf-8 -*-
"""
muoi1912_renderer.py — Template Muốihien1: travel advice guide, 6 slides, 1080x1390.
Slide 0: dark gradient cover + bold hook text.
Slides 1-4: WHITE background infographic — header bar, tips, right photo, venue list, 3 bottom photos.
Slide 5: full-bleed photo CTA.
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from PIL import Image, ImageDraw
from tools.render_utils import (
    load_bg, load_thumb, rounded_thumb,
    anton, noto, beviet_bold,
    draw_pin_icon, apply_bottom_gradient, save_slide
)

W, H = 1080, 1390
DARK_HEADER = (20, 20, 45)
YELLOW = (245, 208, 32)


def _make_gradient_overlay():
    """Semi-transparent dark gradient for compositing over a photo (cover)."""
    img = Image.new("RGBA", (1, H))
    top = (18, 18, 28)
    bot = (40, 40, 50)
    for y in range(H):
        t = y / (H - 1)
        r = int(top[0] * (1 - t) + bot[0] * t)
        g = int(top[1] * (1 - t) + bot[1] * t)
        b = int(top[2] * (1 - t) + bot[2] * t)
        a = int(188 * (1 - t) + 165 * t)
        img.putpixel((0, y), (r, g, b, a))
    return img.resize((W, H), Image.NEAREST)


HOOK_LINES = [
    ("LỜI KHUYÊN DÀNH CHO", "NHỮNG AI SẮP ĐI ĐÀ LẠT", "ĐÓN GIÁNG SINH"),
    ("LỜI KHUYÊN DÀNH CHO", "NHỮNG AI SẮP ĐI ĐÀ LẠT", ""),
    ("AI ĐANG PLAN ĐI ĐÀ LẠT", "ĐỌC CÁI NÀY TRƯỚC ĐÃ", ""),
    ("NHỮNG AI MÊ ĐÀ LẠT", "GHI VÀO MÀ ĐI NHA", ""),
]

GUIDE_SECTIONS = [
    {
        "title":         "ĐẶT PHÒNG SỚM KẺO HỐI HẬN",
        "category":      "khách sạn",
        "section_label": "GỢI Ý CHỖ LƯU TRÚ",
        "bullets": [
            "• Mùa cao điểm (lễ, Tết, cuối tuần) mà không đặt phòng trước rất dễ bị chặt chém",
            "• Nên đặt phòng trước 1-3 tuần, chọn chỗ uy tín, xem kỹ đánh giá trước khi cọc",
            "• Có người quen ở địa phương thì nhờ hỏi giúp để được giá tốt hơn",
            "• Cân nhắc Airbnb — nhiều chỗ rẻ và riêng tư hơn khách sạn",
            "• Tránh đặt qua trang mạng xã hội không có đánh giá",
        ],
    },
    {
        "title":         "ĐỪNG QUÁ TIN VÀO ẢNH TRÊN MẠNG",
        "category":      "điểm checkin",
        "section_label": "3 ĐIỂM CHECK-IN DỄ VỠ MỘNG",
        "bullets": [
            "• Thực tế nhiều khi không giống trên ảnh — nên xem thêm nhiều nguồn",
            "• Nhiều điểm hot trên TikTok nhờ góc chụp nên nhìn lung linh hơn thực tế",
            "• Nên xem review từ nhiều nguồn, có video thực tế thì càng tốt",
            "• Tránh leo Langbiang vào trưa nắng — đi bộ rất mệt",
            "• Vườn hoa thành phố đẹp nhất lúc sáng sớm 6-7h",
        ],
    },
    {
        "title":         "CẨN THẬN KHI ĂN UỐNG NGOÀI CHỢ",
        "category":      "quán ăn",
        "section_label": "QUÁN NGON NÊN THỬ",
        "bullets": [
            "• Ăn uống ở khu chợ tiện nhưng cẩn thận kẻo bị chặt chém",
            "• Nên đọc review trên Google Maps và hỏi giá trước khi gọi món",
            "• Đi chợ khi đã no bụng — tránh bị dụ mua đồ đắt",
            "• Bánh mì Đà Lạt buổi sáng vừa ngon vừa rẻ",
            "• Thử món sườn cay — đặc sản không nên bỏ qua",
        ],
    },
]


def render_cover(hook: tuple, bg_path: str, out_path: str) -> str:
    canvas = load_bg(bg_path, W, H).convert("RGBA")
    canvas.alpha_composite(_make_gradient_overlay())
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    line1, line2, line3 = hook
    font1 = anton(68)
    font2 = anton(68)
    font3 = anton(50)

    y = 160
    for text, font, color in [
        (line1, font1, (255, 255, 255)),
        (line2, font2, YELLOW),
        (line3, font3, YELLOW),
    ]:
        if not text:
            continue
        tw = int(draw.textlength(text, font=font))
        draw.text(((W - tw) // 2, y), text, font=font, fill=color)
        y += font.size + 14

    font_hdl = noto(22)
    hw = int(draw.textlength("@thamhiemdalat", font=font_hdl))
    draw.text(((W - hw) // 2, H - 70), "@thamhiemdalat", font=font_hdl, fill=(180, 180, 180))

    return save_slide(canvas, layer, out_path)


def _wrap_text(text: str, font, max_w: int, draw: ImageDraw.Draw) -> list[str]:
    words = text.split(" ")
    lines, current = [], ""
    for word in words:
        test = current + (" " if current else "") + word
        if draw.textlength(test, font=font) <= max_w:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [text]


def _draw_venue_dark(draw: ImageDraw.Draw, x: int, y: int, venue: dict) -> int:
    """Single venue row for dark background — white text."""
    font_n = beviet_bold(24)
    font_a = noto(20)
    name = venue.get("name", "")
    addr = venue.get("address", "").split(",")[0].strip()
    draw.text((x, y), f"• {name}", font=font_n, fill=(255, 255, 255))
    y += font_n.size + 4
    draw_pin_icon(draw, x + 4, y + 2, size=11, color=(232, 80, 80))
    draw.text((x + 20, y), addr, font=font_a, fill=(200, 210, 230))
    y += font_a.size + 14
    return y


def render_guide_slide(sec: dict, venues: list, venue_imgs: list,
                       bg_path: str, out_path: str) -> str:
    """Dark photo background guide slide — overlay layer + text on top."""
    img = load_bg(bg_path, W, H)
    canvas = img.convert("RGBA")
    overlay = Image.new("RGBA", (W, H), (8, 8, 22, 175))
    canvas.alpha_composite(overlay)

    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    # ── Title ──
    font_hdr = anton(48)
    title = sec["title"]
    tw = int(draw.textlength(title, font=font_hdr))
    draw.text(((W - tw) // 2, 48), title, font=font_hdr, fill=YELLOW)

    # ── Right venue photo ──
    PHOTO_X, PHOTO_Y, PHOTO_W, PHOTO_H = 615, 126, 430, 440
    valid_imgs = [img for img in venue_imgs if img]
    first_img = valid_imgs[0] if valid_imgs else None
    if first_img:
        thumb = load_thumb(first_img, (PHOTO_W, PHOTO_H))
        thumb_r = rounded_thumb(thumb, radius=18)
        canvas.alpha_composite(thumb_r.convert("RGBA"), dest=(PHOTO_X, PHOTO_Y))

    # ── Tip bullets (left side) ──
    font_tip = noto(26)
    MAX_TIP_W = 555  # stay clear of right photo at x=615
    ty = 128
    for bullet in sec["bullets"][:4]:
        lines = _wrap_text(bullet, font_tip, MAX_TIP_W, draw)
        for line in lines:
            draw.text((38, ty), line, font=font_tip, fill=(240, 240, 255))
            ty += font_tip.size + 8
        ty += 6

    # ── Section label pill ──
    LABEL_Y = 595
    label = sec.get("section_label", "GỢI Ý CÁC ĐỊA ĐIỂM")
    font_lbl = beviet_bold(28)
    lw = int(draw.textlength(label, font=font_lbl))
    pill_w = lw + 50
    pill_x = (W - pill_w) // 2
    draw.rounded_rectangle([(pill_x, LABEL_Y), (pill_x + pill_w, LABEL_Y + 56)],
                            radius=14, fill=(*DARK_HEADER, 250))
    draw.text(((W - lw) // 2, LABEL_Y + 13), label, font=font_lbl, fill=YELLOW)

    # ── 2-column venue list ──
    COL_A_X, COL_B_X, LIST_Y = 40, 560, 665
    ya, yb = LIST_Y, LIST_Y
    for i, v in enumerate(venues[:6]):
        if i < 3:
            ya = _draw_venue_dark(draw, COL_A_X, ya, v)
        else:
            yb = _draw_venue_dark(draw, COL_B_X, yb, v)

    # ── Bottom 3 venue photos ──
    BOTTOM_Y = 880
    PW, PH = 300, 265
    xs = [30, 393, 756]
    bottom_imgs = [img for img in venue_imgs[1:] if img]
    if not bottom_imgs:
        bottom_imgs = valid_imgs
    padded = [bottom_imgs[i % len(bottom_imgs)] for i in range(3)] if bottom_imgs else []
    for j, (xi, img_path) in enumerate(zip(xs, padded)):
        thumb = load_thumb(img_path, (PW, PH))
        thumb_r = rounded_thumb(thumb, radius=14)
        canvas.alpha_composite(thumb_r.convert("RGBA"), dest=(xi, BOTTOM_Y))

    # ── Photo captions ──
    font_cap = noto(20)
    CAPTION_Y = BOTTOM_Y + PH + 10
    cap_venues = (venues[1:4] if len(venues) > 1 else venues[:1] * 3)[:3]
    for j, v in enumerate(cap_venues):
        xi = xs[j]
        cap_name = v.get("name", "")[:22]
        cw = int(draw.textlength(cap_name, font=font_cap))
        cx = xi + (PW - cw) // 2
        draw_pin_icon(draw, cx - 16, CAPTION_Y + 2, size=10, color=(232, 80, 80))
        draw.text((cx, CAPTION_Y), cap_name, font=font_cap, fill=(220, 220, 235))

    # ── Handle ──
    font_hdl = noto(20)
    hw = int(draw.textlength("@thamhiemdalat", font=font_hdl))
    draw.text(((W - hw) // 2, H - 55), "@thamhiemdalat", font=font_hdl, fill=(160, 170, 200))

    canvas.alpha_composite(layer)
    rgb = canvas.convert("RGB")
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    rgb.save(out_path, "PNG")
    return out_path


def render_cta_slide(bg_path: str, out_path: str) -> str:
    img = load_bg(bg_path, W, H)
    img_grad = apply_bottom_gradient(img, start_y_frac=0.4, max_alpha=170)
    canvas = img_grad
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    font_cta = anton(52)
    cta = "Save lại để không bỏ lỡ nhé!"
    cw = int(draw.textlength(cta, font=font_cta))
    draw.text(((W - cw) // 2, H // 2 - 30), cta, font=font_cta, fill=(255, 255, 255))

    font_hdl = noto(24)
    hw = int(draw.textlength("@thamhiemdalat", font=font_hdl))
    draw.text(((W - hw) // 2, H - 70), "@thamhiemdalat", font=font_hdl, fill=(200, 200, 200))

    return save_slide(canvas, layer, out_path)
