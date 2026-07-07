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


def zernio_tiktok_account() -> str | None:
    key = os.getenv("ZERNIO_KEY")
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


def post_to_tiktok(video_url: str, caption: str, account_id: str | None = None) -> dict:
    key = os.getenv("ZERNIO_KEY")
    if not key:
        return {"success": False, "error": "Thiếu ZERNIO_KEY"}
    acc = account_id or zernio_tiktok_account()
    if not acc:
        return {"success": False, "error": "Không tìm thấy tài khoản TikTok trong Zernio"}
    full = full_url(video_url)
    if not full.startswith("http"):
        return {"success": False, "error": "Video chưa có URL công khai (đặt PUBLIC_BASE_URL khi deploy VPS)"}
    body = {"content": caption or "",
            "mediaItems": [{"type": "video", "url": full}],
            "platforms": [{"platform": "tiktok", "accountId": acc}],
            "publishNow": True}
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
