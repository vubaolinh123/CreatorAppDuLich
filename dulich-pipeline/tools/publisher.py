"""publisher.py — Đăng TikTok qua Zernio.

- Zernio: POST https://api.zernio.com/v1/posts (Bearer ZERNIO_KEY), publishNow.
LƯU Ý: Zernio cần URL video CÔNG KHAI. Chạy local (localhost) Zernio không tải được →
đặt PUBLIC_BASE_URL (vd https://app.mien.com) khi deploy VPS thì đăng mới chạy.
"""
from __future__ import annotations

import os
from urllib.parse import quote

ZERNIO_BASE = (
    os.getenv("ZERNIO_API_BASE_URL") or "https://zernio.com/api/v1"
).rstrip("/")
ZERNIO_POSTS = f"{ZERNIO_BASE}/posts"
ZERNIO_ACCOUNTS = f"{ZERNIO_BASE}/accounts"


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


def _post_result(data: dict) -> dict:
    """Normalize create/retry responses from current and legacy Zernio APIs."""
    post = (
        data.get("post")
        or data.get("existingPost")
        or data.get("data")
        or data
    )
    if not isinstance(post, dict):
        post = {}
    platforms = post.get("platforms") if isinstance(post.get("platforms"), list) else []
    platform_url = next(
        (
            item.get("platformPostUrl")
            for item in platforms
            if isinstance(item, dict) and item.get("platformPostUrl")
        ),
        "",
    )
    return {
        "success": True,
        "id": post.get("_id") or post.get("id") or "",
        "provider_status": post.get("status") or "",
        "platform_url": platform_url,
        "provider_post": post,
        "deduplicated": bool(data.get("existingPost")),
    }


def _zernio_post(
    media_items: list,
    caption: str,
    api_key: str | None = None,
    account_id: str | None = None,
    tiktok_settings: dict | None = None,
    request_id: str = "",
) -> dict:
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
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }
        if request_id:
            headers["x-request-id"] = request_id
        r = requests.post(ZERNIO_POSTS, timeout=60,
                          headers=headers,
                          json=body)
        if r.status_code in (200, 201, 202):
            return _post_result(r.json() or {})
        return {"success": False, "error": f"Zernio {r.status_code}: {r.text[:200]}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def post_to_tiktok(video_url: str, caption: str, account_id: str | None = None,
                   api_key: str | None = None, request_id: str = "") -> dict:
    full = full_url(video_url)
    if not full.startswith("http"):
        return {"success": False, "error": "Video chưa có URL công khai (đặt PUBLIC_BASE_URL khi deploy VPS)"}
    return _zernio_post(
        [{"type": "video", "url": full}],
        caption,
        api_key,
        account_id,
        request_id=request_id,
    )


def post_images_to_tiktok(image_urls: list, caption: str,
                          api_key: str | None = None,
                          account_id: str | None = None,
                          request_id: str = "") -> dict:
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
                        tiktok_settings={"autoAddMusic": True},
                        request_id=request_id)


def get_zernio_post(post_id: str, api_key: str | None = None) -> dict:
    """Fetch the authoritative Zernio/platform status for one known post."""
    key = api_key or os.getenv("ZERNIO_KEY")
    if not key or not post_id:
        return {"success": False, "error": "Thiếu Zernio key hoặc post id."}
    try:
        import requests

        response = requests.get(
            f"{ZERNIO_POSTS}/{quote(str(post_id), safe='')}",
            headers={"Authorization": f"Bearer {key}"},
            timeout=30,
        )
        if response.status_code == 200:
            return _post_result(response.json() or {})
        return {
            "success": False,
            "http_status": response.status_code,
            "error": f"Zernio {response.status_code}: {response.text[:200]}",
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def retry_zernio_post(post_id: str, api_key: str | None = None) -> dict:
    """Retry only failed platforms of an existing Zernio post."""
    key = api_key or os.getenv("ZERNIO_KEY")
    if not key or not post_id:
        return {"success": False, "error": "Thiếu Zernio key hoặc post id."}
    try:
        import requests

        response = requests.post(
            f"{ZERNIO_POSTS}/{quote(str(post_id), safe='')}/retry",
            headers={"Authorization": f"Bearer {key}"},
            timeout=60,
        )
        if response.status_code in (200, 201, 202):
            return _post_result(response.json() or {})
        return {
            "success": False,
            "error": f"Zernio {response.status_code}: {response.text[:200]}",
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def list_tiktok_accounts(api_key: str | None = None) -> list:
    """Tài khoản TikTok dưới 1 key Zernio → [{id, handle, name}].

    `handle` (@username) là thứ admin dùng để nhận ra kênh; `displayName` có thể
    là bất cứ gì ("Thành chưa đổi tên") nên chỉ dùng làm chú thích."""
    key = api_key or os.getenv("ZERNIO_KEY")
    if not key:
        return []
    try:
        import requests
        r = requests.get(ZERNIO_ACCOUNTS, headers={"Authorization": f"Bearer {key}"}, timeout=20)
        out = []
        for a in (r.json() or {}).get("accounts", []):
            if a.get("platform") != "tiktok":
                continue
            username = (a.get("username") or "").strip().lstrip("@")
            display = (a.get("displayName") or a.get("name") or "").strip()
            out.append({
                "id": a.get("_id") or a.get("accountId") or "",
                "handle": f"@{username}" if username else "",
                "name": display or (f"@{username}" if username else "TikTok"),
            })
        return out
    except Exception as e:
        print(f"[pub] list_tiktok_accounts lỗi: {e}")
        return []
