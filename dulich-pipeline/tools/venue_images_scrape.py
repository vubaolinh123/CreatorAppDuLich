"""
venue_images_scrape.py — Lấy 3-10 ảnh cho 1 quán từ Google Maps qua APIFY (actor compass).
Tải ảnh về data/thumbs và gắn vào venues.json (venues_db.add_image).
"""
from __future__ import annotations

import urllib.request
from pathlib import Path

from tools import venues_db
from tools.news_research import _apify

THUMB_DIR = Path(__file__).parent.parent / "data" / "thumbs"
ACTOR = "compass~crawler-google-places"


def _query(venue: dict) -> str:
    name = (venue.get("name") or "").strip()
    addr = (venue.get("address") or "")
    city = "Đà Lạt" if "đà lạt" in addr.lower() or "đà lạt" not in name.lower() else ""
    return f"{name} {city}".strip()


def scrape_venue_images(venue: dict, max_images: int = 8) -> int:
    """Cào ảnh Google Maps cho 1 venue. Trả số ảnh đã thêm."""
    items = _apify(ACTOR, {
        "searchStringsArray": [_query(venue)],
        "maxCrawledPlacesPerSearch": 1,
        "maxImages": max_images,
        "language": "vi",
        "scrapeImageAuthors": False,
    })
    if not items:
        return 0
    urls = items[0].get("imageUrls") or []
    THUMB_DIR.mkdir(parents=True, exist_ok=True)
    vid = venue["id"]
    added = 0
    for i, u in enumerate(urls[:max_images]):
        if not isinstance(u, str):
            u = u.get("imageUrl", "")
        if not u:
            continue
        # ảnh Google photos: ép kích thước hợp lý
        dl = u + ("=w1024" if "googleusercontent" in u and "=" not in u.rsplit("/", 1)[-1] else "")
        dest = THUMB_DIR / f"{vid}_gm_{i}.jpg"
        try:
            req = urllib.request.Request(dl, headers={"User-Agent": "Mozilla/5.0"})
            data = urllib.request.urlopen(req, timeout=30).read()
            if len(data) < 3000:        # ảnh hỏng/quá nhỏ
                continue
            dest.write_bytes(data)
            venues_db.add_image(vid, f"data/thumbs/{dest.name}")
            added += 1
        except Exception as e:
            print(f"[scrape] tải ảnh lỗi {u[:50]}: {e}")
    return added


def _save_place_images(vid: int, urls: list, max_images: int = 8) -> int:
    """Tải ảnh của 1 place về data/thumbs, gắn vào venue. Trả số ảnh đã thêm."""
    THUMB_DIR.mkdir(parents=True, exist_ok=True)
    added = 0
    for i, u in enumerate((urls or [])[:max_images]):
        if not isinstance(u, str):
            u = u.get("imageUrl", "") if isinstance(u, dict) else ""
        if not u:
            continue
        dl = u + ("=w1024" if "googleusercontent" in u and "=" not in u.rsplit("/", 1)[-1] else "")
        dest = THUMB_DIR / f"{vid}_gm_{i}.jpg"
        try:
            req = urllib.request.Request(dl, headers={"User-Agent": "Mozilla/5.0"})
            data = urllib.request.urlopen(req, timeout=30).read()
            if len(data) < 3000:
                continue
            dest.write_bytes(data)
            venues_db.add_image(vid, f"data/thumbs/{dest.name}")
            added += 1
        except Exception as e:
            print(f"[scrape] tải ảnh lỗi {u[:50]}: {e}")
    return added


def _norm(name: str) -> str:
    return " ".join((name or "").strip().lower().split())


def discover_venues(search: str, loai_quan: str, want: int, max_images: int = 8,
                    accept_cats: list | None = None) -> list:
    """Tìm quán MỚI qua Google Maps (APIFY) theo 1 search term, gán vào loai_quan.
    Bỏ trùng tên với DB hiện có. accept_cats: nếu có, chỉ nhận place mà categoryName
    chứa 1 trong các từ này (lọc cho đúng loại). Thêm venue + tải ảnh. Trả list tên đã thêm."""
    items = _apify(ACTOR, {
        "searchStringsArray": [search],
        "maxCrawledPlacesPerSearch": max(want * 3, want + 5),
        "maxImages": max_images,
        "language": "vi",
        "scrapeImageAuthors": False,
    })
    existing = {_norm(v.get("name")) for v in venues_db.get_all()}
    out = []
    for it in items:
        if len(out) >= want:
            break
        name = (it.get("title") or "").strip()
        if not name or _norm(name) in existing:
            continue
        if accept_cats:
            cat = (it.get("categoryName") or "").lower()
            if not any(c in cat for c in accept_cats):
                continue
        addr = (it.get("address") or "").strip()
        v = venues_db.add_venue(name=name, address=addr, loai="không seeding",
                                co_nguoi="không", loai_quan=loai_quan)
        n_img = _save_place_images(v["id"], it.get("imageUrls") or [], max_images)
        existing.add(_norm(name))
        out.append(name)
        print(f"  + [{loai_quan}] {name} ({n_img} ảnh) — {addr[:40]}")
    return out


if __name__ == "__main__":
    from dotenv import load_dotenv, find_dotenv
    load_dotenv(find_dotenv(usecwd=True))
    seeding = [v for v in venues_db.get_all() if v.get("loai") == "cần seeding"]
    for v in seeding:
        n = scrape_venue_images(v)
        print(f"{v['name']}: +{n} ảnh")
