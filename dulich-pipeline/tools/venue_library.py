"""
venue_library.py — Thư viện quán/địa điểm Đà Lạt cho luồng content.
Nguồn dữ liệu: DATABASE (tools/venues_db.py → data/venues.json), admin sửa trong app.
CSV cũ (`data/venue_library.csv`) chỉ còn dùng để seed/backfill 1 lần.
"""
from __future__ import annotations

import csv
import unicodedata
from pathlib import Path

from tools import venues_db


def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s or "")


def _resolve_csv() -> Path:
    root = Path(__file__).resolve().parent.parent           # dulich-pipeline
    bundled = root / "data" / "venue_library.csv"
    if bundled.exists():
        return bundled
    return root.parent / "Claude - Format - Info.csv"


CSV_PATH = _resolve_csv()


def _map(v: dict) -> dict:
    """venues_db schema → schema mà content (listreview_content) cần."""
    return {
        "category": _nfc(v.get("loai_quan", "")),
        "inhouse": (v.get("loai", "") == "cần seeding"),
        "name": _nfc(v.get("name", "")),
        "address": _nfc(v.get("address", "")),
        "feature": _nfc(v.get("feature", "")),
        "signature": _nfc(v.get("signature", "")),
    }


def load_venues() -> list[dict]:
    """Tất cả địa điểm trong DB, map sang schema content."""
    return [_map(v) for v in venues_db.get_all()]


def seeding_venues() -> list[dict]:
    """Nhóm quán seeding (loai='cần seeding') — dùng cho content + ghim đầu thư viện."""
    return [_map(v) for v in venues_db.get_all() if v.get("loai") == "cần seeding"]


def inhouse_food(limit: int = 5) -> list[dict]:
    """Top `limit` quán ĂN seeding (nhóm cố định) để seeding content nv1."""
    foods = [v for v in seeding_venues() if v["category"].lower().startswith("quán ăn")]
    return foods[:limit]


# ── Backfill 1 lần: lấy 'Đặc điểm' từ CSV cũ điền vào DB cho venue đang thiếu ──
def backfill_feature_from_csv() -> int:
    """Đọc CSV cũ, match theo tên, điền feature cho venue thiếu. Trả số venue đã cập nhật."""
    if not CSV_PATH.exists():
        return 0
    feat_by_name: dict[str, str] = {}
    with open(CSV_PATH, encoding="utf-8") as f:
        for row in csv.reader(f):
            cells = (row + [""] * 10)[:10]
            name, address, feature = cells[2].strip(), cells[3].strip(), cells[4].strip()
            if name and address and address.lower() != "địa chỉ" and feature:
                feat_by_name[_nfc(name).lower()] = _nfc(feature)
    updated = 0
    for v in venues_db.get_all():
        if not (v.get("feature") or "").strip():
            feat = feat_by_name.get(_nfc(v.get("name", "")).lower())
            if feat:
                venues_db.save_venue({"id": v["id"], "feature": feat})
                updated += 1
    return updated


if __name__ == "__main__":
    print("backfilled:", backfill_feature_from_csv())
    for v in inhouse_food():
        print(v)
