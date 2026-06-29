"""
build_venue_library.py

Đọc venues.json + danh sách mới từ research → xuất CSV thư viện.

Cách dùng:
  python build_venue_library.py --new-venues new_venues.json
  python build_venue_library.py  (không có file mới → chỉ rebuild CSV từ venues.json hiện có)
"""

import csv
import json
import sys
import argparse
from pathlib import Path

BASE = Path(__file__).parent
DB_PATH = BASE / "dulich-pipeline" / "data" / "venues.json"
OUT_CSV = BASE / "Thu vien dia diem Da Lat.csv"

# Thumbs có thể nằm ở 2 nơi: cùng thư mục (với ị) hoặc thư mục sibling (không ị)
_thumbs_a = BASE / "thumbs"
_thumbs_b = BASE.parent.parent / "he thong edit video du lich" / "CreatorAppDuLich" / "thumbs"
THUMBS_DIR = _thumbs_a if _thumbs_a.exists() else _thumbs_b

HEADERS = [
    "STT", "Loại", "Tên địa điểm", "Địa chỉ",
    "Đặc điểm", "Signature", "Link ảnh",
    "Link FB", "Link TikTok", "Link Google Maps",
    "Có mặt người", "Loại quán",
]

LOAI_QUAN_ORDER = ["quán ăn", "khách sạn", "quán cà phê", "tham quan"]


def thumb_rel(name: str) -> str:
    """Relative path đến ảnh thumbnail."""
    p = THUMBS_DIR / f"{name}.jpg"
    return f"thumbs/{name}.jpg" if p.exists() else ""


def venue_to_row(stt: int, v: dict) -> list:
    name = v.get("name", "")
    return [
        stt,
        v.get("loai", "Không seeding"),
        name,
        v.get("address", ""),
        v.get("description", v.get("mo_ta", "")),
        v.get("signature", v.get("price_range", "")),
        thumb_rel(name),
        v.get("fb_link", ""),
        v.get("tiktok_link", ""),
        v.get("google_map", ""),
        v.get("co_nguoi", "không"),
        v.get("loai_quan", ""),
    ]


def load_db() -> list:
    if not DB_PATH.exists():
        return []
    with open(DB_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("venues", [])


def save_db(venues: list):
    data = {"_next_id": max((v["id"] for v in venues), default=0) + 1, "venues": venues}
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[DB] Saved {len(venues)} venues → {DB_PATH}")


def merge_new_venues(existing: list, new_venues: list) -> list:
    existing_names = {v["name"] for v in existing}
    next_id = max((v["id"] for v in existing), default=0) + 1
    added = 0
    for nv in new_venues:
        if nv["name"] in existing_names:
            print(f"  [skip] {nv['name']} already exists")
            continue
        nv["id"] = next_id
        nv.setdefault("loai", "Không seeding")
        nv.setdefault("co_nguoi", "không")
        nv.setdefault("fb_link", "")
        nv.setdefault("tiktok_link", "")
        nv.setdefault("google_map", "")
        nv.setdefault("signature", nv.pop("price_range", ""))
        nv["image_path"] = str(THUMBS_DIR / f"{nv['name']}.jpg")
        # description → mo_ta alias (DB uses description key directly)
        existing.append(nv)
        existing_names.add(nv["name"])
        next_id += 1
        added += 1
        print(f"  [+] {nv['name']}")
    print(f"Merged: {added} new venues added")
    return existing


def build_csv(venues: list):
    # Sort by loai_quan order
    def sort_key(v):
        lq = v.get("loai_quan", "")
        try:
            lq_idx = LOAI_QUAN_ORDER.index(lq)
        except ValueError:
            lq_idx = 99
        # seeding trước
        seeding = 0 if v.get("loai", "") == "cần seeding" else 1
        return (lq_idx, seeding, v.get("name", ""))

    sorted_venues = sorted(venues, key=sort_key)

    with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(HEADERS)
        for i, v in enumerate(sorted_venues, 1):
            writer.writerow(venue_to_row(i, v))

    print(f"[CSV] Saved {len(sorted_venues)} venues → {OUT_CSV}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--new-venues", help="JSON file chứa list venues mới cần merge")
    args = parser.parse_args()

    venues = load_db()
    print(f"[DB] Loaded {len(venues)} existing venues")

    if args.new_venues:
        new_path = Path(args.new_venues)
        if not new_path.exists():
            print(f"[ERROR] File không tồn tại: {new_path}")
            sys.exit(1)
        with open(new_path, encoding="utf-8") as f:
            new_data = json.load(f)
        # Support both {"venues": [...]} and [...]
        new_list = new_data if isinstance(new_data, list) else new_data.get("venues", [])
        print(f"[NEW] {len(new_list)} venues to merge")
        venues = merge_new_venues(venues, new_list)
        save_db(venues)

    build_csv(venues)
    print("\nDone.")


if __name__ == "__main__":
    main()
