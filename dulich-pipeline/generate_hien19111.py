"""
generate_hien19111.py — Generate hiền 19111 album: 72h Đà Lạt guide, 8 slides.
Usage: python -X utf8 generate_hien19111.py [--seed N] [--out path]

Slides:
  00_cover     — solid teal bg, bold title, notebook decoration
  01_music     — photo bg, music playlist two-column
  02_cafe_sang — cafes (with card)
  03_cafe_checkin — cafes check-in style (with card)
  04_food      — restaurants (with card)
  05_snack     — street food (with card)
  06_hotel     — accommodation (with card + price subtitle)
  07_sight     — sightseeing spots (bare list, no card)
"""
from __future__ import annotations
import sys, random, argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from tools.venue_picker import VenuePicker, album_bg
from tools.venues_db import resolve_image
from tools.hien19111_renderer import (
    render_cover, render_music_slide,
    render_venue_card_slide, render_venue_bare_slide,
    HOOK, SONGS,
)


def _pick_bg() -> str:
    # Ảnh nền không phải của quán → lấy random từ kho ảnh chung (không trùng).
    return album_bg()


def _venue_bg(venues: list) -> str:
    """Lấy ảnh của venue đầu tiên trong danh sách, fallback về random bg."""
    for v in venues:
        p = resolve_image(v)
        if p:
            return p
    return _pick_bg()


def _pick_n(picker: VenuePicker, cat: str, n: int = 10,
            fallback: str | None = None) -> list:
    avail = [v for v in picker._all if v.get("loai_quan") == cat
             and v["name"] not in picker._used]
    items = picker.pick_n(min(n, len(avail)), loai_quan=cat) if avail else []
    if len(items) < n and fallback:
        items += picker.pick_n(n - len(items), loai_quan=fallback)
    return items[:n]


VENUE_SLIDES = [
    ("cafe_sang",    "Chữa lành thì sáng đi\ncà phê rẻ rẻ thui",
     "", "quán cà phê", None, 10, True),
    ("cafe_checkin", "Còn đây là mấy quán\ncafe check-in đẹp đẹp",
     "Nước từ 80k - 120k/người", "quán cà phê", None, 10, True),
    ("food",         "Mấy quán ăn vừa ngon\nrẻ mà vẫn đảm bảo view",
     "Từ 30k - 200k/người", "quán ăn", None, 10, True),
    ("snack",        "Ăn hàng Đà Lạt\ncũng khác nữa",
     "Đặc sản vỉa hè không thể bỏ qua", "quán ăn", None, 10, True),
    ("hotel",        "Chỗ ngủ sạch sẽ, tiện nghi mà rẻ nữa\nthì chỉ có mấy chỗ này",
     "150k - 200k/đêm/người", "khách sạn", None, 10, True),
    ("sight",        "Check in mấy chỗ đậm vibe Đà Lạt nè",
     "", "điểm checkin", "điểm checkin free", 14, False),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--out", default="")
    args = parser.parse_args()
    if args.seed is not None:
        random.seed(args.seed)

    picker = VenuePicker(seed=args.seed)
    out_dir = args.out or str(
        Path(__file__).parent / "output" / "albums" / "hien19111_demo"
    )
    p = Path(out_dir)
    paths = []

    from tools.album_titles import ai_cover_texts
    hook = ai_cover_texts("vy2", {"hook": HOOK})["hook"]
    out0 = str(p / "hien19111_00_cover.png")
    print("[1/8] Cover →", out0)
    paths.append(render_cover(hook, out0))

    out1 = str(p / "hien19111_01_music.png")
    print("[2/8] Music playlist →", out1)
    paths.append(render_music_slide(_pick_bg(), SONGS, out1))

    for idx, (slug, title, subtitle, cat, fallback, n, use_card) in enumerate(
        VENUE_SLIDES, start=3
    ):
        venues = _pick_n(picker, cat, n, fallback)
        bg = _venue_bg(venues)
        out_n = str(p / f"hien19111_{idx - 1:02d}_{slug}.png")
        print(f"[{idx}/8] {slug} ({cat}) → {out_n}")
        if use_card:
            paths.append(render_venue_card_slide(bg, title, subtitle, venues, out_n))
        else:
            paths.append(render_venue_bare_slide(bg, title, venues, out_n))

    print(f"\n✓ Album xong — {len(paths)} slides:")
    for s in paths:
        print(f"  file:///{Path(s).as_posix()}")


if __name__ == "__main__":
    main()
