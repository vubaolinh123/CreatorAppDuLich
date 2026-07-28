"""
tiktok_photos.py — Tải bộ ảnh từ 1 bài ẢNH TikTok (photo post).
Thử yt-dlp trước; fail → fallback APIFY clockworks/tiktok-scraper (imagePost.images).
Trả list đường dẫn ảnh local (tối đa max_imgs), lưu trong temp dir do caller dọn.
"""
from __future__ import annotations
import os, sys, tempfile
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass


def _via_tikwm(url: str, tmp: Path, max_imgs: int) -> list[str]:
    """tikwm.com — API công khai chuyên lấy bộ ảnh photo post TikTok (nguồn chính)."""
    import requests
    r = requests.post("https://www.tikwm.com/api/", data={"url": url}, timeout=60)
    d = r.json() if r.ok else {}
    if d.get("code") != 0:
        print(f"[tiktok_photos] tikwm: {d.get('msg', r.status_code)}", file=sys.stderr)
        return []
    urls = (d.get("data") or {}).get("images") or []
    out = []
    for i, u in enumerate(urls[:max_imgs]):
        try:
            resp = requests.get(u, timeout=60)
            if resp.ok and len(resp.content) > 10000:
                p = tmp / f"tt_{i:02d}.jpg"
                p.write_bytes(resp.content)
                out.append(str(p))
        except Exception:
            pass
    return out


def _via_ytdlp(url: str, tmp: Path, max_imgs: int) -> list[str]:
    import yt_dlp
    opts = {"quiet": True, "outtmpl": str(tmp / "tt_%(autonumber)02d.%(ext)s"),
            "noplaylist": False, "playlist_items": f"1-{max_imgs}"}
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.extract_info(url, download=True)
    imgs = sorted(str(p) for p in tmp.iterdir()
                  if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"))
    return imgs[:max_imgs]


def _via_apify(url: str, tmp: Path, max_imgs: int) -> list[str]:
    import requests
    tok = os.getenv("APIFY_KEY_VIETCHINH")
    if not tok:
        return []
    r = requests.post(
        f"https://api.apify.com/v2/acts/clockworks~tiktok-scraper/run-sync-get-dataset-items?token={tok}",
        timeout=240, json={"postURLs": [url], "resultsPerPage": 1})
    if not r.ok:
        print(f"[tiktok_photos] APIFY {r.status_code}: {r.text[:150]}", file=sys.stderr)
        return []
    items = r.json() if isinstance(r.json(), list) else []
    urls = []
    for it in items:
        ip = it.get("imagePost") or {}
        for im in (ip.get("images") or []):
            u = im.get("imageURL", {}).get("urlList", [None])[0] if isinstance(im.get("imageURL"), dict) else im.get("imageURL") or im
            if isinstance(u, str):
                urls.append(u)
    out = []
    for i, u in enumerate(urls[:max_imgs]):
        try:
            resp = requests.get(u, timeout=60)
            if resp.ok:
                p = tmp / f"tt_apify_{i:02d}.jpg"
                p.write_bytes(resp.content)
                out.append(str(p))
        except Exception:
            pass
    return out


def download_photos(url: str, max_imgs: int = 3) -> tuple[list[str], str]:
    """Trả (list ảnh local, tmp_dir). Caller tự xóa tmp_dir khi xong."""
    tmp = Path(tempfile.mkdtemp(prefix="ttp_"))
    imgs = []
    try:
        imgs = _via_tikwm(url, tmp, max_imgs)
    except Exception as e:
        print(f"[tiktok_photos] tikwm fail ({str(e)[:120]})", file=sys.stderr)
    if not imgs:
        try:
            # yt-dlp không nhận /photo/ → đổi sang /video/ (chỉ lấy được cover)
            imgs = _via_ytdlp(url.replace("/photo/", "/video/"), tmp, max_imgs)
        except Exception as e:
            print(f"[tiktok_photos] yt-dlp fail ({str(e)[:120]})", file=sys.stderr)
    if not imgs:
        imgs = _via_apify(url, tmp, max_imgs)
    return imgs, str(tmp)
