# -*- coding: utf-8 -*-
"""
generate_muoi1311.py — Auto-generate Muối 13/11 venue-list Local/hot-hit carousel.
Usage: python -X utf8 generate_muoi1311.py [--seed N] [--out path]
"""
from __future__ import annotations
import sys, argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from tools.venue_picker import VenuePicker
from tools.muoi1311_renderer import render_cover, render_list_slide, render_cta_slide

SLIDE_CATEGORIES = [
    ("quán ăn",     "Ăn sáng tại Đà Lạt"),
    ("tham quan",   "Dalat check-in theo hệ"),
    ("quán cà phê", "Dalat ăn uống theo hệ"),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    picker = VenuePicker(seed=args.seed)
    out_dir = args.out or str(Path(__file__).parent / "output" / "albums" / "muoi1311_demo")
    p = Path(out_dir)
    p.mkdir(parents=True, exist_ok=True)

    cover_v = picker.pick_one(co_nguoi="có") or picker.pick_one()
    cover_bg = picker.image(cover_v)
    paths = [render_cover(cover_bg, str(p / "muoi1311_00_cover.png"))]
    print(f"[COVER] bg: {cover_v['name']}")

    for i, (cat, title) in enumerate(SLIDE_CATEGORIES, 1):
        raw = picker.pick_n(12, loai_quan=cat)
        seen = set()
        unique = [v for v in raw if v["name"] not in seen and not seen.add(v["name"])]
        mid = len(unique) // 2
        local = unique[:max(mid, 1)]
        hothit = unique[mid:] if len(unique) > 1 else []

        # Use first local venue photo as slide background
        bg = picker.image(local[0]) if local else picker.image(picker.pick_one())
        out_f = str(p / f"muoi1311_{i:02d}_list.png")
        paths.append(render_list_slide(title, local, hothit, bg, out_f))

        for v in local:  print(f"  [LOCAL] {v['name']}")
        for v in hothit: print(f"  [HOT]   {v['name']}")

    cta_v = picker.pick_one(co_nguoi="có") or picker.pick_one()
    paths.append(render_cta_slide(picker.image(cta_v),
                                  str(p / f"muoi1311_{len(SLIDE_CATEGORIES)+1:02d}_cta.png")))

    print(f"\n✓ {len(paths)} slides:")
    for s in paths:
        print(f"  file:///{Path(s).as_posix()}")


if __name__ == "__main__":
    main()
