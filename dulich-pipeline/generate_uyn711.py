"""
generate_uyn711.py — Auto-generate T5 "7 điều đừng làm ở Đà Lạt" (7 slides).
Usage: python -X utf8 generate_uyn711.py [--seed N] [--out path]
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from tools.venue_picker import VenuePicker
from tools.uyn711_renderer import render_cover, render_title, render_tip

# Dynamic venue slides: slide_idx (0-4) → category config
DYNAMIC_SLIDES = {
    0: {"cats": ["tham quan"], "n": 6},   # page 2: check-in spots
    4: {"cats": ["quán ăn"], "n": 4},     # page 6: food spots
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    picker = VenuePicker(seed=args.seed)
    out_dir = args.out or str(
        Path(__file__).parent / "output" / "albums" / "uyn711_demo"
    )
    p = Path(out_dir)
    paths = []
    used: set = set()

    def _pick(cat=None):
        v = picker.pick_one(loai_quan=cat, exclude=used)
        if v:
            used.add(v["name"])
        return v

    # ── Slide 0: Cover ─────────────────────────────────────────────────────────
    v0 = _pick()
    out0 = str(p / "uyn711_00_cover.png")
    paths.append(render_cover(picker.image(v0) if v0 else "", out0))
    print(f"[0] Cover → {out0}")

    # ── Slide 1: Title ─────────────────────────────────────────────────────────
    v1 = _pick(cat="tham quan")
    out1 = str(p / "uyn711_01_title.png")
    paths.append(render_title(picker.image(v1) if v1 else "", out1))
    print(f"[1] Title → {out1}")

    # ── Slides 2-6: Tip slides ─────────────────────────────────────────────────
    for slide_idx in range(5):
        bg_v = _pick()
        content_v = _pick()
        bg_path = picker.image(bg_v) if bg_v else ""
        content_path = picker.image(content_v) if content_v else ""

        venues_left, venues_right = None, None
        if slide_idx in DYNAMIC_SLIDES:
            cfg = DYNAMIC_SLIDES[slide_idx]
            cats, n = cfg["cats"], cfg["n"]
            venues_raw, dyn_used = [], set()
            for i in range(n):
                cat = cats[i % len(cats)]
                v = picker.pick_one(loai_quan=cat, exclude=used | dyn_used)
                if v and v["name"] not in dyn_used:
                    venues_raw.append(v["name"].upper())
                    dyn_used.add(v["name"])
            half = len(venues_raw) // 2
            venues_left = venues_raw[:half] or None
            venues_right = venues_raw[half:] or None

        out_path = str(p / f"uyn711_0{slide_idx + 2}_tip.png")
        paths.append(render_tip(slide_idx, bg_path, content_path, out_path,
                                venues_left=venues_left,
                                venues_right=venues_right))
        print(f"[{slide_idx + 2}] Tip{slide_idx} → {out_path}")

    print(f"\n{len(paths)} slides generated:")
    for s in paths:
        print(f"  file:///{Path(s).as_posix()}")


if __name__ == "__main__":
    main()
