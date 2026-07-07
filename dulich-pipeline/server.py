"""
server.py — Local HTTP server for browser-mode video assembly.
Receives scene files via multipart/form-data, runs FFmpeg assembly,
and returns the path to the finished video.

Run:
    cd dulich-pipeline
    python server.py

Default port: 7788
"""

from __future__ import annotations

import os
import sys
import json
import uuid
import shutil
import tempfile
import threading
import subprocess
from pathlib import Path
from http.server import HTTPServer, ThreadingHTTPServer, BaseHTTPRequestHandler

# Configure UTF-8 encoding for Windows console to avoid print crashes
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Load .env (keys: OPENROUTER_KEY, VBEE_APP_ID, VBEE_API_KEY, ...) for all handlers.
_DOTENV_PATH = ""
try:
    from dotenv import load_dotenv, find_dotenv
    _DOTENV_PATH = find_dotenv(usecwd=True)   # file .env thực sự đang load (có thể ở thư mục cha)
    load_dotenv(_DOTENV_PATH)
except Exception:
    pass

# ── Cài đặt API key trong app (trang Settings) ──────────────────────────────
# Ghi đúng file .env đang được load; nếu chưa có thì dùng .env cạnh server.py.
ENV_PATH = Path(_DOTENV_PATH) if _DOTENV_PATH else (Path(__file__).parent / ".env")

# Thư mục ảnh địa điểm (upload/cào) + kho ảnh chung
THUMB_DIR = Path(__file__).parent / "data" / "thumbs"
ALBUM_DIR = Path(__file__).parent / "data" / "album"

# ── Tạo ảnh (8 album template) — mỗi cái là 1 script CLI dựng slide PNG ────────
# script: tên file CLI; seed: script có nhận --seed (random hoá) không; label: tên hiển thị.
IMAGE_ALBUMS = {
    "hien1": {"script": "generate_hien25111.py", "seed": True,  "label": "Hiền · Lưới quán"},
    "hien2": {"script": "generate_hien21113.py", "seed": True,  "label": "Hiền · Bộ sưu tập"},
    "le1":   {"script": "demo_mye26.py",          "seed": False, "label": "Lê · Mẫu Đà Lạt"},
    "le2":   {"script": "generate_le2.py",        "seed": False, "label": "Lê · Cover + slide"},
    "muoi1": {"script": "generate_muoi1912.py",   "seed": True,  "label": "Mười · Album 1"},
    "muoi2": {"script": "generate_muoi1311.py",   "seed": True,  "label": "Mười · Album 2"},
    "vy1":   {"script": "generate_vy1.py",        "seed": True,  "label": "Vy · Album 1"},
    "vy2":   {"script": "generate_hien19111.py",  "seed": True,  "label": "Vy · Album 2"},
    # uyen1/uyen2: user đang sửa script, cập nhật sau.
}


def _albums_for(user: str) -> list:
    """Album hiển thị theo tài khoản: admin → tất cả; nhân viên → theo handle (users.json 'album')."""
    items = [{"id": k, "label": v["label"]} for k, v in IMAGE_ALBUMS.items()]
    u = (_load_users().get(user) or {})
    if u.get("role") == "admin":
        return items
    handle = (u.get("album") or "").lower()
    return [it for it in items if handle and it["id"].startswith(handle)]


_ALBUM_SEED_FILE = Path(__file__).parent / "data" / "album_seed_history.json"
_ALBUM_SEED_LOCK = threading.Lock()


def _recent_seeds(album: str, n: int = 10) -> list:
    try:
        d = json.loads(_ALBUM_SEED_FILE.read_text(encoding="utf-8"))
    except Exception:
        d = {}
    return (d.get(album) or [])[-n:]


def _remember_seed(album: str, seed: int) -> None:
    with _ALBUM_SEED_LOCK:
        try:
            d = json.loads(_ALBUM_SEED_FILE.read_text(encoding="utf-8"))
        except Exception:
            d = {}
        lst = d.get(album) or []
        lst.append(seed)
        d[album] = lst[-20:]
        _ALBUM_SEED_FILE.parent.mkdir(parents=True, exist_ok=True)
        _ALBUM_SEED_FILE.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def _generate_album(album: str, user: str = "", auto: bool = False) -> dict:
    """Chạy script CLI dựng 1 album ảnh (tránh lặp seed 10 lần gần nhất), lưu record. Dùng chung
    cho endpoint /assemble-image và bộ tự tạo ảnh hàng ngày."""
    cfg = IMAGE_ALBUMS.get(album)
    if not cfg:
        return {"success": False, "error": f"Album không hợp lệ: {album}"}
    base = Path(__file__).parent
    script_abs = base / cfg["script"]
    if not script_abs.exists():
        return {"success": False, "error": f"Thiếu script: {cfg['script']}"}

    out_dir = base / "output" / "albums" / f"app_{album}_{uuid.uuid4().hex[:8]}"
    out_dir.mkdir(parents=True, exist_ok=True)

    cmd = [sys.executable, str(script_abs), "--out", str(out_dir)]
    seed = None
    if cfg.get("seed"):
        import random
        recent = set(_recent_seeds(album))
        for _ in range(20):
            seed = random.randint(1, 999999)
            if seed not in recent:
                break
        cmd += ["--seed", str(seed)]

    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    try:
        with _HEAVY_LOCK:
            proc = subprocess.run(cmd, cwd=str(base), env=env,
                                  capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", timeout=300)
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Quá thời gian (300s)."}

    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip()[-1200:]
        print(f"[Server] ❌ tạo ảnh {album} lỗi (rc={proc.returncode}):\n{tail}", file=sys.stderr)
        return {"success": False, "error": tail or "Script lỗi"}

    files = sorted(out_dir.glob("*.png"))
    if not files:
        return {"success": False, "error": "Script chạy xong nhưng không có ảnh PNG."}

    if seed is not None:
        _remember_seed(album, seed)

    images = [{"name": f.name, "url": _to_output_url(str(f))} for f in files]
    dir_rel = str(out_dir.relative_to(base)).replace("\\", "/")
    rec = {"user": user, "album": album, "label": cfg.get("label", album),
           "dir": dir_rel, "images": images, "auto": auto}
    try:
        import time as _t
        _append_album({**rec, "time": _t.time()})
    except Exception as _e:
        print(f"[Server] album log lỗi: {_e}", file=sys.stderr)
    return {"success": True, **rec}


# Danh sách key cho trang Cài đặt. Tất cả TÙY CHỌN — thiếu vẫn chạy free.
SETTINGS_KEYS = [
    {"key": "OPENROUTER_KEY",    "label": "OpenRouter",      "group": "AI viết kịch bản",
     "desc": "AI tự viết script cho nv1. Thiếu → dùng nội dung mẫu/clone.", "link": "https://openrouter.ai/keys"},
    {"key": "APIFY_API_KEY",     "label": "Apify",           "group": "Tin tức",
     "desc": "Quét TikTok/Facebook cho luồng tin tức. Thiếu → không tự quét.", "link": "https://console.apify.com/account/integrations"},
    {"key": "VBEE_API_KEY",      "label": "Vbee API key",    "group": "Giọng đọc",
     "desc": "Giọng tiếng Việt xịn hơn gTTS.", "link": "https://vbee.vn"},
    {"key": "VBEE_APP_ID",       "label": "Vbee App ID",     "group": "Giọng đọc",
     "desc": "Đi kèm Vbee API key.", "link": "https://vbee.vn"},
    {"key": "ELEVENLABS_API_KEY","label": "ElevenLabs",      "group": "Giọng đọc",
     "desc": "Giọng/voice clone. Thiếu → fallback gTTS/Edge (free).", "link": "https://elevenlabs.io/app/settings/api-keys"},
    {"key": "PEXELS_API_KEY",    "label": "Pexels",          "group": "Phần Ảnh (sắp ra mắt)",
     "desc": "Ảnh stock cho module ảnh. Free tier.", "link": "https://www.pexels.com/api/"},
    {"key": "GEMINI_API_KEY",    "label": "Gemini",          "group": "Phần Ảnh (sắp ra mắt)",
     "desc": "AI vision dựng khung ảnh.", "link": "https://aistudio.google.com/apikey"},
    {"key": "OPENAI_API_KEY",    "label": "OpenAI",          "group": "Khác",
     "desc": "TTS/Vision OpenAI.", "link": "https://platform.openai.com/api-keys"},
    {"key": "MONGO_URI",         "label": "MongoDB URI",     "group": "Khác",
     "desc": "Lưu DB. Thiếu → tự dùng file mock.", "link": ""},
]
_SETTINGS_ALLOWED = {k["key"] for k in SETTINGS_KEYS}
_ENV_LOCK = threading.Lock()


def _env_is_set(key: str) -> bool:
    v = (os.getenv(key) or "").strip()
    return bool(v) and not v.lower().startswith("your-")


def _update_env(updates: dict) -> None:
    """Ghi/cập nhật các cặp KEY=value vào file .env và os.environ (hiệu lực ngay)."""
    with _ENV_LOCK:
        lines = ENV_PATH.read_text(encoding="utf-8").splitlines() if ENV_PATH.exists() else []
        seen, out = set(), []
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                k = stripped.split("=", 1)[0].strip()
                if k in updates:
                    out.append(f"{k}={updates[k]}")
                    seen.add(k)
                    continue
            out.append(line)
        for k, v in updates.items():
            if k not in seen:
                out.append(f"{k}={v}")
        ENV_PATH.write_text("\n".join(out) + "\n", encoding="utf-8")
        for k, v in updates.items():
            os.environ[k] = v

PORT = 7788
UPLOAD_TEMP_DIR = Path(__file__).parent / "output" / "temp_uploads"
UPLOAD_TEMP_DIR.mkdir(parents=True, exist_ok=True)

WEB_INDEX = Path(__file__).parent / "web" / "index.html"

# Serialize heavy operations (script gen / assembly) so the threaded server can
# still answer health checks + serve files while one render is running.
_HEAVY_LOCK = threading.Lock()

# No API keys in this demo → default voice engine is free Microsoft Edge TTS (vi-VN).
os.environ.setdefault("VOICE_PROVIDER", "edge")


def _to_output_url(abs_path: str) -> str:
    """Convert an absolute output file path into a URL servable by GET /output/..."""
    if not abs_path:
        return ""
    try:
        rel = os.path.relpath(abs_path, str(Path(__file__).parent))
        return "/" + rel.replace("\\", "/")
    except Exception:
        return ""


def _derive_title(topic: str) -> str:
    """Pull a short, big hook title (place name) out of the topic. Uppercased, editable in UI."""
    import re
    t = (topic or "").splitlines()[0].strip()
    for filler in ["khám phá", "kham pha", "một ngày ở", "mot ngay o", "review",
                   "du lịch", "du lich", "trải nghiệm", "trai nghiem", "ghé thăm", "ghé", "đi "]:
        t = re.sub(filler, "", t, flags=re.IGNORECASE)
    t = t.strip(" -–—,.")
    words = t.split()
    if len(words) > 3:
        t = " ".join(words[:3])
    return (t or topic).strip().upper()[:18]


USERS_FILE = Path(__file__).parent / "data" / "users.json"
PRODUCTS_FILE = Path(__file__).parent / "output" / "products.json"
_PROD_LOCK = threading.Lock()

# Supabase client (lazy init)
_supabase_client = None


def _get_supabase():
    """Get or create Supabase client."""
    global _supabase_client
    if _supabase_client is None:
        try:
            from tools.supabase_client import get_supabase
            _supabase_client = get_supabase()
        except Exception as e:
            print(f"[Server] Supabase init error: {e}", file=sys.stderr)
    return _supabase_client


def _load_users() -> dict:
    """Load users from Supabase, fallback to local file."""
    try:
        sb = _get_supabase()
        if sb and sb.url:
            users = sb.get_users()
            if users:
                return {u["username"]: u for u in users}
    except Exception as e:
        print(f"[Server] Supabase users load error: {e}", file=sys.stderr)
    # Fallback to local file
    try:
        return json.loads(USERS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _load_products() -> list:
    try:
        return json.loads(PRODUCTS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _append_product(rec: dict) -> None:
    rec.setdefault("status", "pending")   # pending(chưa duyệt) | posted(đã đăng) | failed(đăng lỗi) | cancelled(hủy)
    with _PROD_LOCK:
        items = _load_products()
        items.append(rec)
        PRODUCTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        PRODUCTS_FILE.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def _set_product_status(key: str, status: str) -> bool:
    """Đổi status 1 video theo video_url. Trả True nếu tìm thấy."""
    with _PROD_LOCK:
        items = _load_products()
        hit = False
        for p in items:
            if p.get("video_url") == key:
                p["status"] = status
                hit = True
        if hit:
            PRODUCTS_FILE.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
        return hit


def _friendly_error(e) -> str:
    """Đổi lỗi kỹ thuật thành thông báo ngắn dễ hiểu (kèm 1 dòng chi tiết cuối)."""
    s = str(e or "")
    low = s.lower()
    if "quá thời gian" in low or "timeout" in low:
        cause = "⏱ Render quá lâu — source có thể quá nặng/hỏng. Thử clip nhẹ hơn."
    elif "ffmpeg" in low and ("not found" in low or "winerror 2" in low or "no such file" in low):
        cause = "⚙ Chưa cài FFmpeg (hoặc chưa có trong PATH)."
    elif "ffmpeg" in low or "moov atom" in low or "invalid data" in low:
        cause = "🎞 Source không đọc được (file hỏng / định dạng không hỗ trợ). Thử file khác."
    elif "thiếu vo" in low or "không render được segment" in low:
        cause = "🔇 Thiếu lời thoại — kiểm tra các scene đã có nội dung chưa."
    elif "openrouter" in low or "openai" in low and ("401" in low or "key" in low):
        cause = "🔑 API key AI lỗi/thiếu — vào Cài đặt kiểm tra OpenRouter/OpenAI."
    elif "vbee" in low:
        cause = "🎙 Vbee lỗi — kiểm tra VBEE_API_KEY trong Cài đặt (đã tự chuyển giọng free)."
    elif "apify" in low:
        cause = "🔑 APIFY lỗi/hết credit — kiểm tra key trong Cài đặt."
    elif "no space" in low or "disk" in low:
        cause = "💾 Hết dung lượng ổ đĩa."
    elif "connection" in low or "getaddrinfo" in low or "ssl" in low:
        cause = "🌐 Lỗi mạng — kiểm tra Internet rồi thử lại."
    else:
        cause = "❌ Server gặp lỗi khi xử lý."
    detail = s.strip().splitlines()[-1][:160] if s.strip() else ""
    return f"{cause}" + (f"\nChi tiết: {detail}" if detail else "")


# ── Đăng bài (Zernio TikTok) + Telegram duyệt ───────────────────────────────
_TG_PENDING: dict = {}
_TG_LOCK = threading.Lock()


def _is_publish_user(user: str) -> bool:
    u = _load_users().get(user) or {}
    return (u.get("publish") or "").lower() == "tiktok"


def _caption_for(topic: str) -> str:
    tags = "#dalat #dulichdalat #reviewdalat #amthucdalat #checkindalat"
    topic = (topic or "").strip()
    return f"{topic}\n{tags}" if topic else tags


def _do_publish(video_url: str, caption: str, user: str) -> dict:
    """Đăng TikTok qua Zernio + cập nhật status product."""
    try:
        from tools import publisher
        res = publisher.post_to_tiktok(video_url, caption)
    except Exception as e:
        res = {"success": False, "error": str(e)}
    _set_product_status(video_url, "posted" if res.get("success") else "failed")
    return res


def _notify_publish(user: str, topic: str, video_url: str) -> None:
    """Gửi Telegram group nút Duyệt/Hủy cho video của nhân viên publish."""
    if not _is_publish_user(user):
        return
    try:
        from tools import publisher
        import uuid as _u
        pid = _u.uuid4().hex[:10]
        with _TG_LOCK:
            _TG_PENDING[pid] = {"video_url": video_url, "caption": _caption_for(topic), "user": user}
        txt = f"🆕 <b>{(topic or 'Video mới')}</b>\nNhân viên: {user}\nDuyệt để đăng TikTok."
        r = publisher.send_telegram(txt, buttons=[[
            {"text": "✅ Duyệt & đăng", "callback_data": f"post:{pid}"},
            {"text": "✕ Hủy", "callback_data": f"cancel:{pid}"}]])
        with _TG_LOCK:
            if pid in _TG_PENDING:
                _TG_PENDING[pid]["message_id"] = r.get("message_id")
    except Exception as e:
        print(f"[pub] notify lỗi: {e}", file=sys.stderr)


def _telegram_poller():
    """Poll callback Telegram: Duyệt → đăng TikTok; Hủy → cancelled."""
    import time as _t
    from tools import publisher
    offset = 0
    while True:
        try:
            for up in publisher.get_updates(offset):
                offset = up.get("update_id", offset) + 1
                cb = up.get("callback_query")
                if not cb:
                    continue
                data = cb.get("data", "")
                cbid = cb.get("id", "")
                if ":" not in data:
                    publisher.answer_callback(cbid)
                    continue
                act, pid = data.split(":", 1)
                with _TG_LOCK:
                    pend = _TG_PENDING.get(pid)
                if not pend:
                    publisher.answer_callback(cbid, "Đã xử lý / hết hạn")
                    continue
                if act == "post":
                    res = _do_publish(pend["video_url"], pend["caption"], pend["user"])
                    ok = res.get("success")
                    publisher.answer_callback(cbid, "Đã đăng TikTok" if ok else "Đăng lỗi")
                    publisher.edit_telegram(pend.get("message_id"),
                        (f"✅ Đã đăng TikTok — NV {pend['user']}" if ok
                         else f"⚠ Đăng lỗi: {res.get('error','')} — NV {pend['user']}"))
                elif act == "cancel":
                    _set_product_status(pend["video_url"], "cancelled")
                    publisher.answer_callback(cbid, "Đã hủy")
                    publisher.edit_telegram(pend.get("message_id"), f"✕ Đã hủy — NV {pend['user']}")
                with _TG_LOCK:
                    _TG_PENDING.pop(pid, None)
        except Exception as e:
            print(f"[tg] poller lỗi: {e}", file=sys.stderr)
        _t.sleep(2)


def _start_telegram_poller():
    if os.getenv("telegram_token") or os.getenv("TELEGRAM_TOKEN"):
        threading.Thread(target=_telegram_poller, daemon=True).start()
        print("[Server] Telegram poller bật.", file=sys.stderr)


# Album ảnh đã tạo — lưu lại như "Tất cả video" (mở lại / xoá / tạo lại).
ALBUM_PRODUCTS_FILE = Path(__file__).parent / "output" / "album_products.json"
_ALBUM_PROD_LOCK = threading.Lock()


def _load_albums() -> list:
    try:
        return json.loads(ALBUM_PRODUCTS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _append_album(rec: dict) -> None:
    rec.setdefault("status", "pending")
    with _ALBUM_PROD_LOCK:
        items = _load_albums()
        items.append(rec)
        ALBUM_PRODUCTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        ALBUM_PRODUCTS_FILE.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def _set_album_status(key: str, status: str) -> bool:
    """Đổi status 1 album theo dir."""
    with _ALBUM_PROD_LOCK:
        items = _load_albums()
        hit = False
        for a in items:
            if a.get("dir") == key:
                a["status"] = status
                hit = True
        if hit:
            ALBUM_PRODUCTS_FILE.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
        return hit


def _delete_album(dir_rel: str) -> bool:
    """Xoá 1 album đã lưu (record + folder ảnh)."""
    dir_rel = (dir_rel or "").strip().replace("\\", "/")
    if not dir_rel.startswith("output/albums/"):
        return False
    with _ALBUM_PROD_LOCK:
        items = _load_albums()
        kept = [a for a in items if a.get("dir") != dir_rel]
        ALBUM_PRODUCTS_FILE.write_text(json.dumps(kept, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        shutil.rmtree(str(Path(__file__).parent / dir_rel), ignore_errors=True)
    except Exception:
        pass
    return True


def _build_framework_script(topic: str) -> dict:
    """
    Build a short ~20s framework script with 4 parts:
      title (big hook overlay), hook (hook subtitle line), body, cta.
    If `topic` is a multi-line / long pasted script, parse it instead of generating.
    """
    text = topic.strip()
    is_pasted = ("\n" in text) or (len(text) >= 80)
    title = _derive_title(text)

    if is_pasted:
        if text.startswith("{") and text.endswith("}"):
            try:
                import json as _json
                d = _json.loads(text)
                return {"title": d.get("title", title), "hook": d.get("hook", ""),
                        "body": d.get("body", ""), "cta": d.get("cta", "")}
            except Exception:
                pass
        lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
        if len(lines) >= 3:
            return {"title": _derive_title(lines[0]), "hook": lines[0],
                    "body": " ".join(lines[1:-1]), "cta": lines[-1]}
        if len(lines) == 2:
            return {"title": _derive_title(lines[0]), "hook": lines[0],
                    "body": lines[1], "cta": "Lưu lại và theo dõi kênh để xem thêm nhé!"}
        return {"title": title, "hook": "Đừng đi nếu chưa biết những điều này!",
                "body": text, "cta": "Theo dõi kênh để xem thêm nhé!"}

    # Short generated template (~20s total when read by vi-VN edge TTS)
    place = text.rstrip(".!?")
    return {
        "title": title,
        "hook": "Đừng đi nếu chưa biết những điều này!",
        "body": (f"Từ cảnh thiên nhiên đẹp nghẹt thở, món ăn địa phương gây thương nhớ, "
                 f"đến những góc check-in cực chill. Mỗi khoảnh khắc ở {place} đều đáng giá."),
        "cta": "Lưu lại ngay và theo dõi kênh để không bỏ lỡ nhé!",
    }


def _concat_scene_clips(paths: list, dest: str) -> bool:
    """
    Concatenate multiple uploaded clips for one scene into a single 1080x1920@30
    H264 file (video only — voiceover is added later). Clips play in order;
    any excess length is trimmed downstream by the renderer's per-scene -t.
    Returns True on success.
    """
    import subprocess
    W, H = 1080, 1920
    cmd = ["ffmpeg", "-y"]
    for p in paths:
        cmd.extend(["-i", p])
    n = len(paths)
    parts = []
    for i in range(n):
        parts.append(
            f"[{i}:v]fps=30,scale={W}:{H}:force_original_aspect_ratio=decrease,"
            f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,setpts=PTS-STARTPTS[v{i}]"
        )
    concat_inputs = "".join(f"[v{i}]" for i in range(n))
    filter_complex = ";".join(parts) + f";{concat_inputs}concat=n={n}:v=1:a=0[outv]"
    cmd.extend([
        "-filter_complex", filter_complex, "-map", "[outv]",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-pix_fmt", "yuv420p", "-an",
        dest,
    ])
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if r.returncode == 0 and os.path.exists(dest) and os.path.getsize(dest) > 1000:
            return True
        print(f"[Server] _concat_scene_clips failed ({r.returncode}): {r.stderr[-300:]}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"[Server] _concat_scene_clips exception: {e}", file=sys.stderr)
        return False


def parse_multipart(handler: BaseHTTPRequestHandler):
    """
    Parse multipart/form-data from the request.
    Pure-Python, no `cgi` module — works on Python 3.13+.
    Returns (fields: dict[str, str], files: dict[str, tuple[filename, bytes]])
    """
    content_type = handler.headers.get("Content-Type", "")
    content_length = int(handler.headers.get("Content-Length", 0))
    body = handler.rfile.read(content_length)

    # Extract boundary from Content-Type header
    # e.g. "multipart/form-data; boundary=----FormBoundaryXYZ"
    boundary = None
    for part in content_type.split(";"):
        part = part.strip()
        if part.startswith("boundary="):
            boundary = part[len("boundary="):].strip().strip('"')
            break

    if not boundary:
        raise ValueError(f"Cannot find multipart boundary in Content-Type: {content_type}")

    # Delimiters as bytes
    delimiter = b"--" + boundary.encode()
    delimiter_end = delimiter + b"--"

    fields: dict = {}
    files: dict = {}

    # Split body by boundary
    parts = body.split(delimiter)
    for raw_part in parts:
        # Skip preamble / epilogue
        if raw_part in (b"", b"\r\n", b"--\r\n", b"--"):
            continue
        raw_part = raw_part.lstrip(b"\r\n")
        if raw_part.startswith(b"--"):
            continue  # final boundary marker

        # Split headers from body — separated by \r\n\r\n
        if b"\r\n\r\n" not in raw_part:
            continue
        raw_headers, _, part_body = raw_part.partition(b"\r\n\r\n")
        # Strip trailing \r\n from body
        part_body = part_body.rstrip(b"\r\n")

        # Parse part headers
        header_lines = raw_headers.decode("utf-8", errors="replace").splitlines()
        part_headers: dict = {}
        for line in header_lines:
            if ":" in line:
                k, _, v = line.partition(":")
                part_headers[k.strip().lower()] = v.strip()

        # Parse Content-Disposition
        disposition = part_headers.get("content-disposition", "")
        disp_params: dict = {}
        for token in disposition.split(";"):
            token = token.strip()
            if "=" in token:
                k, _, v = token.partition("=")
                disp_params[k.strip()] = v.strip().strip('"')

        field_name = disp_params.get("name", "")
        filename = disp_params.get("filename", None)

        if not field_name:
            continue

        if filename:
            files[field_name] = (filename, part_body)
        else:
            fields[field_name] = part_body.decode("utf-8", errors="replace")

    return fields, files


class AssembleHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"[Server] {self.address_string()} — {format % args}", file=sys.stderr)

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self._cors_headers()
        self.end_headers()

    def _cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json_response(self, data: dict, status: int = 200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self._cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path == "/assemble":
            self.handle_assemble()
        elif self.path == "/assemble-listreview":
            self.handle_assemble_listreview()
        elif self.path == "/assemble-image":
            self.handle_assemble_image()
        elif self.path == "/settings":
            self.handle_settings_save()
        elif self.path == "/venues":
            self.handle_venue_save()
        elif self.path == "/venues-delete":
            self.handle_venue_delete()
        elif self.path == "/venue-image":
            self.handle_venue_image()
        elif self.path == "/venue-image-delete":
            self.handle_venue_image_delete()
        elif self.path == "/venue-scrape-images":
            self.handle_venue_scrape_images()
        elif self.path == "/image-upload":
            self.handle_image_upload()
        elif self.path == "/images-delete":
            self.handle_image_delete()
        elif self.path == "/generate-script":
            self.handle_generate_script()
        elif self.path == "/script-prompt":
            self.handle_script_prompt_save()
        elif self.path == "/album-delete":
            self.handle_album_delete()
        elif self.path == "/product-status":
            self.handle_product_status()
        elif self.path == "/script-drafts-use":
            self.handle_script_draft_use()
        elif self.path == "/script-drafts-delete":
            self.handle_script_draft_delete()
        elif self.path == "/news-scrape":
            self.handle_news_scrape()
        elif self.path == "/venues-scrape-all":
            self.handle_venues_scrape_all()
        elif self.path == "/login":
            self.handle_login()
        elif self.path == "/news-research":
            self.handle_news_research()
        elif self.path == "/hookpreview":
            self.handle_hookpreview()
        elif self.path == "/preview":
            self.handle_preview()
        elif self.path == "/open-folder":
            self.handle_open_folder()
        elif self.path == "/download-file":
            self.handle_download_file()
        elif self.path == "/publish-to-dashboard":
            self.handle_publish_to_dashboard()
        elif self.path == "/health":
            self._json_response({"status": "ok", "port": PORT})
        else:
            self._json_response({"error": f"Unknown path: {self.path}"}, 404)

    def do_GET(self):
        if self.path.split("?", 1)[0] in ("/", "/app", "/index.html"):
            self._serve_index()
        elif self.path == "/settings":
            self.handle_settings_get()
        elif self.path == "/venues":
            self.handle_venues_get()
        elif self.path.startswith("/venue-thumb/"):
            self._serve_thumb(self.path[len("/venue-thumb/"):])
        elif self.path == "/images":
            self.handle_images_get()
        elif self.path.startswith("/album-img/"):
            self._serve_album(self.path[len("/album-img/"):])
        elif self.path.startswith("/hookframe/"):
            self._serve_hookframe(self.path[len("/hookframe/"):])
        elif self.path.startswith("/font/"):
            self._serve_font(self.path[len("/font/"):])
        elif self.path == "/health":
            self._json_response({"status": "ok", "port": PORT})
        elif self.path.startswith("/library"):
            self._serve_library()
        elif self.path == "/stats":
            self._serve_stats()
        elif self.path.startswith("/listreview-prefill"):
            self.handle_listreview_prefill()
        elif self.path.startswith("/script-prompt"):
            self.handle_script_prompt_get()
        elif self.path.startswith("/albums"):
            self.handle_albums_get()
        elif self.path.startswith("/album-library"):
            self.handle_album_library()
        elif self.path.startswith("/kpi"):
            self.handle_kpi()
        elif self.path.startswith("/script-drafts"):
            self.handle_script_drafts_get()
        elif self.path.startswith("/news-pool"):
            self.handle_news_pool()
        elif self.path.startswith("/output/"):
            # Serve output files statically for preview/playback (bỏ query ?w=… nếu có)
            rel = self.path.split("?", 1)[0].lstrip("/")
            file_path = Path(__file__).parent / rel
            if file_path.exists() and file_path.is_file():
                ext = file_path.suffix.lower()
                mime_map = {".mp4": "video/mp4", ".mov": "video/quicktime",
                            ".wav": "audio/wav", ".mp3": "audio/mpeg",
                            ".srt": "text/plain",
                            ".png": "image/png", ".jpg": "image/jpeg",
                            ".jpeg": "image/jpeg", ".webp": "image/webp",
                            ".gif": "image/gif"}
                mime = mime_map.get(ext, "application/octet-stream")
                self.send_response(200)
                self._cors_headers()
                self.send_header("Content-Type", mime)
                self.send_header("Content-Length", str(file_path.stat().st_size))
                self.send_header("Connection", "close")
                self.end_headers()
                with open(file_path, "rb") as f:
                    while chunk := f.read(65536):
                        self.wfile.write(chunk)
                self.close_connection = True
                return
            else:
                self.send_response(404)
                self._cors_headers()
                self.end_headers()
                return
        else:
            self._json_response({"error": "Not found"}, 404)

    def _read_json_body(self) -> dict:
        """Read and parse JSON body from request."""
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        return json.loads(body.decode("utf-8")) if body else {}

    def _serve_index(self):
        """Serve the single-page web UI."""
        if not WEB_INDEX.exists():
            self._json_response({"error": f"UI not found: {WEB_INDEX}"}, 404)
            return
        body = WEB_INDEX.read_bytes()
        self.send_response(200)
        self._cors_headers()
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)
        self.close_connection = True

    def _serve_library(self):
        """List a user's products (admin/news see all). Reads output/products.json."""
        from urllib.parse import urlparse, parse_qs
        q = parse_qs(urlparse(self.path).query)
        user = (q.get("user") or [""])[0]
        role = (q.get("role") or [""])[0]
        items = _load_products()
        if user and role not in ("admin",):
            items = [p for p in items if p.get("user") == user]
        items.sort(key=lambda x: x.get("time", 0), reverse=True)
        self._json_response({"videos": items})

    def _serve_stats(self):
        """Admin: count products per user."""
        items = _load_products()
        users = _load_users()
        counts = {}
        for p in items:
            counts[p.get("user", "?")] = counts.get(p.get("user", "?"), 0) + 1
        rows = []
        for uname, u in users.items():
            if u.get("role") in ("staff", "news"):
                rows.append({"user": uname, "name": u.get("name", uname),
                             "role": u.get("role"), "count": counts.get(uname, 0)})
        rows.sort(key=lambda r: r["count"], reverse=True)
        self._json_response({"stats": rows, "total": len(items)})

    def _serve_hookframe(self, name: str):
        """Serve a hook frame PNG from assets/hook_frames/ (for the UI preview)."""
        safe = os.path.basename(name)
        fp = Path(__file__).parent / "assets" / "hook_frames" / safe
        if not fp.exists() or fp.suffix.lower() != ".png":
            self._json_response({"error": "frame not found"}, 404)
            return
        body = fp.read_bytes()
        self.send_response(200)
        self._cors_headers()
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)
        self.close_connection = True

    def _serve_font(self, name: str):
        """Serve a .ttf from assets/fonts/ (for @font-face in the UI preview)."""
        safe = os.path.basename(name)
        fp = Path(__file__).parent / "assets" / "fonts" / safe
        if not fp.exists() or fp.suffix.lower() != ".ttf":
            self._json_response({"error": "font not found"}, 404)
            return
        body = fp.read_bytes()
        self.send_response(200)
        self._cors_headers()
        self.send_header("Content-Type", "font/ttf")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)
        self.close_connection = True

    def handle_login(self):
        """Check username/password against data/users.json."""
        try:
            data = self._read_json_body()
            u = (data.get("username") or "").strip()
            p = data.get("password") or ""
            users = _load_users()
            acc = users.get(u)
            if not acc or acc.get("password") != p:
                self._json_response({"ok": False, "error": "Sai tài khoản hoặc mật khẩu"}, 401)
                return
            self._json_response({
                "ok": True, "username": u, "role": acc.get("role", "staff"),
                "name": acc.get("name", u), "hook_style": acc.get("hook_style", "hook_red"),
                "voice": acc.get("voice", "gtts"),
            })
        except Exception as e:
            self._json_response({"ok": False, "error": str(e)}, 500)

    def handle_news_research(self):
        """News flow: trả TOPIC + LINK source YouTube để user tự tải về thả vào (không auto-download)."""
        try:
            data = self._read_json_body()
            keyword = (data.get("keyword") or "Đà Lạt").strip()
            # 1) script gợi ý (OpenRouter) + 2) link source thật từ YouTube (yt-dlp search, metadata only)
            try:
                from tools.script_ai import generate_script_ai
                script = generate_script_ai(f"tin tức / review {keyword}") or _build_framework_script(keyword)
            except Exception:
                script = _build_framework_script(keyword)
            sources = []
            try:
                import yt_dlp
                opts = {"quiet": True, "skip_download": True, "extract_flat": True, "default_search": "ytsearch"}
                with yt_dlp.YoutubeDL(opts) as ydl:
                    res = ydl.extract_info(f"ytsearch6:{keyword} Đà Lạt review", download=False)
                for e in (res.get("entries") or [])[:6]:
                    sources.append({
                        "title": e.get("title", ""),
                        "url": f"https://youtu.be/{e.get('id')}",
                        "duration": e.get("duration"),
                        "views": e.get("view_count"),
                    })
            except Exception as ex:
                print(f"[news] yt search lỗi: {ex}", file=sys.stderr)
            try:
                from tools.script_drafts import add_draft
                scenes = [
                    {"scene_id": "scene_1", "kind": "intro", "label": "HOOK",
                     "title": script.get("title", ""), "caption": script.get("hook", "")},
                    {"scene_id": "scene_2", "kind": "spot", "label": "NỘI DUNG", "caption": script.get("body", "")},
                    {"scene_id": "scene_3", "kind": "outro", "label": "CTA", "caption": script.get("cta", "")},
                ]
                add_draft("tintuc", scenes, "hook_news", "none", "fade", "pil", "", "ai")
            except Exception as _e:
                print(f"[news] lưu draft lỗi: {_e}", file=sys.stderr)
            self._json_response({"success": True, "keyword": keyword, "script": script, "sources": sources})
        except Exception as e:
            import traceback
            self._json_response({"success": False, "error": str(e), "traceback": traceback.format_exc()}, 500)

    def handle_hookpreview(self):
        """Build the real hook overlay PNG for the given style/title/subtitle and
        return it flattened on a light bg — so the user sees if text fits the frame."""
        try:
            data = self._read_json_body()
            style = data.get("style", "hook_red")
            title = data.get("title", "")
            subtitle = data.get("subtitle", "")

            import uuid as _uuid
            tmp = str(UPLOAD_TEMP_DIR / f"prev_{_uuid.uuid4().hex[:8]}.png")
            from PIL import Image
            if style.startswith("hook_news"):
                from tools.hook_overlay import build_news_hook
                color = style.split("_")[-1] if style.split("_")[-1] in ("green", "purple", "pink") else "pink"
                build_news_hook(caption=title or subtitle or "ĐÀ LẠT", out_path=tmp, color=color)
            elif style == "hook_overlay":
                from tools.hook_overlay import build_overlay
                build_overlay(title=title or "ĐÀ LẠT", script_lines=(subtitle or "",),
                              caption="", out_path=tmp, with_caption=False)
            else:
                from tools.hook_overlay import build_hook
                build_hook(style, title or "", subtitle or "", tmp)

            # Return the hook as a TRANSPARENT PNG so the UI can overlay it on a clip thumbnail.
            ov = Image.open(tmp).convert("RGBA")
            from io import BytesIO
            buf = BytesIO()
            ov.save(buf, format="PNG")
            body = buf.getvalue()
            try:
                os.remove(tmp)
            except Exception:
                pass

            self.send_response(200)
            self._cors_headers()
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)
            self.close_connection = True
        except Exception as e:
            import traceback
            print(f"[Server] /hookpreview error: {e}\n{traceback.format_exc()}", file=sys.stderr)
            self._json_response({"success": False, "error": str(e)}, 500)

    def handle_generate_script(self):
        """
        Stage 1 (framework): build a short ~20s script (hook/body/cta) from a topic
        and return exactly 3 captioned scenes that map 1:1 to the voiceover segments.
        If the user pastes a multi-line script, parse it as hook / body / cta instead.
        """
        print("[Server] /generate-script — Tạo kịch bản theo framework (3 scene)...", file=sys.stderr)
        try:
            data = self._read_json_body()
            topic = (data.get("topic") or "").strip()
            if not topic:
                self._json_response({"success": False, "error": "Thiếu chủ đề / kịch bản."}, 400)
                return

            # Prefer AI (OpenRouter, learns from data/transcripts/); fallback to template.
            script = None
            try:
                from tools.script_ai import generate_script_ai
                script = generate_script_ai(topic)
                if script:
                    print(f"[Server] /generate-script: dùng OpenRouter (AI). title={script.get('title')}", file=sys.stderr)
            except Exception as e:
                print(f"[Server] script_ai lỗi: {e}", file=sys.stderr)
            if not script:
                script = _build_framework_script(topic)
                print("[Server] /generate-script: dùng template (fallback).", file=sys.stderr)

            # ~chars per second for vi-VN edge TTS @ speed 1.08 → estimate scene durations
            def est(text):
                return max(3, round(len(text) / 14.0))

            scenes = [
                {"scene_id": "scene_1", "label": "HOOK", "title": script["title"], "caption": script["hook"],
                 "description": "Cảnh mở đầu (hook overlay)", "min_duration_sec": est(script["title"] + " " + script["hook"]), "type": "clip"},
                {"scene_id": "scene_2", "label": "NỘI DUNG", "caption": script["body"],
                 "description": "Cảnh đẹp / trải nghiệm chính", "min_duration_sec": est(script["body"]), "type": "clip"},
                {"scene_id": "scene_3", "label": "CTA", "caption": script["cta"],
                 "description": "Cảnh kết kèm kêu gọi", "min_duration_sec": est(script["cta"]), "type": "clip"},
            ]

            import uuid as _uuid
            self._json_response({
                "success": True,
                "job_id": f"job_{_uuid.uuid4().hex[:10]}",
                "script": script,
                "scenes": scenes,
            })
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(f"[Server] /generate-script error: {e}\n{tb}", file=sys.stderr)
            self._json_response({"success": False, "error": str(e), "traceback": tb}, 500)

    def handle_open_folder(self):
        """Open Windows Explorer at the directory containing the given file path."""
        try:
            data = self._read_json_body()
            file_path = data.get("path", "")

            # Resolve relative path against pipeline dir
            if not os.path.isabs(file_path):
                file_path = str(Path(__file__).parent / file_path)

            file_path = os.path.normpath(file_path)
            folder = os.path.dirname(file_path) if os.path.isfile(file_path) else file_path

            print(f"[Server] /open-folder: {folder}", file=sys.stderr)

            if not os.path.exists(folder):
                self._json_response({"success": False, "error": f"Path not found: {folder}"}, 404)
                return

            import platform
            if platform.system() == "Windows":
                # Use /select to highlight the specific file in Explorer
                if os.path.isfile(file_path):
                    subprocess.Popen(["explorer", "/select,", file_path])
                else:
                    subprocess.Popen(["explorer", folder])
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", "-R", file_path])
            else:
                subprocess.Popen(["xdg-open", folder])

            self._json_response({"success": True, "folder": folder})
        except Exception as e:
            print(f"[Server] /open-folder error: {e}", file=sys.stderr)
            self._json_response({"success": False, "error": str(e)}, 500)

    def handle_download_file(self):
        """Stream a file from the server to the browser for download."""
        try:
            data = self._read_json_body()
            file_path = data.get("path", "")

            # Resolve relative path
            if not os.path.isabs(file_path):
                file_path = str(Path(__file__).parent / file_path)
            file_path = os.path.normpath(file_path)

            print(f"[Server] /download-file: {file_path}", file=sys.stderr)

            if not os.path.isfile(file_path):
                self._json_response({"error": f"File not found: {file_path}"}, 404)
                return

            file_size = os.path.getsize(file_path)
            filename  = os.path.basename(file_path)

            # Detect MIME type
            ext = os.path.splitext(filename)[1].lower()
            mime_map = {".mp4": "video/mp4", ".mov": "video/quicktime",
                        ".wav": "audio/wav", ".mp3": "audio/mpeg",
                        ".srt": "text/plain"}
            mime = mime_map.get(ext, "application/octet-stream")

            self.send_response(200)
            self._cors_headers()
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(file_size))
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.send_header("Connection", "close")
            self.end_headers()

            with open(file_path, "rb") as f:
                while chunk := f.read(65536):
                    self.wfile.write(chunk)
            self.close_connection = True

        except Exception as e:
            print(f"[Server] /download-file error: {e}", file=sys.stderr)
            self._json_response({"error": str(e)}, 500)

    def handle_preview(self):
        print("[Server] /preview — Nhận request nghe thử...", file=sys.stderr)
        try:
            data = self._read_json_body()
            provider = data.get("provider", "mock")
            voice_id = data.get("voice_id", "")
            text = data.get("text", "Xin chào.")
            
            # Inject keys
            el_key = data.get("elevenlabs_api_key", "")
            if el_key:
                os.environ["ELEVENLABS_API_KEY"] = el_key
            vbee_key = data.get("vbee_api_key", "")
            if vbee_key:
                os.environ["VBEE_API_KEY"] = vbee_key
            openai_key = data.get("openai_api_key", "")
            if openai_key:
                os.environ["OPENAI_API_KEY"] = openai_key
            ant_key = data.get("anthropic_api_key", "")
            if ant_key:
                os.environ["ANTHROPIC_API_KEY"] = ant_key
            gemini_key = data.get("gemini_api_key", "")
            if gemini_key:
                os.environ["GEMINI_API_KEY"] = gemini_key
                
            from tools.voice_generator import VoiceGenerator
            gen = VoiceGenerator(provider=provider)
            output_name = f"preview_{provider}_{voice_id}"
            
            # Force speed to 1.0 for previews
            audio_path = gen.generate_voice(
                text=text,
                voice_id=voice_id,
                output_name=output_name,
                speed=1.0
            )
            
            # Resolve path relative to pipeline root (for static serving)
            rel_path = os.path.relpath(audio_path, str(Path(__file__).parent))
            # Format with forward slashes for URLs
            url_path = "/" + rel_path.replace("\\", "/")
            
            self._json_response({
                "success": True,
                "audio_path": audio_path,
                "url_path": url_path
            })
        except Exception as e:
            print(f"[Server] /preview error: {e}", file=sys.stderr)
            self._json_response({"success": False, "error": str(e)}, 500)


    def handle_assemble(self):
        print("[Server] /assemble — Nhận request ghép video...", file=sys.stderr)
        try:
            fields, files = parse_multipart(self)
        except Exception as e:
            print(f"[Server] Lỗi parse multipart: {e}", file=sys.stderr)
            self._json_response({"success": False, "error": f"Lỗi đọc request: {e}"}, 400)
            return

        # Extract metadata
        job_id = fields.get("job_id", f"job_{uuid.uuid4().hex[:8]}")
        transition = fields.get("transition", "fade")
        voice_mode = fields.get("voice_mode", "mock")
        creator_id = fields.get("creator_id", "lan_anh")
        template_ratio = fields.get("template_ratio", "9:16")
        hook_style = fields.get("hook_style", "zoom_in")
        hook_text = fields.get("hook_text", "")
        hook_title = fields.get("hook_title", "")
        hook_subtitle = fields.get("hook_subtitle", "")
        video_type = fields.get("video_type", "personal")
        voice_id = fields.get("voice_id", "")

        # Inject API keys into environment if provided
        for key_name in ["elevenlabs_api_key", "vbee_api_key", "openai_api_key", "anthropic_api_key", "gemini_api_key"]:
            val = fields.get(key_name, "")
            env_var = key_name.upper()
            if val:
                os.environ[env_var] = val
                print(f"[Server] Key {env_var} set in env (len={len(val)})", file=sys.stderr)
            else:
                existing = os.getenv(env_var, "")
                if existing:
                    print(f"[Server] Key {env_var} already present in server env (len={len(existing)})", file=sys.stderr)
                else:
                    print(f"[Server] Key {env_var} is empty in request and server env", file=sys.stderr)

        try:
            script = json.loads(fields.get("script", "{}"))
        except Exception:
            script = {"hook": "", "body": "", "cta": ""}

        try:
            scenes_meta = json.loads(fields.get("scenes_meta", "[]"))
        except Exception:
            scenes_meta = []

        print(f"[Server] Job: {job_id}, {len(scenes_meta)} scene(s), transition={transition}", file=sys.stderr)

        # Save uploaded files to temp dir
        job_temp = UPLOAD_TEMP_DIR / job_id
        job_temp.mkdir(parents=True, exist_ok=True)

        scene_uploads = []
        for scene in scenes_meta:
            sid = scene.get("scene_id", "")

            # Collect all files for this scene: field name == sid, or "{sid}__{idx}".
            # Sort by the numeric suffix so clips concat in drop order.
            def _idx(fname):
                if "__" in fname:
                    tail = fname.rsplit("__", 1)[1]
                    return int(tail) if tail.isdigit() else 0
                return 0
            field_names = sorted(
                [fn for fn in files if fn == sid or fn.startswith(sid + "__")],
                key=_idx,
            )

            saved_paths = []
            for k, fn in enumerate(field_names):
                filename, file_bytes = files[fn]
                ext = Path(filename).suffix or ".mp4"
                dest = job_temp / f"{sid}_{k}{ext}"
                with open(str(dest), "wb") as f:
                    f.write(file_bytes)
                saved_paths.append(str(dest))
                print(f"[Server]   ✓ {sid}[{k}]: {filename} ({len(file_bytes)/1024/1024:.1f}MB)", file=sys.stderr)

            if not saved_paths:
                scene_uploads.append({"scene_id": sid, "file_path": ""})
                print(f"[Server]   ⚠ {sid}: no file → placeholder", file=sys.stderr)
            elif len(saved_paths) == 1:
                scene_uploads.append({"scene_id": sid, "file_path": saved_paths[0]})
            else:
                concat_dest = str(job_temp / f"{sid}_concat.mp4")
                if _concat_scene_clips(saved_paths, concat_dest):
                    scene_uploads.append({"scene_id": sid, "file_path": concat_dest})
                    print(f"[Server]   ✓ {sid}: nối {len(saved_paths)} clip → {concat_dest}", file=sys.stderr)
                else:
                    # Concat failed → fall back to first clip
                    scene_uploads.append({"scene_id": sid, "file_path": saved_paths[0]})
                    print(f"[Server]   ⚠ {sid}: concat lỗi, dùng clip đầu", file=sys.stderr)

        # Ensure jobs collection
        try:
            from tools.db import get_db, now_utc, new_doc
            db = get_db()
            jobs_col = db["jobs"] if hasattr(db, "__getitem__") else None
            if jobs_col is not None:
                job_doc = new_doc(
                    _id=job_id,
                    status="running",
                    creator_id=creator_id,
                    script=script,
                    scenes=[
                        {**s, "file_path": next((u["file_path"] for u in scene_uploads if u["scene_id"] == s.get("scene_id")), ""), "uploaded": True}
                        for s in scenes_meta
                    ],
                    voice_provider=voice_mode,
                    voice_id=voice_id,
                    hook_style=hook_style,
                    hook_text=hook_text or script.get("hook", ""),
                    hook_title=hook_title,
                    hook_subtitle=hook_subtitle,
                    template_ratio=template_ratio,
                    video_type=video_type,
                    created_at=now_utc().isoformat(),
                )
                try:
                    jobs_col.insert_one(job_doc)
                except Exception:
                    jobs_col.update_one({"_id": job_id}, {"$set": job_doc}, upsert=True)
        except Exception as e:
            print(f"[Server] Warning: DB error (continuing): {e}", file=sys.stderr)

        # Run assembly (serialized — only one heavy job at a time)
        try:
            with _HEAVY_LOCK:
                # Force reload agents/tools modules so code edits take effect without restart
                for m in list(sys.modules.keys()):
                    if m.startswith("agents") or m.startswith("tools"):
                        sys.modules.pop(m, None)

                from agents.personal_video_agent import run_assemble_video
                print(f"[Server] Bắt đầu ghép video với FFmpeg...", file=sys.stderr)
                result = run_assemble_video(
                    job_id=job_id,
                    scene_uploads=scene_uploads,
                    transition=transition,
                    hook_style=hook_style,
                    hook_text=hook_text,
                    hook_title=hook_title,
                    hook_subtitle=hook_subtitle,
                    video_type=video_type,
                    voice_provider=voice_mode,
                    voice_id=voice_id,
                )
            print(f"[Server] ✅ Hoàn tất! Video: {result.get('video_path')}", file=sys.stderr)
            video_url = _to_output_url(result.get("video_path", ""))
            # Track product per user (for admin stats + per-user library)
            try:
                import time as _t
                _append_product({
                    "user": fields.get("user", "") or creator_id,
                    "topic": fields.get("topic", "") or hook_title,
                    "hook_style": hook_style,
                    "video_url": video_url,
                    "time": _t.time(),
                })
            except Exception as _e:
                print(f"[Server] product log lỗi: {_e}", file=sys.stderr)
            self._json_response({
                "success": True,
                "video_path": result.get("video_path", ""),
                "video_url": video_url,
                "audio_path": result.get("audio_path", ""),
                "job_id": job_id,
            })
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(f"[Server] ❌ Lỗi assembly: {e}\n{tb}", file=sys.stderr)
            self._json_response({
                "success": False,
                "error": _friendly_error(e),
            }, 500)
        finally:
            # Cleanup temp upload dir after delay
            def cleanup():
                import time
                time.sleep(60)
                shutil.rmtree(str(job_temp), ignore_errors=True)
            threading.Thread(target=cleanup, daemon=True).start()

    def handle_assemble_listreview(self):
        """Luồng nhân viên (list-review, mẫu nv1): intro + N quán (tên+điểm+VO+clip) + outro."""
        print("[Server] /assemble-listreview — nhận request...", file=sys.stderr)
        try:
            fields, files = parse_multipart(self)
        except Exception as e:
            self._json_response({"success": False, "error": f"Lỗi đọc request: {e}"}, 400)
            return

        job_id = fields.get("job_id", f"lr_{uuid.uuid4().hex[:8]}")
        user = fields.get("user", "") or fields.get("creator_id", "nv1")
        hook_style = fields.get("hook_style", "hook_red")
        voice_provider = fields.get("voice_mode", "gtts")
        voice_id = fields.get("voice_id", "")
        try:
            spec_in = json.loads(fields.get("spec", "{}"))
        except Exception:
            spec_in = {}

        job_temp = UPLOAD_TEMP_DIR / job_id
        job_temp.mkdir(parents=True, exist_ok=True)

        def _save_clips(scene_id: str) -> list:
            def _idx(fn):
                tail = fn.rsplit("__", 1)[1] if "__" in fn else "0"
                return int(tail) if tail.isdigit() else 0
            names = sorted([fn for fn in files if fn == scene_id or fn.startswith(scene_id + "__")], key=_idx)
            out = []
            for k, fn in enumerate(names):
                filename, file_bytes = files[fn]
                ext = Path(filename).suffix or ".mp4"
                dest = job_temp / f"{scene_id}_{k}{ext}"
                with open(str(dest), "wb") as f:
                    f.write(file_bytes)
                out.append(str(dest))
            return out

        # Build render spec với đường dẫn clip đã lưu
        intro = spec_in.get("intro") or {}
        outro = spec_in.get("outro") or {}
        # Engine overlay: HTML (nv2/nv3) hay PIL (nv1) — lấy từ request hoặc prefill nhân viên
        overlay_engine = (fields.get("overlay_engine") or spec_in.get("overlay_engine") or "").strip().lower()
        style = (fields.get("style") or spec_in.get("style") or "").strip().lower()
        # badge_mode (full/name/none) + transition (none/swoosh): từ request, fallback prefill.
        badge_mode = (fields.get("badge_mode") or spec_in.get("badge_mode") or "").strip().lower()
        transition = (fields.get("transition") or spec_in.get("transition") or "").strip().lower()
        if not overlay_engine or not badge_mode:
            try:
                from tools.listreview_content import build_prefill
                pf = build_prefill(user)
                overlay_engine = overlay_engine or (pf.get("overlay_engine") or "pil").lower()
                style = style or (pf.get("style") or "").lower()
                badge_mode = badge_mode or (pf.get("badge_mode") or "full").lower()
                transition = transition or (pf.get("transition") or "none").lower()
            except Exception:
                overlay_engine = overlay_engine or "pil"
        badge_mode = badge_mode or "full"
        transition = transition or "none"
        spec = {
            "job_id": job_id, "hook_style": hook_style,
            "voice_provider": voice_provider, "voice_id": voice_id,
            "overlay_engine": overlay_engine, "style": style,
            "badge_mode": badge_mode, "transition": transition,
            "intro": {"title": intro.get("title", ""), "hook_lines": intro.get("hook_lines"),
                      "vo": intro.get("vo", ""), "clips": _save_clips(intro.get("scene_id", "intro"))},
            "spots": [{"name": s.get("name", ""), "rating": s.get("rating", ""),
                       "address": s.get("address", ""), "vo": s.get("vo", ""),
                       "section_title": s.get("section_title", ""), "emoji": s.get("emoji", ""),
                       "align": s.get("align", "left"), "no_pill": s.get("no_pill", False),
                       "body": s.get("body"),
                       "clips": _save_clips(s.get("scene_id", f"spot{i}"))}
                      for i, s in enumerate(spec_in.get("spots", []), start=1)],
            "outro": {"vo": outro.get("vo", ""), "section_title": outro.get("section_title", ""),
                      "emoji": outro.get("emoji", ""), "body": outro.get("body"),
                      "clips": _save_clips(outro.get("scene_id", "outro"))},
        }

        try:
            with _HEAVY_LOCK:
                for m in list(sys.modules.keys()):
                    if m.startswith("tools.list_review_render"):
                        sys.modules.pop(m, None)
                from tools.list_review_render import render_list_review
                result = render_list_review(spec)
            if not result.get("success"):
                self._json_response({"success": False,
                                     "error": _friendly_error(result.get("error", "render fail"))}, 500)
                return
            video_url = _to_output_url(result.get("video_path", ""))
            try:
                import time as _t
                _topic = intro.get("title", "") or "List review"
                _append_product({"user": user, "topic": _topic,
                                 "hook_style": hook_style, "video_url": video_url, "time": _t.time()})
                _notify_publish(user, _topic, video_url)   # nv publish → gửi Telegram duyệt
            except Exception as _e:
                print(f"[Server] product log lỗi: {_e}", file=sys.stderr)
            self._json_response({"success": True, "video_url": video_url,
                                 "video_path": result.get("video_path", ""),
                                 "duration": result.get("duration"), "job_id": job_id})
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(f"[Server] ❌ list-review lỗi: {e}\n{tb}", file=sys.stderr)
            self._json_response({"success": False, "error": _friendly_error(e)}, 500)
        finally:
            def cleanup():
                import time
                time.sleep(60)
                shutil.rmtree(str(job_temp), ignore_errors=True)
            threading.Thread(target=cleanup, daemon=True).start()

    def handle_assemble_image(self):
        """POST /assemble-image {album, user} → chạy script CLI dựng album ảnh, lưu lại, trả list ảnh PNG."""
        try:
            body = self._read_json_body()
            album = (body.get("album") or "").strip()
            user = (body.get("user") or "").strip()
            res = _generate_album(album, user)
            self._json_response(res, 200 if res.get("success") else (400 if "hợp lệ" in res.get("error", "") else 500))
        except subprocess.TimeoutExpired:
            self._json_response({"success": False, "error": "Quá thời gian (300s)."}, 500)
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(f"[Server] ❌ assemble-image lỗi: {e}\n{tb}", file=sys.stderr)
            self._json_response({"success": False, "error": str(e)}, 500)

    def handle_albums_get(self):
        """GET /albums?user= → danh sách mẫu album theo tài khoản (admin: tất cả)."""
        try:
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            user = (q.get("user", [""])[0] or "").strip()
            self._json_response({"success": True, "albums": _albums_for(user)})
        except Exception as e:
            self._json_response({"success": False, "error": str(e)}, 500)

    def handle_album_library(self):
        """GET /album-library?user=&role= → album đã tạo (lọc theo user nếu không phải admin)."""
        try:
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            user = (q.get("user", [""])[0] or "").strip()
            role = (q.get("role", [""])[0] or "").strip()
            items = sorted(_load_albums(), key=lambda a: a.get("time", 0), reverse=True)
            if role != "admin" and user:
                items = [a for a in items if a.get("user") == user]
            self._json_response({"success": True, "albums": items})
        except Exception as e:
            self._json_response({"success": False, "error": str(e)}, 500)

    def handle_product_status(self):
        """POST /product-status {kind:'video'|'album', key, status} → đổi trạng thái duyệt/đăng."""
        try:
            b = self._read_json_body()
            kind = (b.get("kind") or "video").strip()
            key = (b.get("key") or "").strip()
            status = (b.get("status") or "").strip()
            if status not in ("pending", "posted", "failed", "cancelled"):
                self._json_response({"success": False, "error": "status không hợp lệ"}, 400)
                return
            # Admin duyệt "đã đăng" video của nv publish → đăng TikTok thật (Zernio).
            if kind == "video" and status == "posted":
                rec = next((p for p in _load_products() if p.get("video_url") == key), None)
                owner = (rec or {}).get("user", "")
                if _is_publish_user(owner):
                    res = _do_publish(key, _caption_for((rec or {}).get("topic", "")), owner)
                    self._json_response({"success": bool(res.get("success")),
                                         "posted": bool(res.get("success")),
                                         "error": res.get("error", "")})
                    return
            ok = _set_album_status(key, status) if kind == "album" else _set_product_status(key, status)
            self._json_response({"success": ok})
        except Exception as e:
            self._json_response({"success": False, "error": str(e)}, 500)

    def handle_news_scrape(self):
        """POST /news-scrape {keyword, hashtags[]} → cào YouTube tin Đà Lạt (video+shorts), lưu pool."""
        try:
            b = self._read_json_body()
            kw = (b.get("keyword") or "").strip()
            hts = b.get("hashtags")
            from tools.news_youtube import scrape_news, save_pool, DEFAULT_KEYWORD
            with _HEAVY_LOCK:
                res = scrape_news(kw or DEFAULT_KEYWORD, hts if isinstance(hts, list) else None)
            if res.get("success"):
                save_pool(res)
            self._json_response(res)
        except Exception as e:
            self._json_response({"success": False, "error": str(e), "items": []}, 500)

    def handle_news_pool(self):
        """GET /news-pool → tin đã cào gần nhất + từ khóa/hashtag mặc định."""
        try:
            from tools.news_youtube import load_pool, DEFAULT_KEYWORDS, DEFAULT_HASHTAGS
            p = load_pool()
            self._json_response({"success": True, "time": p.get("time", 0), "items": p.get("items", []),
                                 "keywords": DEFAULT_KEYWORDS, "hashtags": DEFAULT_HASHTAGS})
        except Exception as e:
            self._json_response({"success": False, "error": str(e), "items": []}, 500)

    def handle_script_drafts_get(self):
        """GET /script-drafts?user=&role=&only_unused=1 → kịch bản đã tạo, lưu lại (không xoá)."""
        try:
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            user = (q.get("user", [""])[0] or "").strip()
            role = (q.get("role", [""])[0] or "").strip()
            only_unused = (q.get("only_unused", ["0"])[0] == "1")
            from tools.script_drafts import list_drafts
            items = list_drafts(None if role == "admin" else user, only_unused=only_unused)
            self._json_response({"success": True, "drafts": items})
        except Exception as e:
            self._json_response({"success": False, "error": str(e), "drafts": []}, 500)

    def handle_script_draft_use(self):
        """POST /script-drafts-use {id} → đánh dấu đã dùng, trả về scenes để nạp vào editor."""
        try:
            b = self._read_json_body()
            did = (b.get("id") or "").strip()
            from tools.script_drafts import mark_used
            d = mark_used(did)
            if not d:
                self._json_response({"success": False, "error": "Không tìm thấy kịch bản."}, 404)
                return
            self._json_response({"success": True, "draft": d})
        except Exception as e:
            self._json_response({"success": False, "error": str(e)}, 500)

    def handle_script_draft_delete(self):
        """POST /script-drafts-delete {id} → xoá 1 kịch bản đã lưu."""
        try:
            b = self._read_json_body()
            from tools.script_drafts import delete_draft
            ok = delete_draft((b.get("id") or "").strip())
            self._json_response({"success": ok})
        except Exception as e:
            self._json_response({"success": False, "error": str(e)}, 500)

    def handle_kpi(self):
        """GET /kpi → KPI hôm nay mỗi nhân viên (video + ảnh). Staff mục tiêu 5+5; tin tức 10 video."""
        try:
            import time as _t
            lt = _t.localtime()
            sod = _t.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1))
            users = _load_users()
            prods = _load_products()
            albums = _load_albums()
            rows = []
            for uid, u in users.items():
                role = u.get("role")
                if role not in ("staff", "news"):
                    continue
                v = sum(1 for p in prods if p.get("user") == uid and p.get("time", 0) >= sod)
                a = sum(1 for al in albums if al.get("user") == uid and al.get("time", 0) >= sod)
                rows.append({"user": uid, "name": u.get("name", uid), "role": role,
                             "videos": v, "target_v": (10 if role == "news" else 5),
                             "images": a, "target_a": (0 if role == "news" else 5)})
            self._json_response({"success": True, "kpi": rows})
        except Exception as e:
            self._json_response({"success": False, "error": str(e)}, 500)

    def handle_album_delete(self):
        """POST /album-delete {dir} → xoá album đã lưu."""
        try:
            body = self._read_json_body()
            ok = _delete_album(body.get("dir", ""))
            self._json_response({"success": ok})
        except Exception as e:
            self._json_response({"success": False, "error": str(e)}, 500)

    def handle_venues_scrape_all(self):
        """POST /venues-scrape-all → cào APIFY cho các quán có < 8 ảnh (chạy tuần tự)."""
        if not (os.getenv("APIFY_API_KEY") or os.getenv("APIFY_TOKEN")):
            self._json_response({"success": False, "error": "Thiếu APIFY_API_KEY (vào Cài đặt nhập key)."}, 400)
            return
        try:
            from tools import venues_db
            from tools.venue_images_scrape import scrape_venue_images
            need = [v for v in venues_db.get_all() if len(v.get("images") or []) < 8]
            done, total, per = 0, 0, []
            with _HEAVY_LOCK:
                for v in need:
                    try:
                        n = scrape_venue_images(v, 8)
                    except Exception as ex:
                        n = 0
                        print(f"[Server] scrape-all lỗi {v.get('name')}: {ex}", file=sys.stderr)
                    total += n
                    done += 1
                    per.append({"id": v["id"], "name": v.get("name"), "added": n})
            self._json_response({"success": True, "scanned": len(need),
                                 "done": done, "total_added": total, "per_venue": per})
        except Exception as e:
            import traceback
            print(f"[Server] scrape-all lỗi: {e}\n{traceback.format_exc()}", file=sys.stderr)
            self._json_response({"success": False, "error": str(e)}, 500)

    def handle_script_prompt_get(self):
        """GET /script-prompt?employee=nv1 → prompt persona + examples đã lưu + bản mặc định."""
        try:
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            employee = (q.get("employee", ["nv1"])[0] or "nv1").strip().lower()
            from tools.script_prompts import get_script_prompt, default_persona
            rec = get_script_prompt(employee)
            self._json_response({"success": True, "employee": employee,
                                 "prompt": rec["prompt"], "examples": rec["examples"],
                                 "default_prompt": default_persona(employee)})
        except Exception as e:
            self._json_response({"success": False, "error": str(e)}, 500)

    def handle_script_prompt_save(self):
        """POST /script-prompt {employee, prompt, examples} → lưu prompt viết kịch bản."""
        try:
            body = self._read_json_body()
            employee = (body.get("employee") or "").strip().lower()
            if not employee:
                self._json_response({"success": False, "error": "Thiếu employee"}, 400)
                return
            from tools.script_prompts import set_script_prompt
            set_script_prompt(employee, body.get("prompt", ""), body.get("examples", ""))
            # Xoá cache prefill để lần tạo nội dung sau dùng prompt mới.
            try:
                (Path(__file__).parent / "data" / "prefill" / f"{employee}.json").unlink(missing_ok=True)
            except Exception:
                pass
            self._json_response({"success": True})
        except Exception as e:
            self._json_response({"success": False, "error": str(e)}, 500)

    def handle_listreview_prefill(self):
        """GET /listreview-prefill?employee=nv1&regen=0|1 → scene + nội dung AI điền sẵn (chỉ nv1)."""
        try:
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            employee = (q.get("employee", ["nv1"])[0] or "nv1")
            regen = q.get("regen", ["0"])[0] == "1"
            hook_style = (_load_users().get(employee, {}) or {}).get("hook_style", "hook_red")
            from tools.listreview_content import build_prefill
            data = build_prefill(employee, regen=regen)
            self._json_response({"success": bool(data.get("scenes")),
                                 "hook_style": data.get("hook_style", hook_style),
                                 "style": data.get("style", ""),
                                 "overlay_engine": data.get("overlay_engine", "pil"),
                                 "badge_mode": data.get("badge_mode", "full"),
                                 "transition": data.get("transition", "none"),
                                 "scenes": data.get("scenes", []), "generated_by": data.get("generated_by"),
                                 "error": data.get("error", "")})
        except Exception as e:
            import traceback
            print(f"[Server] /listreview-prefill error: {e}\n{traceback.format_exc()}", file=sys.stderr)
            self._json_response({"success": False, "error": str(e)}, 500)

    def handle_settings_get(self):
        """GET /settings → danh sách key + đã điền hay chưa (KHÔNG trả giá trị key)."""
        items = [{**meta, "is_set": _env_is_set(meta["key"])} for meta in SETTINGS_KEYS]
        self._json_response({"success": True, "keys": items})

    def handle_settings_save(self):
        """POST /settings {KEY: value, ...} → ghi .env + áp dụng ngay. Bỏ qua value rỗng/ẩn."""
        try:
            data = self._read_json_body()
        except Exception as e:
            self._json_response({"success": False, "error": f"Body lỗi: {e}"}, 400)
            return
        updates = {}
        for k, v in (data or {}).items():
            if k not in _SETTINGS_ALLOWED:
                continue
            v = (v or "").strip()
            if not v or set(v) <= {"•", "*"}:   # rỗng hoặc chuỗi ẩn → giữ nguyên key cũ
                continue
            updates[k] = v
        if not updates:
            self._json_response({"success": True, "saved": [], "message": "Không có thay đổi."})
            return
        try:
            _update_env(updates)
            self._json_response({"success": True, "saved": sorted(updates.keys()),
                                 "message": f"Đã lưu {len(updates)} key. Có hiệu lực ngay."})
        except Exception as e:
            import traceback
            print(f"[Server] /settings save error: {e}\n{traceback.format_exc()}", file=sys.stderr)
            self._json_response({"success": False, "error": str(e)}, 500)

    # ── Thư viện địa điểm (DB) ─────────────────────────────────────────────
    @staticmethod
    def _venue_view(v: dict) -> dict:
        """Thêm image_urls (URL trình duyệt) — chỉ ảnh thật sự có trong data/thumbs.
        Ảnh cũ đường dẫn tuyệt đối (máy khác) bị bỏ qua → UI hiện placeholder."""
        urls, kept = [], []
        for p in (v.get("images") or []):
            name = Path(p).name
            if (THUMB_DIR / name).exists():
                urls.append(f"/venue-thumb/{name}")
                kept.append(p)
        return {**v, "images": kept, "image_urls": urls}

    def handle_venues_get(self):
        try:
            from tools import venues_db
            venues = [self._venue_view(v) for v in venues_db.get_all()]
            # seeding lên đầu, giữ thứ tự còn lại
            venues.sort(key=lambda v: 0 if v.get("loai") == "cần seeding" else 1)
            self._json_response({"success": True, "venues": venues, "options": {
                "loai_quan": list(venues_db.LOAI_QUAN_OPTIONS),
                "loai": list(venues_db.LOAI_OPTIONS),
                "co_nguoi": list(venues_db.CO_NGUOI_OPTIONS)}})
        except Exception as e:
            import traceback
            print(f"[Server] /venues GET error: {e}\n{traceback.format_exc()}", file=sys.stderr)
            self._json_response({"success": False, "error": str(e)}, 500)

    def handle_venue_save(self):
        try:
            from tools import venues_db
            v = self._read_json_body()
            saved = venues_db.save_venue(v or {})
            self._json_response({"success": True, "venue": self._venue_view(saved)})
        except Exception as e:
            self._json_response({"success": False, "error": str(e)}, 500)

    def handle_venue_delete(self):
        try:
            from tools import venues_db
            vid = (self._read_json_body() or {}).get("id")
            ok = venues_db.delete_by_id(int(vid)) if vid is not None else False
            self._json_response({"success": ok})
        except Exception as e:
            self._json_response({"success": False, "error": str(e)}, 500)

    def handle_venue_image(self):
        """Multipart: id + 1..n file (field bắt đầu 'image'). Lưu data/thumbs, append vào images."""
        try:
            from tools import venues_db
            fields, files = parse_multipart(self)
            vid = int(fields.get("id"))
            THUMB_DIR.mkdir(parents=True, exist_ok=True)
            imgs = []
            for fn in sorted(files):
                if not fn.startswith("image"):
                    continue
                filename, file_bytes = files[fn]
                ext = (Path(filename).suffix or ".jpg").lower()
                safe = "".join(c if c.isalnum() else "_" for c in Path(filename).stem)[:40]
                dest = THUMB_DIR / f"{vid}_{uuid.uuid4().hex[:6]}_{safe}{ext}"
                with open(dest, "wb") as f:
                    f.write(file_bytes)
                imgs = venues_db.add_image(vid, f"data/thumbs/{dest.name}")
            venue = next((v for v in venues_db.get_all() if v["id"] == vid), {})
            self._json_response({"success": True, "venue": self._venue_view(venue)})
        except Exception as e:
            import traceback
            print(f"[Server] /venue-image error: {e}\n{traceback.format_exc()}", file=sys.stderr)
            self._json_response({"success": False, "error": str(e)}, 500)

    def handle_venue_image_delete(self):
        try:
            from tools import venues_db
            body = self._read_json_body() or {}
            vid, path = int(body.get("id")), body.get("path", "")
            venues_db.remove_image(vid, path)
            # xoá file vật lý nếu nằm trong data/thumbs
            fp = Path(__file__).parent / path
            if fp.exists() and THUMB_DIR in fp.parents:
                try: fp.unlink()
                except Exception: pass
            venue = next((v for v in venues_db.get_all() if v["id"] == vid), {})
            self._json_response({"success": True, "venue": self._venue_view(venue)})
        except Exception as e:
            self._json_response({"success": False, "error": str(e)}, 500)

    def _serve_image(self, base_dir, raw: str):
        """Serve ảnh từ base_dir. Hỗ trợ ?w=<px> → resize (PIL) + cache trong _cache/ để nhẹ + nhanh."""
        from urllib.parse import unquote, urlparse, parse_qs
        parsed = urlparse(raw)
        name = unquote(parsed.path)
        try:
            w = int((parse_qs(parsed.query).get("w") or ["0"])[0])
        except Exception:
            w = 0
        fp = base_dir / name
        if not fp.exists() or not fp.is_file() or base_dir not in fp.parents:
            self.send_response(404); self._cors_headers(); self.end_headers(); return
        serve = fp
        if 0 < w <= 1600:
            try:
                cache = base_dir / "_cache"; cache.mkdir(parents=True, exist_ok=True)
                cp = cache / f"{w}_{fp.stem}.jpg"
                if (not cp.exists()) or cp.stat().st_mtime < fp.stat().st_mtime:
                    from PIL import Image
                    im = Image.open(fp)
                    if im.mode not in ("RGB", "L"):
                        im = im.convert("RGB")
                    ow, oh = im.size
                    if ow > w:
                        im = im.resize((w, max(1, round(oh * w / ow))), Image.LANCZOS)
                    im.save(cp, "JPEG", quality=82)
                if cp.exists():
                    serve = cp
            except Exception as e:
                print(f"[img] resize lỗi {name}: {e}", file=sys.stderr)
        mime = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                ".webp": "image/webp", ".gif": "image/gif", ".avif": "image/avif"}.get(serve.suffix.lower(), "application/octet-stream")
        self.send_response(200); self._cors_headers()
        self.send_header("Content-Type", mime)
        self.send_header("Cache-Control", "public, max-age=86400")
        self.send_header("Content-Length", str(serve.stat().st_size))
        self.send_header("Connection", "close"); self.end_headers()
        with open(serve, "rb") as f:
            while chunk := f.read(65536):
                self.wfile.write(chunk)
        self.close_connection = True

    def _serve_thumb(self, name: str):
        self._serve_image(THUMB_DIR, name)

    # ── Ảnh quán: cào Google Maps (APIFY) ─────────────────────────────────
    def handle_venue_scrape_images(self):
        try:
            from tools import venues_db
            vid = int((self._read_json_body() or {}).get("id"))
            venue = next((v for v in venues_db.get_all() if v["id"] == vid), None)
            if not venue:
                self._json_response({"success": False, "error": "Không thấy địa điểm."}, 404); return
            with _HEAVY_LOCK:
                from tools.venue_images_scrape import scrape_venue_images
                n = scrape_venue_images(venue)
            venue = next((v for v in venues_db.get_all() if v["id"] == vid), {})
            self._json_response({"success": True, "added": n, "venue": self._venue_view(venue)})
        except Exception as e:
            import traceback
            print(f"[Server] /venue-scrape-images error: {e}\n{traceback.format_exc()}", file=sys.stderr)
            self._json_response({"success": False, "error": str(e)}, 500)

    # ── Ảnh chung (album) ─────────────────────────────────────────────────
    @staticmethod
    def _album_view(im: dict) -> dict:
        return {**im, "url": f"/album-img/{Path(im['file']).name}"}

    def handle_images_get(self):
        try:
            from tools import album_db
            self._json_response({"success": True, "images": [self._album_view(i) for i in album_db.get_all()]})
        except Exception as e:
            self._json_response({"success": False, "error": str(e)}, 500)

    def handle_image_upload(self):
        try:
            from tools import album_db
            fields, files = parse_multipart(self)
            ALBUM_DIR.mkdir(parents=True, exist_ok=True)
            added = 0
            for fn in sorted(files):
                if not fn.startswith("image"):
                    continue
                filename, file_bytes = files[fn]
                ext = (Path(filename).suffix or ".jpg").lower()
                safe = "".join(c if c.isalnum() else "_" for c in Path(filename).stem)[:30]
                dest = ALBUM_DIR / f"up_{uuid.uuid4().hex[:8]}_{safe}{ext}"
                with open(dest, "wb") as f:
                    f.write(file_bytes)
                album_db.add(f"data/album/{dest.name}"); added += 1
            self._json_response({"success": True, "added": added,
                                 "images": [self._album_view(i) for i in album_db.get_all()]})
        except Exception as e:
            import traceback
            print(f"[Server] /image-upload error: {e}\n{traceback.format_exc()}", file=sys.stderr)
            self._json_response({"success": False, "error": str(e)}, 500)

    def handle_image_delete(self):
        try:
            from tools import album_db
            iid = int((self._read_json_body() or {}).get("id"))
            rel = album_db.delete_by_id(iid)
            if rel:
                fp = Path(__file__).parent / rel
                if fp.exists() and ALBUM_DIR in fp.parents:
                    try: fp.unlink()
                    except Exception: pass
            self._json_response({"success": True})
        except Exception as e:
            self._json_response({"success": False, "error": str(e)}, 500)

    def _serve_album(self, name: str):
        self._serve_image(ALBUM_DIR, name)

    def handle_publish_to_dashboard(self):
        """Publish content to dashboard via Supabase with Google Drive upload."""
        print("[Server] /publish-to-dashboard — Đăng nội dung lên Dashboard...", file=sys.stderr)
        try:
            data = self._read_json_body()
            
            # Extract data
            job_id = data.get("job_id", "")
            user_id = data.get("user_id", "")
            title = data.get("title", "")
            topic = data.get("topic", "")
            script = data.get("script", {})
            drive_url = data.get("drive_url", "")
            local_path = data.get("local_path", "")
            hook_style = data.get("hook_style", "")
            hook_text = data.get("hook_text", "")
            video_type = data.get("video_type", "video")
            
            if not job_id:
                self._json_response({"success": False, "error": "Thiếu job_id"}, 400)
                return
            
            # Try to upload to Google Drive if local_path exists
            actual_drive_url = drive_url
            if local_path and not drive_url:
                try:
                    from tools.drive_uploader import get_drive_uploader
                    uploader = get_drive_uploader()
                    # Resolve full path
                    full_path = local_path
                    if not os.path.isabs(full_path):
                        full_path = str(Path(__file__).parent / local_path.lstrip("/"))
                    
                    if os.path.exists(full_path):
                        print(f"[Server] Uploading to Google Drive: {full_path}", file=sys.stderr)
                        upload_result = uploader.upload_video(full_path, job_id)
                        if "webViewLink" in upload_result:
                            actual_drive_url = upload_result["webViewLink"]
                            print(f"[Server] ✓ Uploaded to Drive: {actual_drive_url}", file=sys.stderr)
                        elif "error" in upload_result:
                            print(f"[Server] ⚠ Drive upload failed: {upload_result['error']}", file=sys.stderr)
                    else:
                        print(f"[Server] ⚠ File not found: {full_path}", file=sys.stderr)
                except Exception as e:
                    print(f"[Server] ⚠ Google Drive upload error: {e}", file=sys.stderr)
            
            # Save to Supabase
            sb = _get_supabase()
            if sb and sb.url:
                content_data = {
                    "user_id": user_id if user_id else None,
                    "content_type": video_type,
                    "status": "pending",
                    "title": title,
                    "topic": topic,
                    "script": script,
                    "drive_url": actual_drive_url,
                    "local_path": local_path,
                    "hook_style": hook_style,
                    "hook_text": hook_text,
                    "job_id": job_id,
                    "video_type": video_type,
                }
                result = sb.create_content(content_data)
                if result and "id" in result:
                    print(f"[Server] ✅ Đã đăng lên Dashboard. Content ID: {result['id']}", file=sys.stderr)
                    self._json_response({
                        "success": True,
                        "content_id": result["id"],
                        "drive_url": actual_drive_url,
                        "message": "Đã đăng nội dung lên Dashboard thành công"
                    })
                else:
                    print(f"[Server] ❌ Lỗi đăng lên Dashboard: {result}", file=sys.stderr)
                    self._json_response({"success": False, "error": f"Lỗi Supabase: {result}"}, 500)
            else:
                # Fallback: save to local products.json
                print("[Server] Supabase not configured, saving to local products.json", file=sys.stderr)
                import time as _t
                _append_product({
                    "user": data.get("user", ""),
                    "topic": topic,
                    "hook_style": hook_style,
                    "video_url": drive_url or local_path,
                    "time": _t.time(),
                    "status": "pending",
                })
                self._json_response({
                    "success": True,
                    "message": "Đã lưu vào products.json (Supabase chưa cấu hình)"
                })
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(f"[Server] /publish-to-dashboard error: {e}\n{tb}", file=sys.stderr)
            self._json_response({"success": False, "error": str(e), "traceback": tb}, 500)


def main():
    import socket
    import sys

    # Check if running in a virtual environment
    in_venv = sys.prefix != sys.base_prefix
    if not in_venv:
        print("""
==============================================================
⚠ CẢNH BÁO: Bạn đang chạy server bằng Python hệ thống (Global)!
Một số thư viện như 'edge-tts' hay 'pymongo' sẽ báo thiếu.
Vui lòng chạy server bằng Python của môi trường ảo (.venv):

👉 Chạy lệnh: .venv\\Scripts\\python.exe server.py
==============================================================
""", file=sys.stderr)

    # Kill any old process still holding port 7788
    # (Handles cases where previous server didn't shut down cleanly)
    try:
        test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_sock.connect(("127.0.0.1", PORT))
        test_sock.close()
        print(f"[Server] WARNING: Port {PORT} already in use! Kill the old process first.", file=sys.stderr)
        print(f"[Server] Run: netstat -ano | findstr :{PORT}   then   taskkill /F /PID <pid>", file=sys.stderr)
        sys.exit(1)
    except ConnectionRefusedError:
        pass  # Port is free, good

    class ReusableHTTPServer(ThreadingHTTPServer):
        allow_reuse_address = True
        daemon_threads = True

    print("""
+------------------------------------------------------+
|    DuLich Pipeline -- Local Assembly Server          |
|    Endpoint: POST http://localhost:7788/assemble     |
+------------------------------------------------------+
""", file=sys.stderr)

    _start_news_scheduler()
    _start_telegram_poller()
    _start_daily_scheduler()
    server = ReusableHTTPServer(("127.0.0.1", PORT), AssembleHandler)
    print(f"[Server] Listening at http://localhost:{PORT}", file=sys.stderr)
    print(f"[Server] Press Ctrl+C to stop.", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[Server] Shutting down...", file=sys.stderr)
        server.shutdown()
        server.server_close()
        print("[Server] Stopped.", file=sys.stderr)


# ── Bộ hẹn giờ cào tin (3 khung: 05h, 11h, 18h) — chạy khi server sống (VPS) ────
NEWS_SLOTS = (5, 11, 18)


def _news_scheduler():
    import time as _t
    last = ""
    while True:
        try:
            lt = _t.localtime()
            slot = f"{lt.tm_year}-{lt.tm_mon}-{lt.tm_mday}-{lt.tm_hour}"
            if lt.tm_hour in NEWS_SLOTS and lt.tm_min < 3 and slot != last:
                last = slot
                try:
                    from tools.news_youtube import scrape_news, save_pool
                    print(f"[news] scheduler cào tin (khung {lt.tm_hour}h)...", file=sys.stderr)
                    with _HEAVY_LOCK:
                        res = scrape_news()
                    if res.get("success"):
                        save_pool(res)
                        print(f"[news] cào xong: {res.get('count')} video", file=sys.stderr)
                except Exception as e:
                    print(f"[news] scheduler lỗi: {e}", file=sys.stderr)
        except Exception:
            pass
        _t.sleep(60)


def _start_news_scheduler():
    threading.Thread(target=_news_scheduler, daemon=True).start()
    print(f"[Server] News scheduler bật (khung {NEWS_SLOTS} giờ).", file=sys.stderr)


# ── Tự động mỗi ngày: 5 album ảnh (1/nv) + kịch bản chờ mỗi nv+tin tức ─────────
DAILY_SLOT_HOUR = 6


def _daily_auto_job():
    """Tạo trước 1 album ảnh/nv (không lặp seed gần đây) + 1 kịch bản chờ/nv+tin tức,
    lưu vào 'Ảnh'/'Video' để người dùng vào chỉ việc thả clip. Báo admin qua Telegram."""
    from tools.script_drafts import add_draft
    users = _load_users()
    made_albums, made_scripts = [], []

    for uid, u in users.items():
        if u.get("role") not in ("staff", "news"):
            continue
        # 1) album ảnh (staff có handle album)
        albs = _albums_for(uid)
        if albs:
            import random
            pick = random.choice(albs)
            res = _generate_album(pick["id"], uid, auto=True)
            if res.get("success"):
                made_albums.append(f"{u.get('name', uid)} · {pick['label']}")
            else:
                print(f"[daily] album lỗi {uid}: {res.get('error')}", file=sys.stderr)
        # 2) kịch bản chờ
        try:
            if u.get("role") == "staff":
                from tools.listreview_content import build_prefill
                pf = build_prefill(uid, regen=True)
                if pf.get("scenes"):
                    add_draft(uid, pf["scenes"], pf.get("hook_style", "hook_red"),
                              pf.get("badge_mode", "none"), pf.get("transition", "fade"),
                              pf.get("overlay_engine", "pil"), pf.get("style", ""),
                              pf.get("generated_by", "auto"))
                    made_scripts.append(u.get("name", uid))
            else:  # news
                from tools.script_ai import generate_script_ai
                sc = generate_script_ai("tin tức / review Đà Lạt", employee=uid)
                if sc:
                    scenes = [
                        {"scene_id": "scene_1", "kind": "intro", "label": "HOOK",
                         "title": sc.get("title", ""), "caption": sc.get("hook", "")},
                        {"scene_id": "scene_2", "kind": "spot", "label": "NỘI DUNG",
                         "caption": sc.get("body", "")},
                        {"scene_id": "scene_3", "kind": "outro", "label": "CTA",
                         "caption": sc.get("cta", "")},
                    ]
                    add_draft(uid, scenes, "hook_news", "none", "fade", "pil", "", "auto")
                    made_scripts.append(u.get("name", uid))
        except Exception as e:
            print(f"[daily] kịch bản lỗi {uid}: {e}", file=sys.stderr)

    try:
        from tools import publisher
        lines = ["🗓 <b>Tự động hôm nay đã tạo:</b>"]
        lines.append("🖼 Album: " + (", ".join(made_albums) if made_albums else "không có"))
        lines.append("📝 Kịch bản chờ: " + (", ".join(made_scripts) if made_scripts else "không có"))
        publisher.send_telegram("\n".join(lines))
    except Exception as e:
        print(f"[daily] telegram báo lỗi: {e}", file=sys.stderr)


def _daily_scheduler():
    import time as _t
    last = ""
    while True:
        try:
            lt = _t.localtime()
            slot = f"{lt.tm_year}-{lt.tm_mon}-{lt.tm_mday}"
            if lt.tm_hour == DAILY_SLOT_HOUR and lt.tm_min < 3 and slot != last:
                last = slot
                print("[daily] chạy tự động tạo album + kịch bản...", file=sys.stderr)
                _daily_auto_job()
        except Exception as e:
            print(f"[daily] scheduler lỗi: {e}", file=sys.stderr)
        _t.sleep(60)


def _start_daily_scheduler():
    threading.Thread(target=_daily_scheduler, daemon=True).start()
    print(f"[Server] Daily auto scheduler bật ({DAILY_SLOT_HOUR}h).", file=sys.stderr)


if __name__ == "__main__":
    main()
