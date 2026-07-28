# -*- coding: utf-8 -*-
"""
generate_hien21113.py — Auto-generate hiền 21113 venue spotlight carousel.
Usage: python -X utf8 generate_hien21113.py [--seed N] [--out path]
"""
from __future__ import annotations
import sys, random, argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from tools.venue_picker import VenuePicker, CHECKIN_CATS
from tools.hien21113_renderer import render_cover, render_venue_slide, HOOK_TEXTS, VENUE_POSITIONS


HOTEL_SLIDE_NUMBER = 2
HOTEL_CATEGORY = "khách sạn"
NON_HOTEL_CATEGORIES = (
    "quán ăn",
    "quán cà phê",
    "đặc sản",
    *CHECKIN_CATS,
)


def _select_venues(picker: VenuePicker) -> list[dict]:
    """7 venue: cover + 6 slide; chỉ slide 02 là khách sạn seeding."""
    regular = picker.pick_n(3, loai_quan=NON_HOTEL_CATEGORIES)
    hotels = picker.pick_n(1, loai_quan=HOTEL_CATEGORY, seeding_first=True)
    checkins = picker.pick_n(3, loai_quan=CHECKIN_CATS)
    if len(regular) != 3 or len(hotels) != 1 or len(checkins) != 3:
        raise RuntimeError("Album Hiền 2 không đủ venue để tạo 7 slide")

    venues = [
        regular[0],    # cover
        regular[1],    # slide 01
        hotels[0],     # slide 02: khách sạn động, ưu tiên seeding
        regular[2],    # slide 03
        *checkins,     # slide 04-06
    ]
    hotel_slides = [
        index
        for index, venue in enumerate(venues)
        if venue.get("loai_quan") == HOTEL_CATEGORY
    ]
    if hotel_slides != [HOTEL_SLIDE_NUMBER]:
        raise RuntimeError("Album Hiền 2 chỉ được có khách sạn ở slide 02")
    return venues


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    picker = VenuePicker(seed=args.seed)
    venues = _select_venues(picker)

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
        slide_number = i + 1
        bg = picker.image(v)
        tx, ty = VENUE_POSITIONS[i % len(VENUE_POSITIONS)]
        out_f = str(p / f"hien21113_{slide_number:02d}_venue.png")
        paths.append(render_venue_slide(bg, v["name"], v.get("address", ""), out_f, tx, ty))
        print(f"[{slide_number}] {v['name']} pos=({tx},{ty})")

    print(f"\n✓ {len(paths)} slides:")
    for s in paths:
        print(f"  file:///{Path(s).as_posix()}")


if __name__ == "__main__":
    main()
