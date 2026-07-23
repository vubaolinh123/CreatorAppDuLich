# -*- coding: utf-8 -*-
"""
generate_muoi1912.py — Auto-generate Muốihien1 travel advice carousel.
6 slides: cover + 4 guide slides (white infographic) + CTA.
Usage: python -X utf8 generate_muoi1912.py [--seed N] [--out path]
"""
from __future__ import annotations
import sys, random, argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from tools.venue_picker import VenuePicker, CHECKIN_CATS
from tools.muoi1912_renderer import (
    render_cover, render_guide_slide, render_cta_slide,
    HOOK_LINES, GUIDE_SECTIONS,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    picker = VenuePicker(seed=args.seed)
    from tools.album_titles import ai_cover_texts
    _fb = random.choice(HOOK_LINES)
    _t = ai_cover_texts("muoi1", {"line1": _fb[0], "line2": _fb[1], "line3": _fb[2]})
    hook = (_t["line1"], _t["line2"], _t["line3"])

    out_dir = args.out or str(Path(__file__).parent / "output" / "albums" / "muoi1912_demo")
    p = Path(out_dir)
    p.mkdir(parents=True, exist_ok=True)

    cover_bg = picker.album_bg()   # cover không nói về 1 quán → ảnh chung
    print(f"[COVER] hook: {hook[0]}")
    paths = [render_cover(hook, cover_bg, str(p / "muoi1912_00_cover.png"))]

    for i, sec in enumerate(GUIDE_SECTIONS, 1):
        # Pick 6 venues (dedup by name)
        raw = picker.pick_n(8, loai_quan=sec["category"])
        seen = set()
        venues = [v for v in raw if v["name"] not in seen and not seen.add(v["name"])][:6]

        venue_imgs = [picker.image(v) for v in venues]

        # Pick a separate bg photo for the slide (điểm check-in cho cảnh đẹp)
        bg_v = picker.pick_one(loai_quan=CHECKIN_CATS) or picker.pick_one()
        bg_path = picker.image(bg_v) if bg_v else (venue_imgs[0] if venue_imgs else "")

        out_f = str(p / f"muoi1912_{i:02d}_guide.png")
        paths.append(render_guide_slide(sec, venues, venue_imgs, bg_path, out_f))
        for v in venues:
            print(f"  [{sec['category']}] {v['name']}")

    cta_v = picker.pick_one(co_nguoi="không") or picker.pick_one()
    paths.append(render_cta_slide(picker.image(cta_v), str(p / "muoi1912_05_cta.png")))

    print(f"\n✓ {len(paths)} slides:")
    for s in paths:
        print(f"  file:///{Path(s).as_posix()}")


if __name__ == "__main__":
    main()
