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


PINNED_SLIDE_NUMBER = 2
PINNED_SLIDE_VENUE = {
    "name": "Anmai Boutique Hotel",
    "address": "1A Đ. Lữ Gia, Lâm Viên - Đà Lạt",
}
PINNED_SLIDE_IMAGE = Path(__file__).parent / "data" / "thumbs" / "4_gm_0.jpg"


def _pin_slide_02(venues: list[dict]) -> list[dict]:
    """Giữ cố định nội dung file hien21113_02_venue.png qua mọi seed."""
    if len(venues) <= PINNED_SLIDE_NUMBER:
        raise RuntimeError("Album Hiền 2 không đủ venue để tạo slide 02")

    result = [dict(venue) for venue in venues]
    pinned_name = PINNED_SLIDE_VENUE["name"].casefold()
    current_index = next(
        (
            index
            for index, venue in enumerate(result)
            if str(venue.get("name") or "").casefold() == pinned_name
        ),
        None,
    )
    if current_index is not None and current_index != PINNED_SLIDE_NUMBER:
        result[current_index] = result[PINNED_SLIDE_NUMBER]
    result[PINNED_SLIDE_NUMBER] = dict(PINNED_SLIDE_VENUE)
    return result


def _slide_background(slide_number: int, venue: dict, picker: VenuePicker) -> str:
    if slide_number == PINNED_SLIDE_NUMBER:
        if not PINNED_SLIDE_IMAGE.is_file():
            raise FileNotFoundError(
                f"Thiếu ảnh cố định cho Album Hiền 2: {PINNED_SLIDE_IMAGE}"
            )
        return str(PINNED_SLIDE_IMAGE)
    return picker.image(venue)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    picker = VenuePicker(seed=args.seed)
    # 5 venue gốc (cover + 4 slide) + 3 slide check-in MỚI ở cuối
    venues = _pin_slide_02(
        picker.pick_n(5) + picker.pick_n(3, loai_quan=CHECKIN_CATS)
    )

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
        bg = _slide_background(slide_number, v, picker)
        tx, ty = VENUE_POSITIONS[i % len(VENUE_POSITIONS)]
        out_f = str(p / f"hien21113_{slide_number:02d}_venue.png")
        paths.append(render_venue_slide(bg, v["name"], v.get("address", ""), out_f, tx, ty))
        print(f"[{slide_number}] {v['name']} pos=({tx},{ty})")

    print(f"\n✓ {len(paths)} slides:")
    for s in paths:
        print(f"  file:///{Path(s).as_posix()}")


if __name__ == "__main__":
    main()
