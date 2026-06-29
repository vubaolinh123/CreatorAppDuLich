"""
venues_db.py — Thư viện quản lý địa điểm du lịch Đà Lạt.
Schema theo Google Sheet: Tên quán / Địa chỉ / Link ảnh / Loại / Có người / Loại quán.
Storage: data/venues.json
"""

from __future__ import annotations

import json
import os
import threading
import functools
import urllib.request
from pathlib import Path
from typing import Optional

DB_PATH    = Path(__file__).parent.parent / "data" / "venues.json"
THUMB_DIR  = Path(__file__).parent.parent / "data" / "thumbs"

# Khoá ghi: ThreadingHTTPServer có thể gọi mutate đồng thời (upload nhiều ảnh) → tránh trùng id/mất data.
_LOCK = threading.RLock()


def _locked(fn):
    @functools.wraps(fn)
    def _w(*a, **k):
        with _LOCK:
            return fn(*a, **k)
    return _w

LOAI_OPTIONS      = ("cần seeding", "không seeding")
CO_NGUOI_OPTIONS  = ("có", "không")
LOAI_QUAN_OPTIONS = ("quán ăn", "quán cà phê", "khách sạn", "tham quan")


# ── Internal ──────────────────────────────────────────────────────────────────

def _normalize(v: dict) -> dict:
    """Đảm bảo venue có đủ field mới: feature (str), images (list). Migrate image_path → images."""
    v.setdefault("feature", "")
    imgs = v.get("images")
    if not isinstance(imgs, list):
        old = (v.get("image_path") or "").strip()
        imgs = [old] if old else []
        v["images"] = imgs
    v["image_path"] = imgs[0] if imgs else ""   # giữ tương thích: ảnh đầu
    return v


def _load() -> dict:
    if DB_PATH.exists():
        with open(DB_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {"venues": [], "_next_id": 1}
    data["venues"] = [_normalize(v) for v in data.get("venues", [])]
    return data


def _save(data: dict) -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── CRUD ──────────────────────────────────────────────────────────────────────

@_locked
def add_venue(
    name: str,
    address: str,
    image_path: str = "",
    loai: str = "cần seeding",
    co_nguoi: str = "không",
    loai_quan: str = "quán ăn",
    signature: str = "",
    feature: str = "",
    fb_link: str = "",
    tiktok_link: str = "",
    google_map: str = "",
) -> dict:
    """Thêm địa điểm mới vào database."""
    data = _load()
    vid = data.get("_next_id", len(data["venues"]) + 1)
    venue = _normalize({
        "id": vid,
        "name": name,
        "address": address,
        "images": [image_path] if image_path else [],
        "loai": loai,
        "co_nguoi": co_nguoi,
        "loai_quan": loai_quan,
        "signature": signature,
        "feature": feature,
        "fb_link": fb_link,
        "tiktok_link": tiktok_link,
        "google_map": google_map,
    })
    data["venues"].append(venue)
    data["_next_id"] = vid + 1
    _save(data)
    return venue


# ── Upsert / delete / ảnh theo id ──────────────────────────────────────────────
_ALLOWED_FIELDS = ("name", "address", "loai", "loai_quan",
                   "signature", "feature", "fb_link", "tiktok_link", "google_map", "images")


@_locked
def save_venue(v: dict) -> dict:
    """Upsert theo id: có id + tồn tại → cập nhật; không → thêm mới (cấp id)."""
    data = _load()
    vid = v.get("id")
    if vid is not None:
        for cur in data["venues"]:
            if cur["id"] == vid:
                for k in _ALLOWED_FIELDS:
                    if k in v:
                        cur[k] = v[k]
                _normalize(cur)
                _save(data)
                return cur
    # thêm mới
    return add_venue(
        name=v.get("name", ""), address=v.get("address", ""),
        image_path="", loai=v.get("loai", "cần seeding"),
        co_nguoi=v.get("co_nguoi", "không"), loai_quan=v.get("loai_quan", "quán ăn"),
        signature=v.get("signature", ""), feature=v.get("feature", ""),
        fb_link=v.get("fb_link", ""), tiktok_link=v.get("tiktok_link", ""),
        google_map=v.get("google_map", ""),
    )


@_locked
def delete_by_id(vid: int) -> bool:
    data = _load()
    before = len(data["venues"])
    data["venues"] = [v for v in data["venues"] if v["id"] != vid]
    if len(data["venues"]) < before:
        _save(data)
        return True
    return False


@_locked
def add_image(vid: int, path: str) -> list:
    data = _load()
    for v in data["venues"]:
        if v["id"] == vid:
            if path not in v["images"]:
                v["images"].append(path)
            _normalize(v)
            _save(data)
            return v["images"]
    return []


@_locked
def remove_image(vid: int, path: str) -> list:
    data = _load()
    for v in data["venues"]:
        if v["id"] == vid:
            v["images"] = [p for p in v.get("images", []) if p != path]
            _normalize(v)
            _save(data)
            return v["images"]
    return []


def get_all() -> list:
    return _load()["venues"]


def get_venues(
    loai_quan: Optional[str] = None,
    loai: Optional[str] = None,
    co_nguoi: Optional[str] = None,
) -> list:
    """Lọc địa điểm theo tiêu chí."""
    venues = _load()["venues"]
    if loai_quan:
        venues = [v for v in venues if v.get("loai_quan") == loai_quan]
    if loai:
        venues = [v for v in venues if v.get("loai") == loai]
    if co_nguoi:
        venues = [v for v in venues if v.get("co_nguoi") == co_nguoi]
    return venues


def get_by_name(name: str) -> Optional[dict]:
    for v in _load()["venues"]:
        if v["name"] == name:
            return v
    return None


@_locked
def update_image(name: str, image_path: str) -> bool:
    """Cập nhật đường dẫn ảnh cho địa điểm."""
    data = _load()
    for v in data["venues"]:
        if v["name"] == name:
            v["image_path"] = image_path
            _save(data)
            return True
    return False


@_locked
def update_venue(name: str, **fields) -> bool:
    """Cập nhật bất kỳ field nào của địa điểm."""
    data = _load()
    for v in data["venues"]:
        if v["name"] == name:
            v.update(fields)
            _save(data)
            return True
    return False


@_locked
def delete_venue(name: str) -> bool:
    data = _load()
    before = len(data["venues"])
    data["venues"] = [v for v in data["venues"] if v["name"] != name]
    if len(data["venues"]) < before:
        _save(data)
        return True
    return False


# ── Image helpers ─────────────────────────────────────────────────────────────

def resolve_image(venue: dict) -> str:
    """
    Trả về local path ảnh của venue.
    Thứ tự ưu tiên: image_path local → download từ URL → placeholder.
    """
    img = venue.get("image_path", "")
    if img and os.path.exists(img):
        return img

    # Nếu image_path là URL → tải về
    if img and (img.startswith("http://") or img.startswith("https://")):
        return _download_image(img, venue["name"])

    return ""  # caller sẽ dùng placeholder


def _download_image(url: str, venue_name: str) -> str:
    THUMB_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = "".join(c if c.isalnum() or c in "._- " else "_" for c in venue_name)
    ext = url.split("?")[0].rsplit(".", 1)[-1] if "." in url.rsplit("/", 1)[-1] else "jpg"
    out = str(THUMB_DIR / f"{safe_name}.{ext}")
    if os.path.exists(out):
        return out
    try:
        urllib.request.urlretrieve(url, out)
        return out
    except Exception as e:
        print(f"[venues_db] Không tải được ảnh {venue_name}: {e}")
        return ""


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        venues = get_all()
        print(f"Database có {len(venues)} địa điểm:")
        for v in venues:
            print(f"  [{v['id']}] {v['name']} — {v['loai_quan']} — {v['address']}")
        sys.exit(0)

    cmd = sys.argv[1]
    if cmd == "list":
        for v in get_all():
            print(f"{v['id']}\t{v['name']}\t{v['loai_quan']}\t{v['loai']}")

    elif cmd == "add":
        name    = input("Tên quán: ")
        address = input("Địa chỉ: ")
        lq      = input("Loại quán (quán ăn/quán cà phê/khách sạn/tham quan): ") or "quán ăn"
        loai    = input("Cần seeding? (cần seeding/không seeding): ") or "cần seeding"
        co_ng   = input("Có người? (có/không): ") or "không"
        sig     = input("Món đặc trưng/ghi chú: ")
        img     = input("Link ảnh (URL hoặc path): ")
        v = add_venue(name, address, image_path=img, loai=loai,
                      co_nguoi=co_ng, loai_quan=lq, signature=sig)
        print(f"Đã thêm: {v}")
