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

    # 0 — Intro (bỏ slide cover không tiêu đề theo feedback NV). Nền: ảnh chung (không phải quán).
    from tools.album_titles import ai_cover_texts
    from tools.uyen2_renderer import INTRO_TEXT
    _t = ai_cover_texts("uyen2", {"intro": INTRO_TEXT})
    paths.append(render_intro(
        picker.album_bg(),
        str(p / "uyen2_00_intro.png"),
        text=_t["intro"],
    ))
    print(f"[0] Intro")

    # 1-6 — Review slides (6 quán ăn: 3 review + 3 option thêm)
    review_venues = picker.pick_n(6, loai_quan="quán ăn")
    for i, v in enumerate(review_venues):
        paths.append(render_review(
            picker.image(v),
            v,
            i,
            str(p / f"uyen2_{i + 1:02d}_review{i}.png"),
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
