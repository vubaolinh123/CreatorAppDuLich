"""
demo_mye26.py — Demo tạo album Mye26 với dữ liệu thực từ CSV quán.

Chạy từ thư mục dulich-pipeline:
    python demo_mye26.py

Output: output/albums/demo_mye26/
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from tools.mye26_renderer import (
    CoverData, ActivityItem, ItinerarySlide, render_album,
)
from tools.venues_db import get_all
from tools.venue_picker import VenuePicker

# Seed NGẪU NHIÊN ảnh (đọc --seed sớm vì lịch trình build ngay khi import)
import random as _rnd
import argparse as _ap
_pre = _ap.ArgumentParser(add_help=False)
_pre.add_argument("--seed", type=int, default=None)
_seed_args, _ = _pre.parse_known_args()
if _seed_args.seed is not None:
    _rnd.seed(_seed_args.seed)

# ── Lookup ảnh từ thư viện venue (chọn ngẫu nhiên trong bộ ảnh của quán) ──────
_VENUE_DB = {v["name"]: v for v in get_all()}

def _venue_img(name: str) -> str:
    v = _VENUE_DB.get(name)
    return VenuePicker.image(v) if v else ""

def _day_bg(activities: list) -> str:
    for act in activities:
        img = _venue_img(act.venue)
        if img:
            return img
    return ""

def _act(time, activity, venue_name, address):
    """Tạo ActivityItem với thumbnail tự resolve từ DB."""
    return ActivityItem(time, activity, venue_name, address,
                        thumbnail_path=_venue_img(venue_name))

# ── Lịch trình 3 ngày ────────────────────────────────────────────────────────
NGAY_1_ACTIVITIES = [
    _act("7:30",  "Ăn sáng",       "Sườn cay khổng lồ",    "42 Phan Chu Trinh"),
    _act("9:00",  "Check-in",      "Cozy Garden Boutique Hotel", "94 Đ. Lữ Gia"),
    _act("11:30", "Ăn trưa",       "Yod Thong",             "04 Đoàn Thị Điểm"),
    _act("14:00", "Tham quan",     "Langbiang Land",        "93A Đường Bidoup"),
    _act("17:00", "Sunset view",   "Đồi chè Cầu Đất",       "Xã Xuân Trường"),
    _act("19:00", "Ăn tối & BBQ",  "Trạm Nắng BBQ",         "18 Đống Đa"),
    _act("20:30", "Dạo chợ đêm",   "Chợ Đà Lạt",            "Nguyễn Thị Minh Khai"),
]

NGAY_2_ACTIVITIES = [
    _act("7:00",  "Ăn sáng sớm",      "Bánh mì Đà Lạt",        "65 Phan Đình Phùng"),
    _act("8:30",  "Check-in view đẹp", "Anmai Boutique Hotel",  "1A Đ. Lữ Gia"),
    _act("10:00", "Cà phê",            "Tiệm cà phê Chạng Vạng","119 Huỳnh Tấn Phát"),
    _act("12:00", "Ăn trưa Thái",      "Yod Thong",             "04 Đoàn Thị Điểm"),
    _act("14:30", "Tham quan thác",    "Thác Datanla",          "Đèo Prenn"),
    _act("17:30", "Mua đặc sản",       "Chợ Đà Lạt",            "Nguyễn Công Trứ"),
    _act("19:00", "Lẩu bò tối",        "Lẩu bò Gia Lâm",        "30 Ngô Quyền"),
]

NGAY_3_ACTIVITIES = [
    _act("7:00",  "Ăn sáng",         "Bánh Mì Xíu Mại 79",   "14 Yersin"),
    _act("8:30",  "Tham quan thác",  "Thác Datanla",          "Đèo Prenn"),
    _act("10:30", "Check out",        "Cozy Garden Boutique Hotel", "94 Đ. Lữ Gia"),
    _act("12:00", "Ăn trưa",         "Nem nướng Tân Long",    "290 Bùi Thị Xuân"),
    _act("14:00", "Cà phê",          "Cà phê Ollin",          "9 Nguyễn Chí Thanh"),
    _act("16:00", "Mua quà đặc sản", "Chợ Đà Lạt",            "Nguyễn Công Trứ"),
    _act("18:00", "Ăn tối chia tay", "Sườn cay khổng lồ",     "42 Phan Chu Trinh"),
]


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="")
    parser.add_argument("--seed", type=int, default=None)   # đã xử lý sớm ở đầu module
    args = parser.parse_args()

    cover = CoverData(
        background_path=_day_bg(NGAY_1_ACTIVITIES),
        month_tag="Tháng 6",
        handle_tag="@thamhiemdalat",
        location_tag="Đà Lạt",
        title="Soạn Plan đi Đà Lạt\ntháng 6",
        subtitle="Các mom cho em xin ý kiến nhé",
    )

    slides = [
        ItinerarySlide(_day_bg(NGAY_1_ACTIVITIES), 1, NGAY_1_ACTIVITIES),
        ItinerarySlide(_day_bg(NGAY_2_ACTIVITIES), 2, NGAY_2_ACTIVITIES),
        ItinerarySlide(_day_bg(NGAY_3_ACTIVITIES), 3, NGAY_3_ACTIVITIES),
    ]

    out_dir = Path(args.out) if args.out else Path(__file__).parent / "output" / "albums" / "demo_mye26"
    paths = render_album(cover, slides, str(out_dir), album_name="dalat_thang6")

    print(f"\n✓ Album tạo xong — {len(paths)} slides:")
    for p in paths:
        print(f"  file:///{Path(p).as_posix()}")


if __name__ == "__main__":
    main()
