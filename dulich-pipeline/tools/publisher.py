"""publisher.py — Đăng TikTok qua Zernio.

- Zernio: POST https://api.zernio.com/v1/posts (Bearer ZERNIO_KEY), publishNow.
LƯU Ý: Zernio cần URL video CÔNG KHAI. Chạy local (localhost) Zernio không tải được →
đặt PUBLIC_BASE_URL (vd https://app.mien.com) khi deploy VPS thì đăng mới chạy.
"""
from __future__ import annotations

import os

ZERNIO_POSTS = "https://api.zernio.com/v1/posts"
ZERNIO_ACCOUNTS = "https://api.zernio.com/v1/accounts"


def public_base() -> str:
    return (os.getenv("PUBLIC_BASE_URL") or "").rstrip("/")


def full_url(url: str) -> str:
    if not url:
        return ""
    if url.startswith("http"):
        return url
    b = public_base()
    return (b + url) if b else url


def zernio_tiktok_account(api_key: str | None = None) -> str | None:
    key = api_key or os.getenv("ZERNIO_KEY")
    if not key:
        return None
    try:
        import requests
        r = requests.get(ZERNIO_ACCOUNTS, headers={"Authorization": f"Bearer {key}"}, timeout=20)
        for a in (r.json() or {}).get("accounts", []):
            if a.get("platform") == "tiktok":
                return a.get("_id")
    except Exception as e:
        print(f"[pub] zernio accounts lỗi: {e}")
    return None


def _zernio_post(media_items: list, caption: str, api_key: str | None = None,
                 account_id: str | None = None, tiktok_settings: dict | None = None) -> dict:
    key = api_key or os.getenv("ZERNIO_KEY")
    if not key:
        return {"success": False, "error": "Thiếu Zernio key (Cài đặt → key theo tài khoản)"}
    acc = account_id or zernio_tiktok_account(key)
    if not acc:
        return {"success": False, "error": "Không tìm thấy tài khoản TikTok trong Zernio"}
    body = {"content": caption or "",
            "mediaItems": media_items,
            "platforms": [{"platform": "tiktok", "accountId": acc}],
            "publishNow": True}
    if tiktok_settings:
        body["tiktokSettings"] = tiktok_settings
    try:
        import requests
        r = requests.post(ZERNIO_POSTS, timeout=60,
                          headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                          json=body)
        if r.status_code in (200, 201):
            return {"success": True, "id": (r.json() or {}).get("_id", "")}
        return {"success": False, "error": f"Zernio {r.status_code}: {r.text[:200]}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def post_to_tiktok(video_url: str, caption: str, account_id: str | None = None,
                   api_key: str | None = None) -> dict:
    full = full_url(video_url)
    if not full.startswith("http"):
        return {"success": False, "error": "Video chưa có URL công khai (đặt PUBLIC_BASE_URL khi deploy VPS)"}
    return _zernio_post([{"type": "video", "url": full}], caption, api_key, account_id)


def post_images_to_tiktok(image_urls: list, caption: str,
                          api_key: str | None = None,
                          account_id: str | None = None) -> dict:
    """Đăng bộ ảnh (carousel) lên TikTok qua Zernio. Tối đa 10 ảnh."""
    items = []
    for u in image_urls[:10]:
        full = full_url(u)
        if not full.startswith("http"):
            return {"success": False, "error": "Ảnh chưa có URL công khai (đặt PUBLIC_BASE_URL khi deploy VPS)"}
        items.append({"type": "image", "url": full})
    if not items:
        return {"success": False, "error": "Album không có ảnh"}
    # TikTok bài ẢNH: bật auto-add-music để TikTok tự gắn nhạc gợi ý (không gắn nhạc theo link được).
    return _zernio_post(items, caption, api_key, account_id,
                        tiktok_settings={"autoAddMusic": True})


def list_tiktok_accounts(api_key: str | None = None) -> list:
    """Danh sách tài khoản TikTok dưới 1 key Zernio → [{id, name}]. 1 key có thể có nhiều acc."""
    key = api_key or os.getenv("ZERNIO_KEY")
    if not key:
        return []
    try:
        import requests
        r = requests.get(ZERNIO_ACCOUNTS, headers={"Authorization": f"Bearer {key}"}, timeout=20)
        out = []
        for a in (r.json() or {}).get("accounts", []):
            if a.get("platform") == "tiktok":
                out.append({"id": a.get("_id") or a.get("accountId") or "",
                            "name": a.get("displayName") or a.get("username") or a.get("name") or "TikTok"})
        return out
    except Exception as e:
        print(f"[pub] list_tiktok_accounts lỗi: {e}")
        return []
