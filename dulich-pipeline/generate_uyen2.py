# -*- coding: utf-8 -*-
"""
generate_uyen2.py — "Review diary" restaurant carousel.
5 slides: cover + intro + 3 venue review slides.
Usage: python -X utf8 generate_uyen2.py [--seed N] [--out path]
"""
from __future__ import annotations
import sys, argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from tools.venue_picker import VenuePicker
from tools.uyen2_renderer import render_cover, render_intro, render_review


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    picker = VenuePicker(seed=args.seed)
    out_dir = args.out or str(
        Path(__file__).parent / "output" / "albums" / "uyen2_demo"
    )
    p = Path(out_dir)
    p.mkdir(parents=True, exist_ok=True)

    paths = []

    # 0 — Cover
    cover_v = picker.pick_one(co_nguoi="có") or picker.pick_one()
    paths.append(render_cover(
        picker.image(cover_v),
        str(p / "uyen2_00_cover.png"),
    ))
    print(f"[0] Cover  -> {cover_v['name']}")

    # 1 — Intro
    intro_v = picker.pick_one(loai_quan="quán ăn") or picker.pick_one()
    paths.append(render_intro(
        picker.image(intro_v),
        str(p / "uyen2_01_intro.png"),
    ))
    print(f"[1] Intro")

    # 2-4 — Review slides (3 quán ăn)
    review_venues = picker.pick_n(3, loai_quan="quán ăn")
    for i, v in enumerate(review_venues):
        paths.append(render_review(
            picker.image(v),
            v,
            i,
            str(p / f"uyen2_0{i + 2}_review{i}.png"),
        ))
        sig = (v.get("signature") or "")[:55]
        print(f"[{i + 2}] Review -> {v['name']}")
        if sig:
            print(f"     sig: {sig}")

    print(f"\n✓ {len(paths)} slides -> {out_dir}")
    for s in paths:
        print(f"  file:///{Path(s).as_posix()}")


if __name__ == "__main__":
    main()
