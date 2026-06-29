"""
generate_mle23.py — T1 "99% khách du lịch" (5 slides).
Usage: python -X utf8 generate_mle23.py [--seed N] [--out path]
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from tools.venue_picker import VenuePicker
from tools.mle23_renderer import (
    render_cover, render_ggmaps_tip, render_oneway,
    render_activities, render_food,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    picker = VenuePicker(seed=args.seed)
    out_dir = args.out or str(
        Path(__file__).parent / "output" / "albums" / "mye26_output"
    )
    p = Path(out_dir)
    paths = []

    def bg(v):
        return picker.image(v) if v else ""

    # 0 — Cover (street/scenic with people)
    v0 = picker.pick_one(co_nguoi="có")
    out0 = str(p / "mle23_00_cover.png")
    paths.append(render_cover(bg(v0), out0))
    print(f"[0] Cover → {out0}")

    # 1 — Google Maps tip (street/traffic scene)
    v1 = picker.pick_one()
    out1 = str(p / "mle23_01_ggmaps.png")
    paths.append(render_ggmaps_tip(bg(v1), out1))
    print(f"[1] GG Maps tip → {out1}")

    # 2 — Đường một chiều (street photo)
    v2 = picker.pick_one()
    out2 = str(p / "mle23_02_oneway.png")
    paths.append(render_oneway(bg(v2), out2))
    print(f"[2] Đường 1 chiều → {out2}")

    # 3 — Activities (outdoor/cafe/attraction)
    v3 = picker.pick_one(loai_quan=["tham quan", "quán cà phê"])
    out3 = str(p / "mle23_03_activities.png")
    paths.append(render_activities(bg(v3), out3))
    print(f"[3] Activities → {out3}")

    # 4 — Food (3 restaurant photos)
    food_venues = picker.pick_n(3, loai_quan="quán ăn")
    food_photos = [picker.image(v) for v in food_venues]
    v4 = picker.pick_one(loai_quan="quán ăn")
    out4 = str(p / "mle23_04_food.png")
    paths.append(render_food(bg(v4), out4, food_photos=food_photos))
    print(f"[4] Food → {out4}")

    print(f"\n{len(paths)} slides generated:")
    for s in paths:
        print(f"  file:///{Path(s).as_posix()}")


if __name__ == "__main__":
    main()
