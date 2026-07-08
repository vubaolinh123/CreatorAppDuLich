"""
generate_hien.py — Generate Hiền-style album: 7 slides.
Usage: python -X utf8 generate_hien.py [--seed N] [--out path]

Slides:
  00_cover       — solid teal, bold hook title, notebook decoration
  01_cafe_sang   — morning cafes bullet list
  02_cafe_checkin — check-in cafes bullet list
  03_food        — restaurants bullet list
  04_street_food — street food / snacks (quán ăn fallback)
  05_hotel       — accommodation bullet list
  06_sightseeing — tham quan bullet list
"""
from __future__ import annotations
import sys, random, argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from tools.venue_picker import VenuePicker
from tools.venues_db import get_venues
from tools.hien_renderer import (
    render_cover, render_venue_list_slide,
    HOOK_HEADLINES, SLIDE_OVERLAYS,
)

ANH_DIR = Path(__file__).parent.parent / "anh video du lich"
_THUMBS_LOCAL   = Path(__file__).parent.parent / "thumbs"
_THUMBS_SIBLING = (
    Path(__file__).parent.parent.parent.parent
    / "he thong edit video du lich" / "CreatorAppDuLich" / "thumbs"
)
THUMBS = _THUMBS_LOCAL if _THUMBS_LOCAL.exists() else _THUMBS_SIBLING


def _pick_bg() -> str:
    imgs = list(ANH_DIR.glob("*.JPG")) + list(ANH_DIR.glob("*.jpg"))
    imgs = [p for p in imgs if p.stat().st_size > 50_000]
    return str(random.choice(imgs)) if imgs else ""


def _resolve_thumb(venue: dict) -> str:
    name = venue.get("name", "")
    p = THUMBS / f"{name}.jpg"
    if p.exists():
        return str(p)
    img = venue.get("image_path", "")
    if img:
        alt = THUMBS / Path(img).name
        if alt.exists():
            return str(alt)
    return ""


def _add_r(venues: list) -> list:
    return [{**v, "_resolved_path": _resolve_thumb(v)} for v in venues]


def _pick_n(picker: VenuePicker, cat: str, n: int = 14, fallback: str | None = None) -> list:
    avail = [v for v in picker._all if v.get("loai_quan") == cat and v["name"] not in picker._used]
    items = picker.pick_n(min(n, len(avail)), loai_quan=cat) if avail else []
    if len(items) < n and fallback:
        extra = n - len(items)
        items += picker.pick_n(extra, loai_quan=fallback)
    return items[:n]


SLIDES = [
    ("cà phê sáng", "Chữa lành thì sáng đi\ncà phê rẻ rẻ thui",
     "Máy quán cà phê sáng tui mê nè, chill chill",
     "quán cà phê", "quán ăn", 0),
    ("cafe checkin", "Còn đây là mấy quán\ncheck in đẹp đẹp",
     "Giá nước từ 80k - 120k/người",
     "quán cà phê", None, 1),
    ("quán ăn", "Mấy quán ăn vừa ngon\nrẻ mà vẫn đảm bảo view xinh",
     "Chia ra chỉ từ 30k - 200k/người",
     "quán ăn", "quán cà phê", 2),
    ("ăn vặt", "Ăn hàng Đà Lạt\ncũng khác nữa",
     "Đặc sản vỉa hè không thể bỏ qua",
     "quán ăn", None, 3),
    ("khách sạn", "Chỗ ngủ sạch sẽ tiện nghi\nmà rẻ nữa thì chỉ có mấy chỗ này",
     "150k - 200k/đêm/người",
     "khách sạn", None, 4),
    ("tham quan", "Check in mấy chỗ\nđậm vibe Đà Lạt nê",
     "",
     "tham quan", None, 5),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--out", default="")
    args = parser.parse_args()
    if args.seed is not None:
        random.seed(args.seed)

    picker = VenuePicker(seed=args.seed)
    out_dir = args.out or str(Path(__file__).parent / "output" / "albums" / "hien_demo")
    p = Path(out_dir)
    paths = []

    hook = random.choice(HOOK_HEADLINES)
    out0 = str(p / "hien_00_cover.png")
    print(f"[1/7] Cover → {out0}")
    paths.append(render_cover(hook, out0))

    for i, (slug, title, subtitle, cat, fallback, ov_idx) in enumerate(SLIDES, start=2):
        venues = _add_r(_pick_n(picker, cat, 14, fallback))
        bg = _pick_bg()
        overlay = SLIDE_OVERLAYS[ov_idx]
        out_n = str(p / f"hien_{i-1:02d}_{slug.replace(' ','_')}.png")
        print(f"[{i}/7] {slug} → {out_n}")
        paths.append(render_venue_list_slide(bg, title, subtitle, venues, out_n, overlay))

    print(f"\n✓ Album xong — {len(paths)} slides:")
    for s in paths:
        print(f"  file:///{Path(s).as_posix()}")


if __name__ == "__main__":
    main()
