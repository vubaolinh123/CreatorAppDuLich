"""publisher.py — Đăng TikTok qua Zernio + thông báo/duyệt qua Telegram group.

- Zernio: POST https://api.zernio.com/v1/posts (Bearer ZERNIO_KEY), publishNow.
- Telegram: sendMessage tới GROUP_ID kèm nút Duyệt/Hủy; poll callback ở server.
LƯU Ý: Zernio cần URL video CÔNG KHAI. Chạy local (localhost) Zernio không tải được →
đặt PUBLIC_BASE_URL (vd https://app.mien.com) khi deploy VPS thì đăng mới chạy.
"""
from __future__ import annotations

import os

ZERNIO_POSTS = "https://api.zernio.com/v1/posts"
ZERNIO_ACCOUNTS = "https://api.zernio.com/v1/accounts"


def _tg_token() -> str:
    return os.getenv("telegram_token") or os.getenv("TELEGRAM_TOKEN") or ""


def _group_id() -> str:
    return os.getenv("GROUP_ID") or os.getenv("TELEGRAM_GROUP_ID") or ""


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


# ── Telegram ──────────────────────────────────────────────────────────────────

def send_telegram(text: str, buttons: list | None = None) -> dict:
    tok, gid = _tg_token(), _group_id()
    if not (tok and gid):
        return {"success": False, "error": "Thiếu telegram_token/GROUP_ID"}
    payload = {"chat_id": gid, "text": text, "parse_mode": "HTML",
               "disable_web_page_preview": False}
    if buttons:
        payload["reply_markup"] = {"inline_keyboard": buttons}
    try:
        import requests
        r = requests.post(f"https://api.telegram.org/bot{tok}/sendMessage", json=payload, timeout=20)
        j = r.json()
        return {"success": bool(j.get("ok")), "message_id": (j.get("result") or {}).get("message_id"), "raw": j}
    except Exception as e:
        return {"success": False, "error": str(e)}


def send_telegram_video(path: str, caption: str, buttons: list | None = None) -> dict:
    """Gửi FILE video vào group (Bot API giới hạn ~50MB; quá cỡ → fallback gửi text)."""
    tok, gid = _tg_token(), _group_id()
    if not (tok and gid):
        return {"success": False, "error": "Thiếu telegram_token/GROUP_ID"}
    try:
        import os as _os, json as _json, requests
        if not path or not _os.path.exists(path) or _os.path.getsize(path) > 48 * 1024 * 1024:
            return send_telegram(caption + "\n(video quá 50MB — xem trong app)", buttons)
        data = {"chat_id": gid, "caption": caption[:1000], "parse_mode": "HTML"}
        if buttons:
            data["reply_markup"] = _json.dumps({"inline_keyboard": buttons})
        with open(path, "rb") as f:
            r = requests.post(f"https://api.telegram.org/bot{tok}/sendVideo",
                              data=data, files={"video": (_os.path.basename(path), f, "video/mp4")},
                              timeout=180)
        j = r.json()
        return {"success": bool(j.get("ok")), "message_id": (j.get("result") or {}).get("message_id"),
                "error": "" if j.get("ok") else str(j)[:200]}
    except Exception as e:
        return {"success": False, "error": str(e)}


def send_telegram_album(paths: list, caption: str, buttons: list | None = None) -> dict:
    """Gửi nhóm ảnh (tối đa 10) + 1 tin nhắn duyệt kèm nút (media group không gắn nút được)."""
    tok, gid = _tg_token(), _group_id()
    if not (tok and gid):
        return {"success": False, "error": "Thiếu telegram_token/GROUP_ID"}
    try:
        import os as _os, json as _json, requests
        paths = [p for p in (paths or []) if p and _os.path.exists(p)][:10]
        if paths:
            media, files = [], {}
            for i, p in enumerate(paths):
                key = f"ph{i}"
                media.append({"type": "photo", "media": f"attach://{key}",
                              **({"caption": caption[:1000], "parse_mode": "HTML"} if i == 0 else {})})
                files[key] = (_os.path.basename(p), open(p, "rb"), "image/png")
            try:
                requests.post(f"https://api.telegram.org/bot{tok}/sendMediaGroup",
                              data={"chat_id": gid, "media": _json.dumps(media)},
                              files=files, timeout=180)
            finally:
                for _, f, _m in files.values():
                    f.close()
        return send_telegram("👆 " + caption, buttons)   # tin nhắn mang nút Duyệt/Hủy
    except Exception as e:
        return {"success": False, "error": str(e)}


def edit_telegram(message_id, text: str) -> None:
    tok, gid = _tg_token(), _group_id()
    if not (tok and gid and message_id):
        return
    try:
        import requests
        requests.post(f"https://api.telegram.org/bot{tok}/editMessageText", timeout=20,
                      json={"chat_id": gid, "message_id": message_id, "text": text, "parse_mode": "HTML"})
    except Exception:
        pass


def answer_callback(cb_id: str, text: str = "") -> None:
    tok = _tg_token()
    if not (tok and cb_id):
        return
    try:
        import requests
        requests.post(f"https://api.telegram.org/bot{tok}/answerCallbackQuery", timeout=20,
                      json={"callback_query_id": cb_id, "text": text})
    except Exception:
        pass


def get_updates(offset: int) -> list:
    tok = _tg_token()
    if not tok:
        return []
    try:
        import requests
        r = requests.get(f"https://api.telegram.org/bot{tok}/getUpdates",
                         params={"offset": offset, "timeout": 25}, timeout=30)
        return (r.json() or {}).get("result", [])
    except Exception:
        return []
