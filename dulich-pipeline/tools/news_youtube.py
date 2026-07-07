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
# Từ khóa cào tin (chính thống + biến động thực tế) — user cung cấp.
DEFAULT_KEYWORDS = [
    "tin tức đà lạt", "thời sự đà lạt mới nhất", "tin tức lâm đồng hôm nay",
    "thời sự lâm đồng", "báo lâm đồng",
    "đà lạt hôm nay", "tình hình đà lạt mới nhất", "thời tiết đà lạt 24h qua",
    "giao thông đà lạt", "kẹt xe đà lạt", "sạt lở đà lạt", "ngập lụt đà lạt",
    "giá nông sản lâm đồng", "giá hoa đà lạt",
]
DEFAULT_HASHTAGS = [
    "#dalat", "#dalatnews", "#tintucdalat", "#thoisulamdong",
    "#dalathomnay", "#dulichdalat", "#LTV",
]
# Số keyword mỗi lần cào (giới hạn để tiết kiệm credit APIFY) — xoay vòng.
KEYWORDS_PER_RUN = 6


def _thumb(it: dict) -> str:
    t = it.get("thumbnailUrl")
    if t:
        return t
    ths = it.get("thumbnails")
    if isinstance(ths, list) and ths:
        return ths[-1].get("url", "") if isinstance(ths[-1], dict) else ""
    return ""


def _within_24h(iso_date: str) -> bool:
    """True nếu ngày đăng trong 24h qua. Không parse được → giữ (uploadDate=today đã lọc)."""
    if not iso_date:
        return True
    try:
        from datetime import datetime, timezone, timedelta
        s = iso_date.replace("Z", "+00:00")
        d = datetime.fromisoformat(s)
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - d) <= timedelta(hours=24)
    except Exception:
        return True


def _query_list() -> list[str]:
    """Xoay vòng KEYWORDS_PER_RUN keyword theo khung giờ + 1 combo hashtag."""
    import time
    lt = time.localtime()
    start = (lt.tm_hour * 60 + lt.tm_yday) % max(1, len(DEFAULT_KEYWORDS))
    picked = [DEFAULT_KEYWORDS[(start + i) % len(DEFAULT_KEYWORDS)] for i in range(min(KEYWORDS_PER_RUN, len(DEFAULT_KEYWORDS)))]
    picked.append(" ".join(DEFAULT_HASHTAGS))
    return picked


def scrape_news(keyword: str | None = None, hashtags: list[str] | None = None,
                per_query: int = 4, upload_date: str = "today", only_24h: bool = True) -> dict:
    """Cào YouTube tin Đà Lạt (video + shorts) theo nhiều từ khóa + hashtag, chỉ tin trong 24h."""
    tok = os.getenv("APIFY_API_KEY") or os.getenv("APIFY_TOKEN")
    if not tok:
        return {"success": False, "error": "Thiếu APIFY_API_KEY", "items": []}
    try:
        import requests
    except Exception:
        return {"success": False, "error": "requests chưa cài", "items": []}

    if keyword:  # cào 1 từ khóa cụ thể (từ UI)
        queries = [keyword.strip(), " ".join(hashtags if hashtags is not None else DEFAULT_HASHTAGS)]
    else:
        queries = _query_list()
    queries = [q for q in queries if q]

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
            dt = it.get("date") or it.get("uploadDate") or ""
            if only_24h and not _within_24h(dt):
                continue
            seen[vid] = {
                "title": it.get("title", ""), "url": vurl, "date": dt,
                "is_short": "/shorts/" in vurl,
                "channel": it.get("channelName") or it.get("channelUsername") or "",
                "views": it.get("viewCount") or it.get("views"),
                "duration": it.get("duration"), "thumbnail": _thumb(it),
            }
    items = sorted(seen.values(), key=lambda x: x.get("date") or "", reverse=True)
    return {"success": True, "items": items, "count": len(items), "queries": queries}


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
