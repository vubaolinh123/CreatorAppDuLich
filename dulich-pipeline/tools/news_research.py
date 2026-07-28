"""
news_research.py — Lấy nội dung Đà Lạt từ TikTok/Facebook qua APIFY rồi để OpenRouter
viết kịch bản MỚI (tin tức / review). 2 chế độ: tự động quét kênh nguồn + thủ công dán link.
Nguồn (mô tả + subtitle EN) chỉ dùng làm INPUT; kịch bản đầu ra là tiếng Việt viết mới.
"""
from __future__ import annotations

import os
import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
APIFY_SYNC = "https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items?token={tok}"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def _apify(actor: str, inp: dict, timeout: int = 300):
    tok = os.getenv("APIFY_KEY_VIETCHINH")
    if not tok:
        print("[news] thiếu APIFY_KEY_VIETCHINH"); return []
    try:
        import requests
        r = requests.post(APIFY_SYNC.format(actor=actor, tok=tok), json=inp, timeout=timeout)
        if r.status_code not in (200, 201):
            print(f"[news] APIFY {actor} {r.status_code}: {r.text[:160]}"); return []
        return r.json()
    except Exception as e:
        print(f"[news] APIFY {actor} lỗi: {e}"); return []


def _subtitle_text(item: dict, limit: int = 1500) -> str:
    links = (item.get("videoMeta") or {}).get("subtitleLinks") or item.get("subtitleLinks") or []
    if not links:
        return ""
    try:
        import requests
        vtt = requests.get(links[0].get("downloadLink"), timeout=30).text
        out = [l.strip() for l in vtt.splitlines()
               if l.strip() and "-->" not in l and not l.strip().isdigit() and l.strip() != "WEBVTT"]
        return " ".join(out)[:limit]
    except Exception:
        return ""


def discover(channels: list[str], per: int = 5) -> list[dict]:
    items = _apify("clockworks~tiktok-scraper", {
        "profiles": channels, "resultsPerPage": per,
        "shouldDownloadVideos": False, "shouldDownloadCovers": False, "shouldDownloadSubtitles": False,
    })
    out = []
    for it in items:
        out.append({
            "text": it.get("text", ""), "views": it.get("playCount"),
            "date": it.get("createTimeISO", ""),
            "url": it.get("webVideoUrl") or it.get("submittedVideoUrl", ""),
            "author": (it.get("authorMeta") or {}).get("name", ""),
        })
    out.sort(key=lambda x: (x.get("date") or ""), reverse=True)
    return out


def scrape_tiktok(url: str) -> dict | None:
    items = _apify("clockworks~tiktok-scraper",
                   {"postURLs": [url], "resultsPerPage": 1, "shouldDownloadSubtitles": True})
    if not items:
        return None
    it = items[0]
    return {"url": url, "text": it.get("text", ""), "subtitle": _subtitle_text(it),
            "views": it.get("playCount"), "platform": "tiktok"}


def scrape_facebook(url: str) -> dict | None:
    items = _apify("apify~facebook-posts-scraper", {"startUrls": [{"url": url}], "resultsLimit": 1})
    if not items:
        return None
    it = items[0]
    return {"url": url, "text": it.get("text") or it.get("message") or "",
            "subtitle": "", "platform": "facebook"}


def build_script(content: str) -> dict | None:
    key = os.getenv("OPENROUTER_KEY") or os.getenv("OPENROUTER_API_KEY")
    if not key or not (content or "").strip():
        return None
    system = (
        "Bạn viết kịch bản video TikTok tiếng Việt cho kênh Đà Lạt (tin tức + review quán ăn / chỗ đi chơi). "
        "Dựa trên NỘI DUNG NGUỒN, viết 1 kịch bản MỚI (KHÔNG copy nguyên văn). "
        "Công thức: HOOK giá trị/tò mò ngay 10s đầu (người xem ĐL quan tâm) → triển khai → "
        "cài lịch trình / list cụ thể (địa điểm, giá nếu có) → CTA ngắn. "
        "Trả DUY NHẤT JSON {\"title\":\"...\",\"hook\":\"...\",\"body\":\"...\",\"cta\":\"...\"}. "
        "title = cụm ngắn in khung hook; hook = 1 câu; body 3-6 câu; cta 1 câu. Chỉ JSON."
    )
    try:
        import requests
        r = requests.post(OPENROUTER_URL, timeout=60,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": "openai/gpt-4o-mini",
                  "messages": [{"role": "system", "content": system},
                               {"role": "user", "content": f"NỘI DUNG NGUỒN:\n{content[:3000]}"}],
                  "response_format": {"type": "json_object"}, "temperature": 0.8})
        if r.status_code != 200:
            print(f"[news] OpenRouter {r.status_code}: {r.text[:160]}"); return None
        d = json.loads(r.json()["choices"][0]["message"]["content"])
        if not d.get("title") or not d.get("body"):
            return None
        return {"title": str(d.get("title", "")).strip()[:40], "hook": str(d.get("hook", "")).strip(),
                "body": str(d.get("body", "")).strip(),
                "cta": str(d.get("cta", "")).strip() or "Lưu lại và theo dõi kênh nhé!"}
    except Exception as e:
        print(f"[news] build_script lỗi: {e}"); return None


def research_auto() -> dict:
    try:
        cfg = json.loads((DATA_DIR / "news_sources.json").read_text(encoding="utf-8"))
    except Exception:
        cfg = {"channels": [], "results_per_channel": 5}
    vids = discover(cfg.get("channels", []), int(cfg.get("results_per_channel", 5)))
    if not vids:
        return {"success": False, "error": "Không cào được video từ APIFY (kiểm tra APIFY_KEY_VIETCHINH/credit)."}
    top = vids[0]
    detail = scrape_tiktok(top["url"]) or {}
    content = (top.get("text") or "") + "\n" + (detail.get("subtitle") or "")
    # Chỉ lấy 1 video mới nhất + trả link đó về (không cần cả list).
    return {"success": True, "mode": "auto", "sources": [top], "picked": top, "script": build_script(content)}


def research_manual(link: str) -> dict:
    link = (link or "").strip()
    if not link:
        return {"success": False, "error": "Thiếu link."}
    is_fb = any(x in link for x in ("facebook.com", "fb.com", "fb.watch"))
    s = scrape_facebook(link) if is_fb else scrape_tiktok(link)
    if not s or not (s.get("text") or s.get("subtitle")):
        return {"success": False, "error": "Không lấy được nội dung từ link (FB group kín / link sai)."}
    content = (s.get("text") or "") + "\n" + (s.get("subtitle") or "")
    return {"success": True, "mode": "manual",
            "sources": [{"url": link, "text": s.get("text", ""), "views": s.get("views")}],
            "picked": s, "script": build_script(content)}
