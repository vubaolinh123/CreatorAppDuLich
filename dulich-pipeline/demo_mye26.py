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

def _act_v(time, activity, venue: dict):
    """ActivityItem từ 1 venue trong thư viện (tên + địa chỉ + thumbnail random)."""
    addr = (venue.get("address") or "").split(",")[0].strip()
    return ActivityItem(time, activity, venue["name"], addr,
                        thumbnail_path=VenuePicker.image(venue))

# ── Pool venue theo loại, tách seeding / thường để đưa seeding vào bữa hợp lý ──
_POOLS: dict = {}

def _catpool(category: str) -> dict:
    p = _POOLS.get(category)
    if not p:
        cands = [v for v in get_all() if (v.get("loai_quan") or "").strip() == category]
        if category == "tham quan":   # gộp thêm cà phê cho phong phú điểm chơi
            cands += [v for v in get_all() if (v.get("loai_quan") or "").strip() == "quán cà phê"]
        _rnd.shuffle(cands)
        p = _POOLS[category] = {"seed": [v for v in cands if VenuePicker.is_seeding(v)],
                                "rest": [v for v in cands if not VenuePicker.is_seeding(v)]}
    return p

def _pick(category: str, prefer_seeding: bool = False) -> dict:
    """Bốc 1 venue. prefer_seeding=True → ưu tiên quán seeding trước (dành cho bữa tối / check-in);
    False → lấy quán thường trước, để dành seeding cho slot phù hợp."""
    p = _catpool(category)
    for key in (("seed", "rest") if prefer_seeding else ("rest", "seed")):
        if p[key]:
            return p[key].pop()
    return {"name": "Đà Lạt", "address": "Đà Lạt", "images": []}

# ── Lịch trình 3 ngày: khung giờ giữ nguyên, QUÁN random từ thư viện ──────────
_DAY_SLOTS = [
    [("7:30", "Ăn sáng", "quán ăn"), ("9:00", "Check-in", "khách sạn"),
     ("11:30", "Ăn trưa", "quán ăn"), ("14:00", "Tham quan", "tham quan"),
     ("17:00", "Chill chiều", "tham quan"), ("19:00", "Ăn tối", "quán ăn"),
     ("20:30", "Dạo phố đêm", "tham quan")],
    [("7:00", "Ăn sáng sớm", "quán ăn"), ("8:30", "Check-in view đẹp", "khách sạn"),
     ("10:00", "Cà phê", "tham quan"), ("12:00", "Ăn trưa", "quán ăn"),
     ("14:30", "Tham quan", "tham quan"), ("17:30", "Mua đặc sản", "tham quan"),
     ("19:00", "Ăn tối", "quán ăn")],
    [("7:00", "Ăn sáng", "quán ăn"), ("8:30", "Tham quan", "tham quan"),
     ("10:30", "Check out", "khách sạn"), ("12:00", "Ăn trưa", "quán ăn"),
     ("14:00", "Cà phê chill", "tham quan"), ("16:00", "Mua quà đặc sản", "tham quan"),
     ("18:00", "Ăn tối chia tay", "quán ăn")],
]

def _build_day(slots):
    # Seeding vào bữa hợp lý: khách sạn → check-in; quán ăn 'tối' → bữa tối. Sáng/trưa/tham quan: quán thường.
    out = []
    for t, act, cat in slots:
        prefer = (cat == "khách sạn") or (cat == "quán ăn" and "tối" in act.lower())
        out.append(_act_v(t, act, _pick(cat, prefer)))
    return out

NGAY_1_ACTIVITIES = _build_day(_DAY_SLOTS[0])
NGAY_2_ACTIVITIES = _build_day(_DAY_SLOTS[1])
NGAY_3_ACTIVITIES = _build_day(_DAY_SLOTS[2])


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="")
    parser.add_argument("--seed", type=int, default=None)   # đã xử lý sớm ở đầu module
    args = parser.parse_args()

    from tools.album_titles import ai_cover_texts
    texts = ai_cover_texts("le1", {
        "title": "Soạn Plan đi Đà Lạt tháng 6",
        "subtitle": "Các mom cho em xin ý kiến nhé",
        "month_tag": "Tháng 6",
    })
    cover = CoverData(
        background_path=_day_bg(NGAY_1_ACTIVITIES),
        month_tag=texts["month_tag"],
        handle_tag="@thamhiemdalat",
        location_tag="Đà Lạt",
        title=texts["title"],
        subtitle=texts["subtitle"],
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
