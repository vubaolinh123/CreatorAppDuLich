# -*- coding: utf-8 -*-
"""
muoi1311_renderer.py — Template Muối 13/11: venue list Local vs hot-hit.
Slide 0: dark gradient cover — "Đi Đà Lạt theo hệ / Local hay hohit".
Slides 1-N: dark bg (near-black) — title + Local section + hot-hit section.
Canvas: 1080 × 1390px.
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from PIL import Image, ImageDraw
from tools.render_utils import (
    load_bg, dancing, anton, noto, beviet_bold,
    apply_bottom_gradient, save_slide
)

W, H = 1080, 1390
DARK_BG = (8, 8, 22)        # near-black navy
YELLOW = (245, 208, 32)
ORANGE = (255, 160, 30)


def _make_gradient_overlay():
    """Semi-transparent dark gradient for compositing over a photo (cover)."""
    img = Image.new("RGBA", (1, H))
    top = (8, 8, 22)
    bot = (30, 30, 40)
    for y in range(H):
        t = y / (H - 1)
        r = int(top[0] * (1 - t) + bot[0] * t)
        g = int(top[1] * (1 - t) + bot[1] * t)
        b = int(top[2] * (1 - t) + bot[2] * t)
        a = int(192 * (1 - t) + 170 * t)
        img.putpixel((0, y), (r, g, b, a))
    return img.resize((W, H), Image.NEAREST)


def render_cover(bg_path: str, out_path: str) -> str:
    canvas = load_bg(bg_path, W, H).convert("RGBA")
    canvas.alpha_composite(_make_gradient_overlay())
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    # "Đi Đà Lạt theo hệ" in dark rounded rect
    font_title = dancing(88)
    title = "Đi Đà Lạt theo hệ"
    tw = int(draw.textlength(title, font=font_title))
    tx = (W - tw) // 2
    ty = 140
    pad = 20
    draw.rounded_rectangle(
        [(tx - pad, ty - 14), (tx + tw + pad, ty + font_title.size + 14)],
        radius=22, fill=(12, 12, 30, 240)
    )
    draw.text((tx, ty), title, font=font_title, fill=(255, 255, 255))

    # "Local hay hohit"
    font_sub = dancing(96)
    font_hay = dancing(96)
    hay = "hay "
    local = "Local "
    hohit = "hohit"
    lw = int(draw.textlength(local, font=font_sub))
    hw = int(draw.textlength(hay, font=font_hay))
    hiw = int(draw.textlength(hohit, font=font_sub))
    total_w = lw + hw + hiw
    sx = (W - total_w) // 2
    sy = ty + font_title.size + 28
    draw.text((sx, sy), local, font=font_sub, fill=(255, 255, 255))
    draw.text((sx + lw, sy), hay, font=font_hay, fill=YELLOW)
    draw.text((sx + lw + hw, sy), hohit, font=font_sub, fill=(255, 255, 255))

    # Subtitle
    font_sm = noto(24)
    sub = "[ Kết hợp địa điểm local và hot hit cho chuyến đi thêm nhiều trải nghiệm ]"
    sw = int(draw.textlength(sub, font=font_sm))
    draw.text(((W - sw) // 2, sy + font_sub.size + 20), sub, font=font_sm,
              fill=(180, 180, 190))

    return save_slide(canvas, layer, out_path)


def render_list_slide(title: str, venues_local: list, venues_hothit: list,
                      bg_path: str, out_path: str) -> str:
    """Photo bg + dark purple boxed containers per section. No full-slide overlay."""
    img = load_bg(bg_path, W, H)
    canvas = img.convert("RGBA")
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 70))
    canvas.alpha_composite(overlay)

    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    BOX_COLOR = (28, 14, 62, 238)   # dark purple, semi-transparent
    BOX_X1, BOX_X2 = 38, W - 38

    font_title  = dancing(70)
    font_label  = dancing(56)
    font_vname  = beviet_bold(26)
    font_vaddr  = noto(22)

    ROW_H = font_vname.size + 2 + font_vaddr.size + 18   # ~68px per venue row
    LABEL_H = font_label.size + 30                        # label + vertical padding

    def _draw_box_section(label_text: str, label_color: tuple,
                          venues: list, box_y: int) -> int:
        n = len(venues)
        box_h = LABEL_H + n * ROW_H + 24
        draw.rounded_rectangle(
            [(BOX_X1, box_y), (BOX_X2, box_y + box_h)],
            radius=22, fill=BOX_COLOR
        )
        lw = int(draw.textlength(label_text, font=font_label))
        draw.text(((W - lw) // 2, box_y + 12), label_text, font=font_label, fill=label_color)
        vy = box_y + LABEL_H + 4
        for v in venues:
            name = v.get("name", "")
            addr = v.get("address", "")
            if len(addr) > 52:
                addr = addr.split(",")[0]
            draw.text((BOX_X1 + 22, vy), f"• {name}", font=font_vname, fill=(255, 255, 255))
            vy += font_vname.size + 2
            draw.text((BOX_X1 + 36, vy), addr, font=font_vaddr, fill=(195, 208, 230))
            vy += font_vaddr.size + 18
        return box_y + box_h

    # ── Title box ──
    TITLE_PAD = 18
    title_h = font_title.size + TITLE_PAD * 2
    draw.rounded_rectangle(
        [(BOX_X1, 50), (BOX_X2, 50 + title_h)],
        radius=22, fill=BOX_COLOR
    )
    tw = int(draw.textlength(title, font=font_title))
    draw.text(((W - tw) // 2, 50 + TITLE_PAD), title, font=font_title, fill=(255, 255, 255))

    # ── Local section ──
    local_box_y = 50 + title_h + 28
    local_box_end = _draw_box_section("Local", YELLOW, venues_local, local_box_y)

    # ── hot-hit section ──
    if venues_hothit:
        _draw_box_section("hot-hit", ORANGE, venues_hothit, local_box_end + 26)

    return save_slide(canvas, layer, out_path)


def render_cta_slide(bg_path: str, out_path: str) -> str:
    img = load_bg(bg_path, W, H)
    img_grad = apply_bottom_gradient(img, start_y_frac=0.4, max_alpha=170)
    canvas = img_grad
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    font_cta = anton(52)
    cta = "Save lại để dùng nhé!"
    cw = int(draw.textlength(cta, font=font_cta))
    draw.text(((W - cw) // 2, H // 2 - 26), cta, font=font_cta, fill=(255, 255, 255))

    font_hdl = noto(24)
    hw = int(draw.textlength("@thamhiemdalat", font=font_hdl))
    draw.text(((W - hw) // 2, H - 70), "@thamhiemdalat", font=font_hdl, fill=(200, 200, 200))

    return save_slide(canvas, layer, out_path)
