"""
generate_from_library.py — Tự động tạo album Mye26 từ thư viện địa điểm Đà Lạt.

Cách dùng:
  python -X utf8 generate_from_library.py
  python -X utf8 generate_from_library.py --seed 42
  python -X utf8 generate_from_library.py --out output/my_album
"""

from __future__ import annotations

import sys
import random
import argparse
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from tools.venues_db import get_all, resolve_image
from tools.mye26_renderer import CoverData, ActivityItem, ItinerarySlide, render_album


TITLE_TEMPLATES = [
    "Soạn Plan 3 Ngày\nĐà Lạt Chill",
    "Đà Lạt Full Option\nAn + Ở + Vui",
    "3 Ngày 2 Đêm\nPhố Núi Trọn Gói",
    "Check-in Ăn Uống\nĐà Lạt Chi Tiết",
    "Cẩm Nang Đà Lạt\nDành Cho Gia Đình",
    "Đà Lạt Tiết Kiệm\nBudget 3 Triệu",
    "Lịch Trình Đà Lạt\nNgày Nghỉ Lễ",
]

SUBTITLE_OPTIONS = [
    "Lưu lại đi ba",
    "Save lại đi cưng",
    "Share cho bạn bè nhé",
    "Đi theo plan này là chill",
    "Ghim lại nhớ lấy nha",
]

# (giờ, nhãn hoạt động, loại quán)
DAY_TEMPLATES = [
    [  # Ngày 1
        ("07:00", "Ăn sáng",    "quán ăn"),
        ("09:00", "Check-in",   "khách sạn"),
        ("12:00", "Ăn trưa",    "quán ăn"),
        ("15:00", "Tham quan",  "tham quan"),
        ("19:00", "Ăn tối",     "quán ăn"),
    ],
    [  # Ngày 2
        ("08:00", "Cà phê sáng","quán cà phê"),
        ("11:30", "Ăn trưa",    "quán ăn"),
        ("14:30", "Tham quan",  "tham quan"),
        ("19:00", "Ăn tối BBQ", "quán ăn"),
    ],
    [  # Ngày 3
        ("07:30", "Ăn sáng",    "quán ăn"),
        ("11:00", "Check-out",  "khách sạn"),
        ("12:30", "Ăn trưa",    "quán ăn"),
        ("15:30", "Cà phê",     "quán cà phê"),
    ],
]


def _pick(pool: list, used: set, fallback_pool: list | None = None) -> dict | None:
    available = [v for v in pool if v["name"] not in used]
    if not available and fallback_pool:
        available = [v for v in fallback_pool if v["name"] not in used]
    if not available:
        available = pool
    if not available:
        return None
    v = random.choice(available)
    used.add(v["name"])
    return v


def main() -> None:
    parser = argparse.ArgumentParser(description="Tạo album Mye26 từ thư viện địa điểm")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--out",  default="")
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    all_venues = get_all()

    # ── Pools ────────────────────────────────────────────────────────────────
    bg_with    = [v for v in all_venues if v.get("co_nguoi") == "có"]
    bg_without = [v for v in all_venues if v.get("co_nguoi") == "không"]
    pools = {
        "quán ăn":     [v for v in all_venues if v.get("loai_quan") == "quán ăn"],
        "khách sạn":   [v for v in all_venues if v.get("loai_quan") == "khách sạn"],
        "tham quan":   [v for v in all_venues if v.get("loai_quan") == "tham quan"],
        "quán cà phê": [v for v in all_venues if v.get("loai_quan") == "quán cà phê"],
    }

    if not bg_with:
        bg_with = all_venues
    if not bg_without:
        bg_without = all_venues

    # ── Cover background: venue có mặt người ─────────────────────────────────
    cover_bg_v = random.choice(bg_with)
    cover_bg   = resolve_image(cover_bg_v)
    print(f"[COVER BG]  {cover_bg_v['name']}  (co_nguoi={cover_bg_v.get('co_nguoi')})")

    # ── Build 3 day slides ───────────────────────────────────────────────────
    used_activity: set = set()
    hotel_day1: dict | None = None
    slides = []
    used_bgs: set = {cover_bg_v["name"]}

    for day_num, schedule in enumerate(DAY_TEMPLATES, 1):
        # Background cho slide nội dung: không có người
        bg_pool_avail = [v for v in bg_without if v["name"] not in used_bgs]
        if not bg_pool_avail:
            bg_pool_avail = bg_without
        bg_v  = random.choice(bg_pool_avail)
        used_bgs.add(bg_v["name"])
        bg_path = resolve_image(bg_v)
        print(f"\n[DAY {day_num} BG]  {bg_v['name']}")

        activities = []
        for time, label, category in schedule:
            # Ngày 3 check-out → reuse hotel đã pick ngày 1
            if category == "khách sạn" and day_num == 3 and hotel_day1:
                v = hotel_day1
            else:
                v = _pick(pools.get(category, []), used_activity)
                if category == "khách sạn" and day_num == 1:
                    hotel_day1 = v

            if v is None:
                continue

            thumb = resolve_image(v)
            # Rút gọn địa chỉ: bỏ "Đà Lạt" ở cuối nếu quá dài
            addr = v.get("address", "")
            if len(addr) > 35:
                addr = addr.split(",")[0]  # chỉ lấy số + tên đường
            activities.append(ActivityItem(
                time=time,
                activity=label,
                venue=v["name"],
                address=addr,
                thumbnail_path=thumb,
            ))
            print(f"  {time}  {label:12}  {v['name']}")

        slides.append(ItinerarySlide(bg_path, day_num, activities))

    # ── Cover ────────────────────────────────────────────────────────────────
    month = datetime.now().month
    cover = CoverData(
        background_path=cover_bg,
        month_tag    =f"Tháng {month}",
        handle_tag   ="@thamhiemdalat",
        location_tag ="Đà Lạt",
        title        =random.choice(TITLE_TEMPLATES),
        subtitle     =random.choice(SUBTITLE_OPTIONS),
    )

    # ── Render ───────────────────────────────────────────────────────────────
    out_dir = args.out or str(Path(__file__).parent / "output" / "albums" / "library_demo")
    paths = render_album(cover, slides, out_dir, album_name="library_demo")

    print(f"\n✓ {len(paths)} slides:")
    for p in paths:
        print(f"  file:///{Path(p).as_posix()}")


if __name__ == "__main__":
    main()
