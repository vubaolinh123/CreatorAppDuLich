"""news_youtube.py — Cào tin tức Đà Lạt từ YouTube (video + shorts) qua APIFY.
Theo từ khóa + hashtag, lấy mới nhất. Dùng actor streamers~youtube-scraper.
"""
from __future__ import annotations

import os
import json
from pathlib import Path

ACTOR = "streamers~youtube-scraper"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
POOL_FILE = DATA_DIR / "news_pool.json"

DEFAULT_KEYWORD = "tin tức Đà Lạt"
# Hashtag của user (#thongtuyen #dulich #dalat) + gợi ý thêm.
DEFAULT_HASHTAGS = [
    "#thongtuyen", "#dulich", "#dalat",
    "#dulichdalat", "#checkindalat", "#amthucdalat",
    "#langbiang", "#lamdong", "#tindalat", "#dalatnews",
]


def _thumb(it: dict) -> str:
    t = it.get("thumbnailUrl")
    if t:
        return t
    ths = it.get("thumbnails")
    if isinstance(ths, list) and ths:
        return ths[-1].get("url", "") if isinstance(ths[-1], dict) else ""
    return ""


def scrape_news(keyword: str = DEFAULT_KEYWORD, hashtags: list[str] | None = None,
                per_query: int = 6, upload_date: str = "month") -> dict:
    """Cào YouTube theo từ khóa + hashtag, gộp video + shorts, khử trùng, mới nhất trước."""
    tok = os.getenv("APIFY_API_KEY") or os.getenv("APIFY_TOKEN")
    if not tok:
        return {"success": False, "error": "Thiếu APIFY_API_KEY", "items": []}
    try:
        import requests
    except Exception:
        return {"success": False, "error": "requests chưa cài", "items": []}

    hashtags = hashtags if hashtags is not None else DEFAULT_HASHTAGS
    queries = [q for q in [keyword.strip(), " ".join(hashtags).strip()] if q]
    seen: dict[str, dict] = {}
    url = f"https://api.apify.com/v2/acts/{ACTOR}/run-sync-get-dataset-items?token={tok}"
    for q in queries:
        try:
            r = requests.post(url, timeout=240, json={
                "searchKeywords": q, "maxResults": per_query, "maxResultsShorts": per_query,
                "sortBy": "date", "uploadDate": upload_date,
            })
            data = r.json() if r.ok else []
        except Exception as e:
            print(f"[news] scrape lỗi '{q}': {e}")
            continue
        for it in (data if isinstance(data, list) else []):
            vurl = it.get("url") or ""
            if not vurl:
                continue
            vid = vurl.rstrip("/").rsplit("/", 1)[-1].split("?")[0]
            if vid in seen:
                continue
            seen[vid] = {
                "title": it.get("title", ""),
                "url": vurl,
                "date": it.get("date") or it.get("uploadDate") or "",
                "is_short": "/shorts/" in vurl,
                "channel": it.get("channelName") or it.get("channelUsername") or "",
                "views": it.get("viewCount") or it.get("views"),
                "duration": it.get("duration"),
                "thumbnail": _thumb(it),
            }
    items = sorted(seen.values(), key=lambda x: x.get("date") or "", reverse=True)
    return {"success": True, "items": items, "count": len(items)}


def save_pool(result: dict) -> None:
    import time
    try:
        POOL_FILE.parent.mkdir(parents=True, exist_ok=True)
        POOL_FILE.write_text(json.dumps(
            {"time": time.time(), "items": result.get("items", [])},
            ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[news] save pool lỗi: {e}")


def load_pool() -> dict:
    try:
        return json.loads(POOL_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"time": 0, "items": []}
