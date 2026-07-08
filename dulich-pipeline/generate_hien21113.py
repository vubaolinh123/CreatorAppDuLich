# -*- coding: utf-8 -*-
"""
generate_hien21113.py — Auto-generate hiền 21113 venue spotlight carousel.
Usage: python -X utf8 generate_hien21113.py [--seed N] [--out path]
"""
from __future__ import annotations
import sys, random, argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from tools.venue_picker import VenuePicker
from tools.hien21113_renderer import render_cover, render_venue_slide, HOOK_TEXTS, VENUE_POSITIONS


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    picker = VenuePicker(seed=args.seed)
    venues = picker.pick_n(5)

    out_dir = args.out or str(Path(__file__).parent / "output" / "albums" / "hien21113_demo")
    p = Path(out_dir)
    p.mkdir(parents=True, exist_ok=True)

    from tools.album_titles import ai_cover_texts
    pov_text = ai_cover_texts("hien2", {"pov": random.choice(HOOK_TEXTS)})["pov"]
    cover_v = venues[0]
    cover_bg = picker.image(cover_v)

    print(f"[COVER] {cover_v['name']}")
    paths = [render_cover(cover_bg, pov_text, str(p / "hien21113_00_cover.png"))]

    for i, v in enumerate(venues[1:], 0):
        bg = picker.image(v)
        tx, ty = VENUE_POSITIONS[i % len(VENUE_POSITIONS)]
        out_f = str(p / f"hien21113_{i+1:02d}_venue.png")
        paths.append(render_venue_slide(bg, v["name"], v.get("address", ""), out_f, tx, ty))
        print(f"[{i+1}] {v['name']} pos=({tx},{ty})")

    print(f"\n✓ {len(paths)} slides:")
    for s in paths:
        print(f"  file:///{Path(s).as_posix()}")


if __name__ == "__main__":
    main()
