"""
generate_myle115.py — Generate Myle115 album: 7 slides matching template format.
Usage: python -X utf8 generate_myle115.py [--seed N] [--out path]

Slide layout:
  00_cover    — full-screen bg + hook headline
  01_cafe     — 2x2 grid cafés / food mix, label "cà phê chillchill"
  02_checkin  — 2x2 grid tham quan, label "Check-in free"
  03_hotel    — 2x2 grid khách sạn, label "Lưu trú xịn"
  04_food1    — 2x2 grid quán ăn, label "Quán ăn ngon"
  05_food2    — 2x2 grid quán ăn, label "Đặc sản Đà Lạt"
  06_list     — bullet list of all food venues + bottom 4 thumbnails
"""
from __future__ import annotations
import sys, random, argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from tools.venue_picker import VenuePicker
from tools.venues_db import get_venues
from tools.myle115_renderer import (
    render_cover, render_grid_slide, render_food_list_slide, HOOK_HEADLINES,
)

# Paths to assets
ANH_DIR = Path(__file__).parent.parent / "anh video du lich"

# Thumbs may be in sibling project folder (no-accent variant)
_THUMBS_LOCAL = Path(__file__).parent.parent / "thumbs"
_THUMBS_SIBLING = (
    Path(__file__).parent.parent.parent.parent
    / "he thong edit video du lich" / "CreatorAppDuLich" / "thumbs"
)
THUMBS = _THUMBS_LOCAL if _THUMBS_LOCAL.exists() else _THUMBS_SIBLING


def _pick_bg() -> str:
    imgs = list(ANH_DIR.glob("*.JPG")) + list(ANH_DIR.glob("*.jpg"))
    imgs = [p for p in imgs if p.stat().st_size > 50_000]  # skip tiny files
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


def _add_resolved(venues: list) -> list:
    result = []
    for v in venues:
        v2 = dict(v)
        v2["_resolved_path"] = _resolve_thumb(v)
        result.append(v2)
    return result


def _fill_to_4(picker: VenuePicker, primary_cat: str, fallbacks: list | None = None) -> list:
    # Count how many unique venues are available in primary category
    avail = [v for v in picker._all
             if v.get("loai_quan") == primary_cat and v["name"] not in picker._used]
    n_primary = min(4, len(avail))
    result = picker.pick_n(n_primary, loai_quan=primary_cat) if n_primary > 0 else []
    if len(result) < 4 and fallbacks:
        for cat in fallbacks:
            needed = 4 - len(result)
            result.extend(picker.pick_n(needed, loai_quan=cat))
            if len(result) >= 4:
                break
    return result[:4]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    picker = VenuePicker(seed=args.seed)
    out_dir = args.out or str(Path(__file__).parent / "output" / "albums" / "myle115_demo")
    p = Path(out_dir)
    paths = []

    hook = random.choice(HOOK_HEADLINES)

    # ── Slide 1: Cover ───────────────────────────────────────────────────────
    bg = _pick_bg()
    out0 = str(p / "myle115_00_cover.png")
    print(f"[1/7] Cover → {out0}")
    paths.append(render_cover(bg, hook, out0))

    # ── Slide 2: Cafés (fill with food if < 4 cafés) ─────────────────────────
    cafes = _fill_to_4(picker, "quán cà phê", ["quán ăn"])
    print(f"[2/7] Café grid: {[v['name'] for v in cafes]}")
    paths.append(render_grid_slide(
        _add_resolved(cafes), "cà phê chillchill",
        str(p / "myle115_01_cafe.png")))

    # ── Slide 3: Check-in free ────────────────────────────────────────────────
    checkin = _fill_to_4(picker, "tham quan", ["khách sạn"])
    print(f"[3/7] Check-in grid: {[v['name'] for v in checkin]}")
    paths.append(render_grid_slide(
        _add_resolved(checkin), "Check-in free",
        str(p / "myle115_02_checkin.png")))

    # ── Slide 4: Hotels ───────────────────────────────────────────────────────
    hotels = _fill_to_4(picker, "khách sạn", ["tham quan"])
    print(f"[4/7] Hotel grid: {[v['name'] for v in hotels]}")
    paths.append(render_grid_slide(
        _add_resolved(hotels), "Lưu trú xịn",
        str(p / "myle115_03_hotel.png")))

    # ── Slide 5: Food grid 1 ──────────────────────────────────────────────────
    food1 = _fill_to_4(picker, "quán ăn", ["quán cà phê"])
    print(f"[5/7] Food grid 1: {[v['name'] for v in food1]}")
    paths.append(render_grid_slide(
        _add_resolved(food1), "Quán ăn ngon",
        str(p / "myle115_04_food1.png")))

    # ── Slide 6: Food grid 2 ──────────────────────────────────────────────────
    food2 = _fill_to_4(picker, "quán ăn", ["quán cà phê"])
    print(f"[6/7] Food grid 2: {[v['name'] for v in food2]}")
    paths.append(render_grid_slide(
        _add_resolved(food2), "Đặc sản Đà Lạt",
        str(p / "myle115_05_food2.png")))

    # ── Slide 7: Food list ────────────────────────────────────────────────────
    all_food = _add_resolved(get_venues(loai_quan="quán ăn"))
    food_thumbs = all_food[:4]
    bg2 = _pick_bg()
    print(f"[7/7] Food list ({len(all_food)} venues)")
    paths.append(render_food_list_slide(
        bg2, all_food, food_thumbs,
        str(p / "myle115_06_list.png")))

    print(f"\n✓ Album xong — {len(paths)} slides:")
    for s in paths:
        print(f"  file:///{Path(s).as_posix()}")


if __name__ == "__main__":
    main()
