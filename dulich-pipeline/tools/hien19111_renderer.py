"""
hien19111_renderer.py — Template hiền 19111: 72h Đà Lạt travel guide, 8 slides, 1080x1280.

Slide design (from reference):
  cover       — solid teal, hourglass emoji, bold title, notebook decoration bottom
  music       — photo bg dark overlay, yellow cursive title top-left, bullet song list right side
  venue_card  — photo bg dark overlay, per-line yellow pill titles, dark card with venues+addresses
  venue_bare  — photo bg dark overlay, per-line yellow pill title, bare text list (no card)
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from PIL import Image, ImageDraw
from tools.render_utils import (
    load_bg, dancing, beviet_bold, noto,
    draw_text_in_box, save_slide,
)

W, H = 1080, 1280
TEAL     = (126, 200, 200)   # cover bg
GOLD     = (200, 168, 75)    # yellow title text
DK_GREEN = (26, 74, 58)      # cover title text
OLIVE    = (43, 71, 33, 220) # dark pill behind title lines
CREAM    = (245, 240, 232)   # notebook fill


def _title_pill(draw: ImageDraw.Draw, text: str, font, x_center: int, y: int,
                pad_x: int = 18, pad_y: int = 9) -> int:
    """Draw one title line with a tight olive pill. Returns y after the line."""
    tw = int(draw.textlength(text, font=font))
    bx = x_center - tw // 2 - pad_x
    draw.rounded_rectangle(
        [(bx, y - pad_y), (bx + tw + pad_x * 2, y + font.size + pad_y)],
        radius=10, fill=OLIVE,
    )
    draw.text((x_center - tw // 2, y), text, font=font, fill=GOLD)
    return y + font.size + pad_y * 2 + 14


def render_cover(hook: str, out_path: str) -> str:
    canvas = Image.new("RGB", (W, H), TEAL)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    # Notebook decoration at bottom
    nb_y = H - 240
    draw.rounded_rectangle([(0, nb_y), (W, H)], radius=28, fill=(*CREAM, 255))
    draw.line([(60, nb_y + 88), (W - 60, nb_y + 88)],  fill=(*GOLD, 180), width=2)
    draw.line([(60, nb_y + 158), (W - 60, nb_y + 158)], fill=(*GOLD, 180), width=2)

    # Title centered between top and notebook
    font_title = beviet_bold(80)
    lines = hook.split("\n")
    line_gap = 12
    total_h = len(lines) * font_title.size + (len(lines) - 1) * line_gap
    y = max(140, (nb_y - total_h) // 2 - 40)
    for line in lines:
        tw = int(draw.textlength(line, font=font_title))
        draw.text(((W - tw) // 2, y), line, font=font_title, fill=DK_GREEN)
        y += font_title.size + line_gap

    canvas = canvas.convert("RGBA")
    canvas.alpha_composite(layer)
    out_img = canvas.convert("RGB")
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    out_img.save(out_path, "PNG")
    return out_path


def render_music_slide(bg_path: str, songs: list, out_path: str) -> str:
    """Dark photo + yellow cursive title top-left + bullet song list on right side."""
    img = load_bg(bg_path, W, H)
    canvas = img.convert("RGBA")
    canvas.alpha_composite(Image.new("RGBA", (W, H), (40, 55, 35, 168)))

    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    # Title top-left, yellow cursive
    font_title = dancing(56)
    title = "Chuẩn bị nhạc ghép story\ncho hợp vibe nha"
    y = 78
    for line in title.split("\n"):
        draw.text((60, y), line, font=font_title, fill=GOLD)
        y += font_title.size + 8
    y += 28

    # Song bullet list — right side (x=480 for 2-column feel)
    font_item = noto(26)
    LINE_H = font_item.size + 10
    col1_x, col2_x = 70, 570
    col = 0
    y1, y2 = y, y
    for song in songs:
        if col == 0:
            draw.text((col1_x, y1), f"• {song}", font=font_item, fill=(238, 238, 238))
            y1 += LINE_H
        else:
            draw.text((col2_x, y2), f"• {song}", font=font_item, fill=(238, 238, 238))
            y2 += LINE_H
        col = 1 - col

    canvas.alpha_composite(layer)
    out_img = canvas.convert("RGB")
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    out_img.save(out_path, "PNG")
    return out_path


def render_venue_card_slide(bg_path: str, title: str, subtitle: str,
                             venues: list, out_path: str) -> str:
    """Dark photo + per-line yellow pill title + dark rounded card with venue list."""
    img = load_bg(bg_path, W, H)
    canvas = img.convert("RGBA")
    canvas.alpha_composite(Image.new("RGBA", (W, H), (18, 22, 15, 185)))

    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    # Per-line pill titles centered
    font_title = dancing(52)
    y = 70
    for line in title.split("\n"):
        y = _title_pill(draw, line, font_title, W // 2, y)

    # Subtitle (price range etc.)
    if subtitle:
        font_sub = noto(28)
        sw = int(draw.textlength(subtitle, font=font_sub))
        draw.text(((W - sw) // 2, y), subtitle, font=font_sub, fill=(220, 220, 220))
        y += font_sub.size + 30
    else:
        y += 20

    # Dark card for venue list — chỉ render khi có venues
    card_pad = 48
    card_x = card_pad
    card_w = W - card_pad * 2
    font_venue = noto(26)
    row_h = font_venue.size + 10
    if venues:
        card_h = len(venues[:14]) * row_h + 36
        draw.rounded_rectangle(
            [(card_x, y), (card_x + card_w, y + card_h)],
            radius=18, fill=(30, 45, 22, 230)
        )
    vy = y + 18
    for vn in venues[:14]:
        name = vn.get("name", "")
        addr = vn.get("address", "")
        if len(addr) > 35:
            addr = addr.split(",")[0]
        line = f"{name} - {addr}" if addr else name
        draw.text((card_x + 22, vy), line, font=font_venue, fill=(235, 235, 235))
        vy += row_h

    canvas.alpha_composite(layer)
    out_img = canvas.convert("RGB")
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    out_img.save(out_path, "PNG")
    return out_path


def render_venue_bare_slide(bg_path: str, title: str, items: list,
                             out_path: str) -> str:
    """Dark photo + per-line yellow pill title + bare text list (no card, no address)."""
    img = load_bg(bg_path, W, H)
    canvas = img.convert("RGBA")
    canvas.alpha_composite(Image.new("RGBA", (W, H), (18, 22, 15, 178)))

    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    # Per-line pill title centered
    font_title = dancing(52)
    y = 70
    for line in title.split("\n"):
        y = _title_pill(draw, line, font_title, W // 2, y)

    y += 16

    # Bare item list centered, white
    font_item = noto(30)
    LINE_H = font_item.size + 16
    for item in items:
        name = item if isinstance(item, str) else item.get("name", "")
        iw = int(draw.textlength(name, font=font_item))
        draw.text(((W - iw) // 2, y), name, font=font_item, fill=(235, 235, 235))
        y += LINE_H
        if y > H - 60:
            break

    canvas.alpha_composite(layer)
    out_img = canvas.convert("RGB")
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    out_img.save(out_path, "PNG")
    return out_path


# Default hook and song list matching reference slide 1 and 3
HOOK = "Đà Lạt 72h\nCó đủ không?"

SONGS = [
    "Nếu những tiếc nuối",
    "Trước khi tuổi trẻ này đóng lối",
    "Perfect",
    "Vạn vật như muốn ta bên nhau",
    "Queen of disaster",
    "Pool",
    "ilomilo",
    "You broke me first",
    "The one of me",
    "Cơ hội cuối remix",
    "Phép màu",
    "Giấc mơ 20",
    "Không điều kiện",
    "Không đau nữa rồi",
    "Ngày hạnh phúc remix",
    "Giấc mơ - tùng",
    "An - Lil Wuyn",
    "Anh đã lớn hơn thế nhiều",
]
