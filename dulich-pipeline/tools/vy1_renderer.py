"""
myle115_renderer.py — Template Myle115: 2x2 grid venue album, 1080x1280.
7-slide format matching Myle115 reference images.
  - render_cover: full-bg + handle pill + orange badge + bold title + subtitle
  - render_grid_slide: 2x2 venue thumbnails + category label at junction
  - render_food_list_slide: dark-overlay bg + bullet list + 4 bottom thumbnails
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from PIL import Image, ImageDraw
from tools.render_utils import (
    load_bg, load_thumb, pill,
    beviet_bold, noto, dancing, anton,
    apply_bottom_gradient, save_slide,
)

W, H = 1080, 1280
GRID_Y = H // 2  # 640 — dividing line between top/bottom rows

HOOK_HEADLINES = [
    "Đi hết những điểm này\nở Đà Lạt",
    "Những nơi không thể bỏ qua\nkhi đến Đà Lạt",
    "Check-in đủ chỗ này\nmới gọi là đã đến Đà Lạt",
    "Đà Lạt có gì hay?\nĐây rồi, lưu lại đi!",
    "Bỏ túi ngay\ncác địa điểm Đà Lạt xịn nhất",
]


def _shadow_text(draw, x, y, text, font, color, shadow=(0, 0, 0, 160), offset=2):
    draw.text((x + offset, y + offset), text, font=font, fill=shadow)
    draw.text((x, y), text, font=font, fill=color)


def _cell_gradient(layer, x, y, w, h_grad, direction="down", max_alpha=170):
    pix = layer.load()
    for i in range(h_grad):
        t = i / h_grad if direction == "down" else 1.0 - i / h_grad
        alpha = int(max_alpha * t)
        for cx in range(x, x + w):
            pix[cx, y + i] = (0, 0, 0, alpha)


def _name_tag(draw, x, y, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad_x, pad_y = 10, 8
    draw.rounded_rectangle(
        [(x - pad_x, y - pad_y), (x + tw + pad_x, y + th + pad_y)],
        radius=4, fill=(255, 255, 255, 230)
    )
    draw.text((x, y), text, font=font, fill=(140, 8, 8))


def render_cover(bg_path: str, hook: str, out_path: str,
                 handle: str = "@dalatlamdong",
                 badge: str = "~ Nếu có 72H ở Đà lạt ~") -> str:
    img = load_bg(bg_path, W, H)
    canvas = img.convert("RGBA")
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    y = 382

    # Handle pill — centered
    font_handle = noto(18)
    hw = int(draw.textlength(handle, font=font_handle)) + 28
    pill(draw, (W - hw) // 2, y, hw, 30, handle,
         bg=(255, 255, 255, 200), fg=(30, 30, 30), font=font_handle, radius=15)
    y += 42

    # Orange badge — centered
    font_badge = noto(21)
    bw = int(draw.textlength(badge, font=font_badge)) + 34
    pill(draw, (W - bw) // 2, y, bw, 34, badge,
         bg=(234, 88, 12, 240), fg=(255, 255, 255), font=font_badge, radius=17)
    y += 52

    # Title — dark bg pill + auto-sized beviet_bold, white
    lines = hook.split("\n")
    line_gap = 10
    bg_pad_x, bg_pad_y = 50, 18
    max_line_w = W - bg_pad_x * 2
    font_size = 68
    font_title = beviet_bold(font_size)
    while font_size > 40:
        font_title = beviet_bold(font_size)
        if all(int(draw.textlength(l, font=font_title)) <= max_line_w for l in lines):
            break
        font_size -= 2
    total_title_h = len(lines) * font_title.size + (len(lines) - 1) * line_gap
    draw.rounded_rectangle(
        [(bg_pad_x, y - bg_pad_y), (W - bg_pad_x, y + total_title_h + bg_pad_y)],
        radius=20, fill=(15, 8, 3, 215)
    )
    for line in lines:
        tw = int(draw.textlength(line, font=font_title))
        draw.text(((W - tw) // 2, y), line, font=font_title, fill=(255, 255, 255))
        y += font_title.size + line_gap
    y += bg_pad_y + 20

    # Decorative wave — DancingScript tildes render as curvy wave
    font_wave = dancing(30)
    wave = "~~~~~~~~~~~"
    ww = int(draw.textlength(wave, font=font_wave))
    draw.text(((W - ww) // 2, y), wave, font=font_wave, fill=(190, 190, 190, 180))

    return save_slide(canvas, layer, out_path)


def render_grid_slide(venues_4: list, category_label: str, out_path: str) -> str:
    """venues_4: list of 4 venue dicts, each must have '_resolved_path' key."""
    CW, CH = W // 2, H // 2  # cell: 540 x 640
    pad = 16

    canvas = Image.new("RGB", (W, H), (20, 20, 20))
    positions = [(0, 0), (CW, 0), (0, CH), (CW, CH)]
    for vn, (px, py) in zip(venues_4, positions):
        thumb = load_thumb(vn.get("_resolved_path", ""), (CW, CH))
        canvas.paste(thumb, (px, py))

    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    _cell_gradient(layer, 0,  CH - 80, CW, 80, direction="down", max_alpha=180)
    _cell_gradient(layer, CW, CH - 80, CW, 80, direction="down", max_alpha=180)
    _cell_gradient(layer, 0,  CH,      CW, 80, direction="up",   max_alpha=160)
    _cell_gradient(layer, CW, CH,      CW, 80, direction="up",   max_alpha=160)

    draw = ImageDraw.Draw(layer)
    font_name = noto(20)
    font_cat = beviet_bold(70)
    label_h = font_cat.size
    cat_y = CH - label_h // 2 - 4

    # Top row: TOP-LEFT; bottom row: BOTTOM-LEFT
    name_y_top = pad
    name_y_bot = H - font_name.size - 8 - pad
    for vn, px_off in zip(venues_4[:2], [0, CW]):
        _name_tag(draw, px_off + pad, name_y_top, vn.get("name", ""), font_name)
    for vn, px_off in zip(venues_4[2:], [0, CW]):
        _name_tag(draw, px_off + pad, name_y_bot, vn.get("name", ""), font_name)

    # Category label: beviet_bold white + #8c0808 outline
    cat_w = int(draw.textlength(category_label, font=font_cat))
    cat_x = (W - cat_w) // 2
    stroke_col = (140, 8, 8)
    for ox, oy in [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, -1), (-1, 1), (1, 1)]:
        draw.text((cat_x + ox, cat_y + oy), category_label, font=font_cat, fill=stroke_col)
    draw.text((cat_x, cat_y), category_label, font=font_cat, fill=(255, 255, 255))

    canvas_rgba = canvas.convert("RGBA")
    canvas_rgba.alpha_composite(layer)
    out = canvas_rgba.convert("RGB")
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    out.save(out_path, "PNG")
    return out_path


def render_food_list_slide(bg_path: str, venues_list: list, food_thumb_venues: list,
                           out_path: str) -> str:
    """
    venues_list: venue dicts for bullet list (name + address)
    food_thumb_venues: 4 venue dicts with '_resolved_path' for bottom 2x2 grid
    """
    THUMB_TOP = 820
    THUMB_H = (H - THUMB_TOP) // 2  # 230
    THUMB_W = W // 2                 # 540

    img = load_bg(bg_path, W, H)
    canvas = img.convert("RGBA")

    # Dark overlay on text area only
    overlay = Image.new("RGBA", (W, THUMB_TOP), (0, 0, 0, 168))
    canvas.alpha_composite(overlay)

    # Bottom food thumbnails
    for i, vn in enumerate(food_thumb_venues[:4]):
        img_path = vn.get("_resolved_path", "")
        thumb = load_thumb(img_path, (THUMB_W, THUMB_H))
        col = i % 2
        row = i // 2
        canvas.paste(thumb, (col * THUMB_W, THUMB_TOP + row * THUMB_H))

    # Text layer
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    # Title
    font_title = beviet_bold(46)
    title = "List quán ăn ngon"
    tw = int(draw.textlength(title, font=font_title))
    _shadow_text(draw, (W - tw) // 2, 68, title, font_title, (255, 255, 255))

    # Separator line
    sep_y = 138
    draw.line([(58, sep_y), (W - 58, sep_y)], fill=(255, 255, 255, 90), width=2)

    # Bullet list
    font_item = noto(18)
    y = 155
    for vn in venues_list[:13]:
        name = vn.get("name", "")
        addr = vn.get("address", "")
        if len(addr) > 38:
            addr = addr.split(",")[0]
        draw.text((58, y), f"• {name} – {addr}", font=font_item, fill=(238, 238, 238))
        y += 40

    canvas.alpha_composite(layer)
    out_img = canvas.convert("RGB")
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    out_img.save(out_path, "PNG")
    return out_path
