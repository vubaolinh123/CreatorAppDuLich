"""
generate_hien25111.py — Auto-generate T6 "Cập nhật tình hình đèo Đà Lạt".
Tạo: 1 cover + 1 road status + 3 venue-grid pages (café/restaurant).
Usage: python -X utf8 generate_hien25111.py [--seed N] [--out path]
"""
from __future__ import annotations

import argparse
import random
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from tools.venue_picker import VenuePicker
from tools.hien25111_renderer import (
    RoadSection, SeasonalItem,
    render_cover, render_road_status, render_inside_update, render_venue_grid,
)

# 3 slide grid đồng bộ 1 tiêu đề (fix cứng, KHÔNG qua AI để 3 slide giống hệt nhau).
GRID_TITLE = "BẢN ĐỒ MÓN NGON ĐÀ LẠT PHẢI THỬ"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    picker = VenuePicker(seed=args.seed)
    now = datetime.now()
    date_str = f"{now.day}/{now.month}"

    from tools.album_titles import ai_cover_texts
    texts = ai_cover_texts("hien1", {
        "line1": "Bản đồ món ngon",
        "line2": "Đà Lạt phải thử",
    })

    out_dir = args.out or str(
        Path(__file__).parent / "output" / "albums" / "hien25111_demo"
    )
    p = Path(out_dir)

    paths = []

    # ── Slide 0: Cover (nền ảnh chung, không phải quán) ─────────────────────────
    out0 = str(p / "hien25111_00_cover.png")
    paths.append(render_cover(
        bg_path=picker.album_bg(),
        title_line1=texts["line1"],
        title_line2=texts["line2"],
        out_path=out0,
    ))
    print(f"[0] Cover → {out0}")

    # ── Slides 1-3: Venue grids (3 slide quán ăn, cùng 1 tiêu đề) ────────────────
    cats = [("quán ăn", GRID_TITLE)] * 3

    for slide_idx, (cat, title) in enumerate(cats, 1):
        venues = picker.pick_n(9, loai_quan=cat)
        # Fallback: refill with any if not enough
        while len(venues) < 9:
            extra = picker.pick_one(loai_quan=cat)
            if extra:
                venues.append(extra)
            else:
                break

        venue_dicts = [
            {
                "name": v["name"],
                "address": v.get("address", ""),
                "image_path": picker.image(v),
            }
            for v in venues
        ]

        out_path = str(p / f"hien25111_0{slide_idx}_grid.png")
        paths.append(render_venue_grid(title, venue_dicts, out_path))
        print(f"[{slide_idx}] {title} → {out_path}")

    print(f"\n{len(paths)} slides generated:")
    for s in paths:
        print(f"  file:///{Path(s).as_posix()}")


if __name__ == "__main__":
    main()
