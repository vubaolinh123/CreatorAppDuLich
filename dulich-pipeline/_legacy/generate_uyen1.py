# -*- coding: utf-8 -*-
"""
generate_uyen1.py — Auto-generate "48h ở Đà Lạt" carousel (template uyen1).
5 slides: cover + title + illustrated map + checkin grid + food grid.
Usage: python -X utf8 generate_uyen1.py [--seed N] [--out path]
"""
from __future__ import annotations
import sys, argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from tools.venue_picker import VenuePicker
from tools.uyen1_renderer import (
    render_cover, render_title, render_map, render_photo_grid,
)

CITY           = "Đà Lạt"
CHECKIN_BANNER = "Đi check-in free"
FOOD_BANNER    = "Đi ănggg"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--out",  default="")
    args = parser.parse_args()

    picker  = VenuePicker(seed=args.seed)
    out_dir = args.out or str(Path(__file__).parent / "output" / "albums" / "uyen1_demo")
    p = Path(out_dir)
    p.mkdir(parents=True, exist_ok=True)

    cover_v = picker.pick_one(loai_quan="tham quan", co_nguoi="có") or picker.pick_one()
    checkin = picker.pick_n(4, loai_quan="tham quan")
    food    = picker.pick_n(4, loai_quan="quán ăn")

    paths = []

    # 0 — Cover
    paths.append(render_cover(picker.image(cover_v), str(p / "uyen1_00_cover.png")))
    print(f"[0] Cover  → {cover_v['name']}")

    # 1 — Title
    paths.append(render_title(str(p / "uyen1_01_title.png"), city=CITY))
    print(f"[1] Title")

    # 2 — Illustrated map
    paths.append(render_map(checkin, str(p / "uyen1_02_map.png"),
                            banner_text=CHECKIN_BANNER))
    print(f"[2] Map    — {len(checkin)} check-in spots")

    # 3 — Check-in photo grid
    paths.append(render_photo_grid(checkin, CHECKIN_BANNER,
                                   str(p / "uyen1_03_checkin.png")))
    print(f"[3] Check-in grid")
    for v in checkin:
        print(f"     {v['name']}")

    # 4 — Food photo grid
    paths.append(render_photo_grid(food, FOOD_BANNER,
                                   str(p / "uyen1_04_food.png")))
    print(f"[4] Food grid")
    for v in food:
        print(f"     {v['name']}")

    print(f"\n✓ {len(paths)} slides:")
    for s in paths:
        print(f"  file:///{Path(s).as_posix()}")


if __name__ == "__main__":
    main()
