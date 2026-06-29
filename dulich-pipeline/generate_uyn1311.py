"""
generate_uyn1311.py — Auto-generate T4 "Nếu chỉ có 48h ở Đà Lạt" (7 slides).
Usage: python -X utf8 generate_uyn1311.py [--seed N] [--out path]
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from tools.venue_picker import VenuePicker
from tools.uyn1311_renderer import GridVenue, render_cover, render_title, render_grid_page

SECTIONS = [
    ("Đi check-in free 🌿",    ["tham quan"]),
    ("Đi cafe vibe Đà Lạt ☕",  ["quán cà phê", "quán ăn"]),
    ("Đi chơi 🌳",              ["tham quan"]),
    ("Đi ănggg 🍽️",             ["quán ăn"]),
    ("Đi tráng miệng 🧋",       ["quán ăn"]),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    picker = VenuePicker(seed=args.seed)
    out_dir = args.out or str(
        Path(__file__).parent / "output" / "albums" / "uyn1311_demo"
    )
    p = Path(out_dir)
    paths = []

    # ── Slide 0: Cover ─────────────────────────────────────────────────────
    cover_v = picker.pick_one()
    out0 = str(p / "uyn1311_00_cover.png")
    paths.append(render_cover(picker.image(cover_v) if cover_v else "", out0))
    print(f"[0] Cover → {out0}")

    # ── Slide 1: Title ─────────────────────────────────────────────────────
    title_v = picker.pick_one(co_nguoi="có")
    out1 = str(p / "uyn1311_01_title.png")
    paths.append(render_title(picker.image(title_v) if title_v else "", out1))
    print(f"[1] Title → {out1}")

    # ── Slides 2-6: Grid pages ─────────────────────────────────────────────
    for slide_idx, (header, cats) in enumerate(SECTIONS, 2):
        picker.reset_used()
        venues_raw = []
        used_names: set = set()
        for i in range(6):
            cat = cats[i % len(cats)] if cats else None
            v = picker.pick_one(loai_quan=cat, exclude=used_names)
            if v["name"] in used_names:
                # Primary category exhausted — try any type
                v = picker.pick_one(exclude=used_names)
            if v and v["name"] not in used_names:
                venues_raw.append(v)
                used_names.add(v["name"])

        venues = [
            GridVenue(name=v["name"], photo_path=picker.image(v))
            for v in venues_raw
        ]

        out_path = str(p / f"uyn1311_0{slide_idx}_grid.png")
        paths.append(render_grid_page(header, venues, out_path))
        print(f"[{slide_idx}] {header} → {out_path}")

    print(f"\n{len(paths)} slides generated:")
    for s in paths:
        print(f"  file:///{Path(s).as_posix()}")


if __name__ == "__main__":
    main()
