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


if __name__ == "__main__":
    from dotenv import load_dotenv, find_dotenv
    load_dotenv(find_dotenv(usecwd=True))
    seeding = [v for v in venues_db.get_all() if v.get("loai") == "cần seeding"]
    for v in seeding:
        n = scrape_venue_images(v)
        print(f"{v['name']}: +{n} ảnh")
