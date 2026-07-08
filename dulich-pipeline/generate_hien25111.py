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

DEFAULT_ROAD_SECTIONS = [
    RoadSection(
        header="ĐÃ HOẠT ĐỘNG TRỞ LẠI",
        items=[
            "• Đèo Sông Pha: Mở lại từ 10h sáng",
            "• Đèo Tà Nung: Hoạt động bình thường",
            "• Đèo Sacom: Lưu thông ổn định",
        ],
    ),
    RoadSection(
        header="HẠN CHẾ / LƯU THÔNG THẬN TRỌNG",
        items=[
            "• Đèo Đại Ninh: Nên đi chậm",
            "• Đèo Gia Bắc: Lưu thông cẩn trọng",
            "• Đèo Prenn: Lưu thông 1 chiều",
        ],
    ),
    RoadSection(
        header="TẠM THỜI ĐÓNG",
        items=[
            "• Đèo Mimosa",
            "• Đèo Khánh Lê",
            "• Đèo Đ'Ran",
        ],
    ),
]

GRID_TITLES = [
    "Quán ăn nhất định phải ghé khi đến Đà Lạt",
    "Địa điểm ăn uống tuyệt vời tại Đà Lạt",
    "Quán ăn ngon không nên bỏ qua",
]


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
        "line1": "Cập nhật tình hình",
        "line2": "các đèo lên Đà Lạt",
        "grid1": GRID_TITLES[0], "grid2": GRID_TITLES[1], "grid3": GRID_TITLES[2],
    })

    out_dir = args.out or str(
        Path(__file__).parent / "output" / "albums" / "hien25111_demo"
    )
    p = Path(out_dir)

    paths = []

    # ── Slide 0: Cover ─────────────────────────────────────────────────────────
    cover_v = picker.pick_one(co_nguoi="có")
    bg_cover = picker.image(cover_v) if cover_v else ""
    out0 = str(p / "hien25111_00_cover.png")
    paths.append(render_cover(
        bg_path=bg_cover,
        title_line1=texts["line1"],
        title_line2=f"{texts['line2']} ({date_str})",
        out_path=out0,
    ))
    print(f"[0] Cover → {out0}")

    # ── Slide 1: Road status ───────────────────────────────────────────────────
    bg_road = picker.pick_one(co_nguoi="có")
    bg_road_path = picker.image(bg_road) if bg_road else ""
    out1 = str(p / "hien25111_01_road.png")
    paths.append(render_road_status(
        bg_path=bg_road_path,
        title=f"{texts['line1']} {texts['line2']} ({date_str})".upper(),
        sections=DEFAULT_ROAD_SECTIONS,
        footer_note="Mình sẽ tiếp tục cập nhật khi có thêm thông tin mới nhé",
        out_path=out1,
    ))
    print(f"[1] Road status → {out1}")

    # ── Slides 2-4: Venue grids ────────────────────────────────────────────────
    cats = [
        ("quán ăn", texts["grid1"]),
        ("quán ăn", texts["grid2"]),
        ("quán ăn", texts["grid3"]),
    ]

    for slide_idx, (cat, title) in enumerate(cats, 2):
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
