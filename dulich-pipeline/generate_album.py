"""
generate_album.py — Tạo album lịch trình Mye26 từ trip plan JSON.

Cách dùng:
  python generate_album.py --trip trips/dalat_thang6.json
  python generate_album.py --trip trips/dalat_thang6.json --out output/custom_dir

Trip plan JSON format:
  {
    "album_name": "dalat_thang6",
    "cover": {
      "background_photo": "IMG_1584.JPG",   # tên file trong anh video du lich/
      "month_tag": "Tháng 6",
      "handle_tag": "@thamhiemdalat",
      "location_tag": "Đà Lạt",
      "title": "Soạn Plan đi Đà Lạt\\ntháng 6",
      "subtitle": "Các mom cho em xin ý kiến nhé"
    },
    "days": [
      {
        "day": 1,
        "background_photo": "IMG_1595.JPG",
        "activities": [
          {"time": "7:30", "activity": "Ăn sáng", "venue": "Sườn cay khổng lồ", "address": "42 Phan Chu Trinh"},
          ...
        ]
      }
    ]
  }

Thumbnail ảnh: hệ thống tự tìm trong venues_db.json (theo tên quán).
Nếu venues_db có image_path → dùng. Nếu là URL → tải về data/thumbs/.
"""

from __future__ import annotations

import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from tools.mye26_renderer import (
    CoverData, ActivityItem, ItinerarySlide, render_album,
)
from tools.venues_db import get_by_name, resolve_image

# Thư mục ảnh phong cảnh Đà Lạt
BASE    = Path(__file__).parent.parent.parent
ANH_DIR = BASE / "CreatorAppDuLich" / "anh video du lich"


def _find_bg(photo_name: str) -> str:
    """Tìm ảnh background — thử theo thứ tự: path đầy đủ → anh video du lich folder."""
    if not photo_name:
        return ""
    p = Path(photo_name)
    if p.exists():
        return str(p)
    for folder in (ANH_DIR, Path(__file__).parent):
        candidate = folder / p.name
        if candidate.exists():
            return str(candidate)
    print(f"[WARN] Không tìm được ảnh: {photo_name}")
    return ""


def _venue_thumbnail(venue_name: str) -> str:
    """Trả về local path ảnh thumbnail của venue từ DB. Rỗng nếu không có."""
    entry = get_by_name(venue_name)
    if entry:
        return resolve_image(entry)
    return ""


def main() -> None:
    parser = argparse.ArgumentParser(description="Tạo album lịch trình Mye26")
    parser.add_argument("--trip", required=True, help="Path đến file trip JSON")
    parser.add_argument("--out",  default="",  help="Thư mục output (default: output/albums/<album_name>)")
    args = parser.parse_args()

    trip_path = Path(args.trip)
    if not trip_path.exists():
        print(f"[ERROR] Không tìm thấy: {trip_path}")
        sys.exit(1)

    with open(trip_path, "r", encoding="utf-8") as f:
        trip = json.load(f)

    album_name = trip.get("album_name", "album")
    out_dir    = args.out or str(Path(__file__).parent / "output" / "albums" / album_name)

    # ── Cover ────────────────────────────────────────────────────────────────
    cov   = trip["cover"]
    cover = CoverData(
        background_path=_find_bg(cov.get("background_photo", "")),
        month_tag    = cov.get("month_tag",    "Tháng 6"),
        handle_tag   = cov.get("handle_tag",   "@thamhiemdalat"),
        location_tag = cov.get("location_tag", "Đà Lạt"),
        title        = cov.get("title",        ""),
        subtitle     = cov.get("subtitle",     ""),
    )

    # ── Day slides ────────────────────────────────────────────────────────────
    slides = []
    for day_data in trip.get("days", []):
        day_num = day_data["day"]
        bg      = _find_bg(day_data.get("background_photo", ""))

        activities = []
        for act in day_data.get("activities", []):
            venue_name = act.get("venue", "")
            activities.append(ActivityItem(
                time           = act.get("time", ""),
                activity       = act.get("activity", ""),
                venue          = venue_name,
                address        = act.get("address", ""),
                thumbnail_path = _venue_thumbnail(venue_name),
            ))

        slides.append(ItinerarySlide(bg, day_num, activities))

    # ── Render ────────────────────────────────────────────────────────────────
    paths = render_album(cover, slides, out_dir, album_name=album_name)

    print(f"\n✓ Album '{album_name}' — {len(paths)} slides:")
    for p in paths:
        print(f"  file:///{Path(p).as_posix()}")


if __name__ == "__main__":
    main()
