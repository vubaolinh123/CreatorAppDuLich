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
    "hien1": {"script": "generate_hien25111.py", "seed": True,  "label": "Hiền · Album 1"},
    "hien2": {"script": "generate_hien21113.py", "seed": True,  "label": "Hiền · Album 2"},
    "le1":   {"script": "demo_mye26.py",          "seed": True,  "label": "Lê · Album 1"},
    "le2":   {"script": "generate_le2.py",        "seed": True,  "label": "Lê · Album 2"},
    "muoi1": {"script": "generate_muoi1912.py",   "seed": True,  "label": "Muối · Album 1"},
    "muoi2": {"script": "generate_muoi1311.py",   "seed": True,  "label": "Muối · Album 2"},
    "vy1":   {"script": "generate_vy1.py",        "seed": True,  "label": "Vy · Album 1"},
    "vy2":   {"script": "generate_hien19111.py",  "seed": True,  "label": "Vy · Album 2"},
    "uyen1": {"script": "generate_uyen1tip.py",   "seed": True,  "label": "Uyên · Album 1"},
    "uyen2": {"script": "generate_uyen2.py",      "seed": True,  "label": "Uyên · Album 2"},
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


def _generate_album(album: str, user: str = "", auto: bool = False,
                    title_prompt: str = "") -> dict:
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
    if title_prompt.strip():
        env["ALBUM_TITLE_PROMPT"] = title_prompt.strip()[:500]

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
    {"key": "OPENROUTER_KEY",    "label": "OpenRouter",      "group": "AI viết kịch bản + caption",
     "desc": "AI viết script, title album, caption đăng bài. Thiếu → dùng nội dung mẫu.", "link": "https://openrouter.ai/keys"},
    {"key": "VBEE_API_KEY",      "label": "Vbee API key (Voice)", "group": "Giọng đọc Vbee",
     "desc": "Giọng clone tiếng Việt. Thiếu → fallback Edge (free).", "link": "https://vbee.vn"},
    {"key": "VBEE_APP_ID",       "label": "Vbee Account ID (App ID)", "group": "Giọng đọc Vbee",
     "desc": "Đi kèm Vbee API key.", "link": "https://vbee.vn"},
    {"key": "OPENAI_API_KEY",    "label": "OpenAI",          "group": "Phụ đề",
     "desc": "Whisper đọc voice để ghép phụ đề chính xác.", "link": "https://platform.openai.com/api-keys"},
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

# ── Render NỀN: hàng đợi tuần tự — bấm render là vào queue, logout vẫn chạy ────
import queue as _queue
_RENDER_QUEUE: "_queue.Queue" = _queue.Queue()
_RENDER_JOBS: dict = {}          # job_id → {user, topic, status, error, video_url, time}
_RENDER_JOBS_LOCK = threading.Lock()


def _job_update(job_id: str, **kw) -> None:
    with _RENDER_JOBS_LOCK:
        _RENDER_JOBS.setdefault(job_id, {})
        _RENDER_JOBS[job_id].update(kw)


def _is_transient_render_err(e) -> bool:
    """Lỗi tạm thời (đáng thử lại): timeout do server bận, không phải source hỏng."""
    low = str(e or "").lower()
    return "quá thời gian" in low or "timeout" in low


def _render_worker():
    """Worker nền: render từng job trong queue (sống độc lập với session người dùng).
    Số worker song song = env RENDER_WORKERS (mặc định 1)."""
    n_workers = max(1, int(os.getenv("RENDER_WORKERS", "1") or 1))
    while True:
        job = _RENDER_QUEUE.get()
        jid = job["job_id"]
        _job_update(jid, status="rendering")
        print(f"[render-queue] bắt đầu {jid} (user {job.get('user')})", file=sys.stderr)

        def _render_once():
            if n_workers == 1:
                with _HEAVY_LOCK:
                    for m in list(sys.modules.keys()):
                        if m.startswith("tools.list_review_render"):
                            sys.modules.pop(m, None)
                    from tools.list_review_render import render_list_review
                    return render_list_review(job["spec"])
            # nhiều worker: không reload module (không thread-safe), không giữ _HEAVY_LOCK
            from tools.list_review_render import render_list_review
            return render_list_review(job["spec"])

        try:
            # Render + tự thử lại 1 lần nếu lỗi TẠM THỜI (timeout do server bận).
            # Retry chạy inline trước finally → temp_dir còn nguyên, không cần re-queue.
            result = None
            for attempt in (1, 2):
                try:
                    result = _render_once()
                except Exception as e:
                    if attempt == 1 and _is_transient_render_err(e):
                        print(f"[render-queue] {jid} lỗi tạm ({e}) → thử lại (lần 2)", file=sys.stderr)
                        continue
                    raise
                if (attempt == 1 and not result.get("success")
                        and _is_transient_render_err(result.get("error"))):
                    print(f"[render-queue] {jid} fail tạm → thử lại (lần 2)", file=sys.stderr)
                    continue
                break
            if result.get("success"):
                video_url = _to_output_url(result.get("video_path", ""))
                thumb_url = _to_output_url(result.get("thumb_path", ""))
                preview_url = _to_output_url(result.get("preview_path", ""))
                _job_update(jid, status="done", video_url=video_url, thumb_url=thumb_url)
                try:
                    import time as _t
                    _append_product({"user": job["user"], "topic": job["topic"],
                                     "hook_style": job.get("hook_style", ""),
                                     "video_url": video_url, "thumb_url": thumb_url,
                                     "preview_url": preview_url,
                                     "time": _t.time()})
                except Exception as _e:
                    print(f"[render-queue] product log lỗi: {_e}", file=sys.stderr)
                # Kịch bản đã render xong → đánh dấu "đã render" (vào Lưu trữ, không xóa)
                if job.get("draft_id"):
                    try:
                        from tools.script_drafts import mark_used
                        mark_used(job["draft_id"])
                    except Exception as _e:
                        print(f"[render-queue] mark draft lỗi: {_e}", file=sys.stderr)
                print(f"[render-queue] ✓ xong {jid}: {video_url}", file=sys.stderr)
            else:
                _job_update(jid, status="failed", error=_friendly_error(result.get("error", "render fail")))
                print(f"[render-queue] ✗ {jid}: {result.get('error')}", file=sys.stderr)
        except Exception as e:
            import traceback
            print(f"[render-queue] ✗ {jid}: {e}\n{traceback.format_exc()}", file=sys.stderr)
            _job_update(jid, status="failed", error=_friendly_error(e))
        finally:
            def _cleanup(p=job.get("temp_dir")):
                import time as _t
                _t.sleep(60)
                if p:
                    shutil.rmtree(str(p), ignore_errors=True)
            threading.Thread(target=_cleanup, daemon=True).start()


def _start_render_worker():
    n = max(1, int(os.getenv("RENDER_WORKERS", "1") or 1))
    for _ in range(n):
        threading.Thread(target=_render_worker, daemon=True).start()
    print(f"[Server] Render queue nền bật ({n} worker).", file=sys.stderr)

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
        cause = ("⏱ Render lâu quá — server đang bận (nhiều clip cùng lúc) hoặc clip quá nặng. "
                 "Hệ thống đã tự thử lại 1 lần; thử render lại sau ít phút.")
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


# ── Đăng bài (Zernio TikTok) ────────────────────────────────────────────────

# Key Zernio/Apify RIÊNG từng tài khoản (admin nhập ở Cài đặt) — data/user_keys.json
USER_KEYS_FILE = Path(__file__).parent / "data" / "user_keys.json"
_USER_KEYS_LOCK = threading.Lock()


def _load_user_keys() -> dict:
    try:
        return json.loads(USER_KEYS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_user_keys(d: dict) -> None:
    with _USER_KEYS_LOCK:
        USER_KEYS_FILE.parent.mkdir(parents=True, exist_ok=True)
        USER_KEYS_FILE.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def _user_zernio_keys(user: str) -> list:
    """Danh sách key Zernio của nv (mỗi nv có thể nhiều key). Migrate key đơn cũ.
    Rỗng → fallback ZERNIO_KEY chung (1 phần tử)."""
    rec = _load_user_keys().get(user) or {}
    keys = rec.get("zernio_keys")
    if not isinstance(keys, list):
        old = (rec.get("zernio_key") or "").strip()
        keys = [old] if old else []
    keys = [k.strip() for k in keys if (k or "").strip()]
    if keys:
        return keys
    g = (os.getenv("ZERNIO_KEY") or "").strip()
    return [g] if g else []


def _user_zernio(user: str, ki: int = 0) -> str:
    """1 key Zernio theo index (mặc định key đầu)."""
    keys = _user_zernio_keys(user)
    return keys[ki] if 0 <= ki < len(keys) else (keys[0] if keys else "")


def _user_apify(user: str) -> str:
    k = ((_load_user_keys().get(user) or {}).get("apify_key") or "").strip()
    return k or (os.getenv("APIFY_API_KEY") or "").strip()


def _is_publish_user(user: str) -> bool:
    """NV có key Zernio (riêng hoặc chung + cờ publish cũ) là đăng được."""
    if _user_zernio_keys(user):
        u = _load_users().get(user) or {}
        # có key riêng → luôn cho đăng; nếu chỉ có key chung thì cần cờ publish
        rec = _load_user_keys().get(user) or {}
        own = rec.get("zernio_keys") or ([rec["zernio_key"]] if rec.get("zernio_key") else [])
        if any((k or "").strip() for k in own):
            return True
        return (u.get("publish") or "").lower() == "tiktok"
    return False


_CAPTION_TAGS = "#reviewdalat #dalatdiary #dalatstory #dulichdalat"
_CAPTION_TAGS_SHORT = "#reviewdalat #dulichdalat"


def _caption_for(topic: str, user: str = "", photo: bool = False) -> str:
    """Caption ngắn kiểu tâm tình + hashtag. AI viết (DeepSeek), fail → mẫu đơn giản.
    photo=True: TikTok cap 90 ký tự cho bài ảnh → viết cực ngắn + ít hashtag."""
    topic = (topic or "").strip()
    limit_words = "tối đa 8 từ" if photo else "tối đa 20 từ"
    tags = _CAPTION_TAGS_SHORT if photo else _CAPTION_TAGS
    key = os.getenv("OPENROUTER_KEY") or os.getenv("OPENROUTER_API_KEY")
    cap = ""
    if key:
        try:
            import requests as _rq, random as _rd
            r = _rq.post(
                "https://openrouter.ai/api/v1/chat/completions", timeout=25,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"model": "deepseek/deepseek-chat", "temperature": 1.0, "max_tokens": 120,
                      "messages": [
                          {"role": "system", "content": "Bạn là người viết caption TikTok du lịch Đà Lạt."},
                          {"role": "user", "content":
                           f"Viết 1 caption TikTok NGẮN GỌN (1 câu, {limit_words}, giọng gần gũi tâm tình, "
                           "không emoji, không hashtag) cho nội dung về Đà Lạt"
                           + (f" chủ đề: {topic}." if topic else ".")
                           + ' Ví dụ phong cách: "Anh sẽ ở đây giúp các em có những kỉ niệm toẹt vời tại Đà Lạt mộng mơ". '
                           "Chỉ trả về đúng câu caption."
                           + f" (seed: {_rd.randint(100, 999)})"}]})
            if r.status_code == 200:
                cap = r.json()["choices"][0]["message"]["content"].strip().strip('"')
        except Exception as e:
            print(f"[pub] caption AI lỗi: {e}", file=sys.stderr)
    if not cap:
        cap = topic
    out = f"{cap} {tags}".strip() if cap else tags
    if photo and len(out) > 90:   # TikTok photo: content = slideshow title, max 90 ký tự
        out = f"{cap} {_CAPTION_TAGS_SHORT}".strip()
        if len(out) > 90:
            out = cap[:90].strip()
    return out


# Gợi ý chủ đề theo loại album (khi label cover chưa nói rõ) — để caption + hashtag đúng ngữ cảnh.
_ALBUM_KIND_CAT = {
    "le1": "lịch trình du lịch Đà Lạt",
    "le2": "review địa điểm Đà Lạt",
    "hien1": "bản đồ món ngon, quán ăn Đà Lạt",
    "hien2": "điểm check-in Đà Lạt",
    "muoi1": "quán cà phê, ăn sáng, điểm check-in Đà Lạt",
    "muoi2": "quán cà phê, ăn sáng, điểm check-in Đà Lạt",
    "vy1": "quán ăn, cà phê, điểm check-in Đà Lạt",
    "vy2": "quán ăn, cà phê, điểm check-in Đà Lạt",
    "uyen1": "tips du lịch Đà Lạt",
    "uyen2": "review du lịch Đà Lạt",
}
_ALBUM_CAPTION_FALLBACK_TAGS = "#dalat #checkindalat #dulichdalat #reviewdalat"


def _album_caption(rec: dict) -> str:
    """Caption sáng tạo + hashtag cho BÀI ẢNH album, viết bằng OpenRouter, dựa trên chủ đề album.
    VD: 'Những quán cafe mới toanh ở Đà Lạt☕️✨ #dalat #checkindalat #cafedalat'.
    Fail → dùng label + hashtag mẫu. Giới hạn ~90 ký tự (TikTok photo = tiêu đề slideshow)."""
    import re as _re
    label = _re.sub(r"^[^·]+·\s*", "", (rec.get("label") or "").strip()).strip()
    cat = _ALBUM_KIND_CAT.get((rec.get("album") or "").strip(), "")
    theme = " – ".join([x for x in (label, cat) if x]) or "địa điểm Đà Lạt"

    key = os.getenv("OPENROUTER_KEY") or os.getenv("OPENROUTER_API_KEY")
    out = ""
    if key:
        try:
            import requests as _rq, random as _rd
            r = _rq.post(
                "https://openrouter.ai/api/v1/chat/completions", timeout=25,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"model": "deepseek/deepseek-chat", "temperature": 1.0, "max_tokens": 120,
                      "messages": [
                          {"role": "system", "content":
                           "Bạn viết caption cho bài ảnh (slideshow) du lịch Đà Lạt, giọng trẻ trung bắt trend."},
                          {"role": "user", "content":
                           f"Viết caption cho 1 bài ảnh về Đà Lạt. Chủ đề: {theme}.\n"
                           "- 1 câu ngắn, sáng tạo, giọng gần gũi/bắt trend, được dùng 1-2 emoji hợp ngữ cảnh.\n"
                           "- Ngay sau đó thêm 3-5 hashtag tiếng Việt KHÔNG DẤU, liền mạch trên cùng dòng, "
                           "bắt buộc có #dalat và hashtag theo chủ đề (vd #cafedalat #checkindalat #anuongdalat #sanmaydalat).\n"
                           "- TỔNG độ dài cả hashtag không quá 90 ký tự. Chỉ tiếng Việt + emoji + hashtag, không giải thích.\n"
                           'Ví dụ phong cách: "Những quán cafe mới toanh ở Đà Lạt☕️✨ #dalat #checkindalat #cafedalat"\n'
                           f"Chỉ trả về đúng caption. (seed: {_rd.randint(100, 999)})"}]})
            if r.status_code == 200:
                out = r.json()["choices"][0]["message"]["content"].strip().strip('"')
                out = " ".join(out.split())   # gộp về 1 dòng
        except Exception as e:
            print(f"[pub] album caption AI lỗi: {e}", file=sys.stderr)
    if not out:
        base = label or "Đà Lạt trong tim"
        out = f"{base} {_ALBUM_CAPTION_FALLBACK_TAGS}".strip()
    if len(out) > 90:   # cắt bớt hashtag cuối cho vừa, không cắt giữa câu
        while len(out) > 90 and "#" in out and out.rfind(" #") > 0:
            out = out[:out.rfind(" #")].rstrip()
        if len(out) > 90:
            out = out[:90].rstrip()
    return out


def _update_product(video_url: str, **fields) -> None:
    with _PROD_LOCK:
        items = _load_products()
        for p in items:
            if p.get("video_url") == video_url:
                p.update(fields)
        PRODUCTS_FILE.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def _archive_video(video_url: str, delay_sec: int = 900) -> None:
    """Sau khi ĐĂNG xong: chờ delay (Zernio kịp tải video) → upload Google Drive
    → ghi drive_link vào record → xóa mp4 local (giải phóng disk). Fail → giữ file."""
    def _job():
        import time as _t
        _t.sleep(delay_sec)
        try:
            local = Path(__file__).parent / video_url.lstrip("/")
            if not local.exists():
                return
            from tools.drive_uploader import get_drive_uploader
            up = get_drive_uploader()
            folder = up.create_subfolder(f"posted/{_t.strftime('%Y-%m')}")
            if not folder:
                print(f"[archive] không tạo được folder Drive → giữ {video_url}", file=sys.stderr)
                return
            res = up.upload_file(str(local), folder)
            if res.get("error"):
                print(f"[archive] upload fail ({str(res['error'])[:120]}) → giữ {video_url}", file=sys.stderr)
                return
            _update_product(video_url, drive_link=res.get("webViewLink", ""), archived=True)
            local.unlink(missing_ok=True)
            print(f"[archive] ✓ {video_url} → Drive, đã xóa local", file=sys.stderr)
        except Exception as e:
            print(f"[archive] lỗi {video_url}: {e}", file=sys.stderr)
    threading.Thread(target=_job, daemon=True).start()


def _do_publish(video_url: str, caption: str, user: str,
                ki: int = 0, account_id: str = "") -> dict:
    """Đăng TikTok qua Zernio (key ki của nv, account_id đã chọn) + cập nhật status."""
    try:
        from tools import publisher
        res = publisher.post_to_tiktok(video_url, caption,
                                       api_key=_user_zernio(user, ki),
                                       account_id=account_id or None)
    except Exception as e:
        res = {"success": False, "error": str(e)}
    _set_product_status(video_url, "posted" if res.get("success") else "failed")
    if res.get("success"):
        _archive_video(video_url)   # 15 phút sau tự đẩy Drive + xóa local
    return res


def _do_publish_album(dir_rel: str, user: str,
                      ki: int = 0, account_id: str = "") -> dict:
    """Đăng bộ ảnh album lên TikTok (carousel) qua Zernio key ki + account_id đã chọn."""
    rec = next((a for a in _load_albums() if a.get("dir") == dir_rel), None)
    urls = [im.get("url", "") for im in (rec or {}).get("images", []) if im.get("url")]
    if not urls:
        return {"success": False, "error": "Album không có ảnh"}
    caption = _album_caption(rec)   # caption sáng tạo + hashtag theo chủ đề album (OpenRouter)
    try:
        from tools import publisher
        res = publisher.post_images_to_tiktok(urls, caption,
                                              api_key=_user_zernio(user, ki),
                                              account_id=account_id or None)
    except Exception as e:
        res = {"success": False, "error": str(e)}
    _set_album_status(dir_rel, "posted" if res.get("success") else "failed")
    return res


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
        elif self.path == "/ai-image-from-link":
            self.handle_ai_image_from_link()
        elif self.path == "/settings":
            self.handle_settings_save()
        elif self.path == "/user-keys":
            self.handle_user_keys_save()
        elif self.path == "/news-use":
            self.handle_news_use()
        elif self.path == "/script-from-text":
            self.handle_script_from(mode="text")
        elif self.path == "/script-from-link":
            self.handle_script_from(mode="link")
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
        if self.path.split("?", 1)[0] in ("/", "/app", "/index.html",
                                          "/trang-chu", "/video", "/thu-vien", "/anh", "/cai-dat"):
            self._serve_index()   # SPA routes → trả index.html để refresh/bookmark không 404
        elif self.path == "/settings":
            self.handle_settings_get()
        elif self.path == "/user-keys":
            self.handle_user_keys_get()
        elif self.path.startswith("/zernio-accounts"):
            self.handle_zernio_accounts()
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
        elif self.path.startswith("/render-jobs"):
            self.handle_render_jobs()
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
            # Ảnh + ?w=<px> → resize/cache (cover album là PNG 1-3MB, lưới duyệt bài không kham nổi)
            raw = self.path[len("/output/"):]
            if "?w=" in raw and Path(raw.split("?", 1)[0]).suffix.lower() in (
                    ".png", ".jpg", ".jpeg", ".webp"):
                self._serve_image(Path(__file__).parent / "output", raw)
                return
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
                fsize = file_path.stat().st_size
                # HTTP Range (206) — cho video phát/tua ngay như YouTube (không tải cả file).
                # Chỉ xử lý single-range "bytes=a-b"; bất thường → gửi full 200 (fallback an toàn).
                rng = self.headers.get("Range", "")
                start, end = 0, fsize - 1
                use_range = False
                if rng.startswith("bytes=") and "," not in rng:
                    try:
                        s, e = rng[6:].split("-", 1)
                        if s.strip() == "":            # bytes=-N → N byte cuối
                            start = max(0, fsize - int(e))
                        else:
                            start = int(s)
                            if e.strip() != "":
                                end = min(int(e), fsize - 1)
                        if 0 <= start <= end < fsize:
                            use_range = True
                    except Exception:
                        use_range = False
                if use_range and start > end:            # range không thoả mãn
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{fsize}")
                    self._cors_headers(); self.end_headers()
                    return
                length = (end - start + 1) if use_range else fsize
                self.send_response(206 if use_range else 200)
                self._cors_headers()
                self.send_header("Content-Type", mime)
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Content-Length", str(length))
                if use_range:
                    self.send_header("Content-Range", f"bytes {start}-{end}/{fsize}")
                self.send_header("Connection", "close")
                self.end_headers()
                if self.command == "HEAD":
                    self.close_connection = True
                    return
                remaining = length
                with open(file_path, "rb") as f:
                    if use_range:
                        f.seek(start)
                    while remaining > 0:
                        chunk = f.read(min(65536, remaining))
                        if not chunk:
                            break
                        try:
                            self.wfile.write(chunk)
                        except (BrokenPipeError, ConnectionResetError):
                            break   # player đóng kết nối khi tua/dừng — bình thường
                        remaining -= len(chunk)
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
        since = float((q.get("since") or ["0"])[0] or 0)
        limit = int((q.get("limit") or ["0"])[0] or 0)
        items = _load_products()
        if user and role not in ("admin",):
            items = [p for p in items if p.get("user") == user]
        if since:
            items = [p for p in items if p.get("time", 0) >= since]
        items.sort(key=lambda x: x.get("time", 0), reverse=True)
        total = len(items)
        if limit > 0:
            items = items[:limit]
        self._json_response({"videos": items, "total": total})

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

        # Guard: cảnh nào SẼ render (có lời thoại) mà thiếu clip → render ra nền navy (blue screen) như
        # bug nv2/nv3. Báo lỗi rõ ngay thay vì âm thầm tạo video hỏng. Log số clip từng cảnh để soi upload lỗi.
        def _has_vo(seg):
            return bool((seg.get("vo") or "").strip())
        _counts, missing = {}, []
        _scenes = ([("Hook", spec["intro"])]
                   + [(spec["spots"][i].get("name") or f"Cảnh {i+1}", sp) for i, sp in enumerate(spec["spots"])]
                   + [("Outro", spec["outro"])])
        for name, seg in _scenes:
            n = len(seg.get("clips") or [])
            _counts[name] = n
            if _has_vo(seg) and n == 0:
                missing.append(name)
        print(f"[Server] /assemble-listreview clip mỗi cảnh: {_counts}", file=sys.stderr)
        if missing:
            shutil.rmtree(str(job_temp), ignore_errors=True)
            self._json_response({"success": False,
                                 "error": "Thiếu footage ở: " + ", ".join(missing) +
                                 ". Thêm clip cho các cảnh này rồi render lại (đừng để trống)."}, 400)
            return

        # RENDER NỀN: đưa vào hàng đợi tuần tự rồi trả lời ngay — logout vẫn render tiếp.
        try:
            import time as _t
            _topic = intro.get("title", "") or "List review"
            position = _RENDER_QUEUE.qsize() + 1
            _job_update(job_id, user=user, topic=_topic, status="queued",
                        error="", video_url="", time=_t.time())
            _RENDER_QUEUE.put({"job_id": job_id, "spec": spec, "user": user,
                               "topic": _topic, "hook_style": hook_style,
                               "draft_id": fields.get("draft_id", ""),
                               "temp_dir": job_temp})
            print(f"[Server] /assemble-listreview → queue {job_id} (vị trí {position})", file=sys.stderr)
            self._json_response({"success": True, "queued": True,
                                 "job_id": job_id, "position": position})
        except Exception as e:
            import traceback
            print(f"[Server] ❌ queue lỗi: {e}\n{traceback.format_exc()}", file=sys.stderr)
            shutil.rmtree(str(job_temp), ignore_errors=True)
            self._json_response({"success": False, "error": _friendly_error(e)}, 500)

    def handle_render_jobs(self):
        """GET /render-jobs?user= → trạng thái job render của user (admin: tất cả)."""
        from urllib.parse import urlparse, parse_qs
        q = parse_qs(urlparse(self.path).query)
        user = (q.get("user", [""])[0] or "").strip()
        role = (q.get("role", [""])[0] or "").strip()
        with _RENDER_JOBS_LOCK:
            jobs = [{"job_id": k, **v} for k, v in _RENDER_JOBS.items()
                    if role == "admin" or v.get("user") == user]
        jobs.sort(key=lambda j: j.get("time", 0), reverse=True)
        self._json_response({"success": True, "jobs": jobs[:30],
                             "queue_len": _RENDER_QUEUE.qsize()})

    def handle_assemble_image(self):
        """POST /assemble-image {album, user} → chạy script CLI dựng album ảnh, lưu lại, trả list ảnh PNG."""
        try:
            body = self._read_json_body()
            album = (body.get("album") or "").strip()
            user = (body.get("user") or "").strip()
            title_prompt = (body.get("title_prompt") or "").strip()
            res = _generate_album(album, user, title_prompt=title_prompt)
            self._json_response(res, 200 if res.get("success") else (400 if "hợp lệ" in res.get("error", "") else 500))
        except subprocess.TimeoutExpired:
            self._json_response({"success": False, "error": "Quá thời gian (300s)."}, 500)
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(f"[Server] ❌ assemble-image lỗi: {e}\n{tb}", file=sys.stderr)
            self._json_response({"success": False, "error": str(e)}, 500)

    def handle_script_from(self, mode: str):
        """POST /script-from-text {user,text} | /script-from-link {user,url}
        → AI tạo scenes chuẩn editor + lưu Kịch bản chờ, trả scenes để nạp thẳng."""
        try:
            b = self._read_json_body()
            user = (b.get("user") or "").strip() or "nv1"
            from tools.script_import import scenes_from_text, scenes_from_link
            if mode == "text":
                scenes = scenes_from_text(b.get("text") or "")
                src = "paste"
            else:
                url = (b.get("url") or "").strip()
                if not url.startswith("http"):
                    self._json_response({"success": False, "error": "Link không hợp lệ"}, 400)
                    return
                with _HEAVY_LOCK:   # tải audio + whisper — tránh chạy chồng
                    scenes = scenes_from_link(url, employee=user)
                src = f"link:{url}"
            if not scenes:
                self._json_response({"success": False,
                                     "error": "AI không tạo được kịch bản (kiểm tra OPENROUTER_KEY/nội dung)"}, 500)
                return
            try:
                from tools.script_drafts import add_draft
                from tools.listreview_content import _TEMPLATES, _DEFAULT_TEMPLATE
                tpl = _TEMPLATES.get(user, _DEFAULT_TEMPLATE)
                add_draft(user, scenes, "hook_red", tpl["badge_mode"], tpl["transition"],
                          "pil", "", src)
            except Exception as _e:
                print(f"[script-from] lưu draft lỗi: {_e}", file=sys.stderr)
            self._json_response({"success": True, "scenes": scenes})
        except Exception as e:
            import traceback
            print(f"[Server] script-from-{mode} lỗi: {e}\n{traceback.format_exc()}", file=sys.stderr)
            self._json_response({"success": False, "error": _friendly_error(e)}, 500)

    def handle_news_use(self):
        """POST /news-use {url, title} → AI viết kịch bản video từ 1 tin → lưu Kịch bản chờ (tintuc)."""
        try:
            b = self._read_json_body()
            title = (b.get("title") or "").strip()
            url = (b.get("url") or "").strip()
            if not title:
                self._json_response({"success": False, "error": "Tin không có tiêu đề"}, 400)
                return
            from tools.script_ai import generate_script_ai
            from tools.script_drafts import add_draft
            sc = generate_script_ai(f"tin tức Đà Lạt: {title}", employee="tintuc")
            if not sc:
                self._json_response({"success": False, "error": "AI không viết được kịch bản (kiểm tra OPENROUTER_KEY)"}, 500)
                return
            scenes = [
                {"scene_id": "scene_1", "kind": "intro", "label": "HOOK",
                 "title": sc.get("title", title), "caption": sc.get("hook", "")},
                {"scene_id": "scene_2", "kind": "spot", "label": "NỘI DUNG",
                 "caption": sc.get("body", "")},
                {"scene_id": "scene_3", "kind": "outro", "label": "CTA",
                 "caption": sc.get("cta", "")},
            ]
            add_draft("tintuc", scenes, "hook_news", "none", "fade", "pil", "",
                      f"news:{url}" if url else "news")
            self._json_response({"success": True, "title": sc.get("title", title)})
        except Exception as e:
            import traceback
            print(f"[Server] news-use lỗi: {e}\n{traceback.format_exc()}", file=sys.stderr)
            self._json_response({"success": False, "error": str(e)}, 500)

    def handle_ai_image_from_link(self):
        """POST /ai-image-from-link {user, url} — bài ảnh carousel TikTok mẫu →
        AI vẽ lại Y HỆT TỪNG ảnh (Nano Banana Pro), đúng số lượng ảnh trong link, watermark @dalatnow."""
        try:
            b = self._read_json_body()
            user = (b.get("user") or "").strip() or "admin"
            url = (b.get("url") or "").strip()
            if "tiktok.com" not in url:
                self._json_response({"success": False, "error": "Dán link bài ẢNH TikTok"}, 400)
                return

            # Chạy NỀN: bài nhiều ảnh mất vài phút (mỗi ảnh ~30-45s) → vượt timeout nginx nếu đồng bộ.
            # Trả lời ngay, xong tự lưu vào "Album đã lưu" (logout vẫn chạy tiếp).
            def _work():
                try:
                    from tools.ai_image_gen import recreate_all_from_tiktok
                    with _HEAVY_LOCK:
                        res = recreate_all_from_tiktok(url, handle="@dalatnow")
                    if not res.get("success"):
                        print(f"[Server] recreate-from-link fail: {res.get('error')}", file=sys.stderr)
                        return
                    base = Path(__file__).parent
                    out_dir = base / "output" / "albums" / f"app_aiimg_{uuid.uuid4().hex[:8]}"
                    out_dir.mkdir(parents=True, exist_ok=True)
                    images = []
                    for i, p in enumerate(res["paths"]):
                        dst = out_dir / f"aiimg_{i:02d}.png"
                        shutil.copy2(p, dst)
                        images.append({"name": dst.name, "url": _to_output_url(str(dst))})
                    dir_rel = str(out_dir.relative_to(base)).replace("\\", "/")
                    label = f"Tạo lại từ TikTok ({len(images)} ảnh)"
                    import time as _t
                    _append_album({"user": user, "album": "aiimg", "label": label, "dir": dir_rel,
                                   "images": images, "auto": False, "time": _t.time()})
                    print(f"[Server] recreate-from-link ✓ {len(images)}/{res.get('source_count')} ảnh cho {user}",
                          file=sys.stderr)
                except Exception as _e:
                    import traceback
                    print(f"[Server] recreate-from-link lỗi: {_e}\n{traceback.format_exc()}", file=sys.stderr)

            threading.Thread(target=_work, daemon=True).start()
            self._json_response({"success": True, "queued": True})
        except Exception as e:
            import traceback
            print(f"[Server] ai-image-from-link lỗi: {e}\n{traceback.format_exc()}", file=sys.stderr)
            self._json_response({"success": False, "error": _friendly_error(e)}, 500)

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
            since = float((q.get("since") or ["0"])[0] or 0)
            limit = int((q.get("limit") or ["0"])[0] or 0)
            items = sorted(_load_albums(), key=lambda a: a.get("time", 0), reverse=True)
            if role != "admin" and user:
                items = [a for a in items if a.get("user") == user]
            if since:
                items = [a for a in items if a.get("time", 0) >= since]
            total = len(items)
            if limit > 0:
                items = items[:limit]
            self._json_response({"success": True, "albums": items, "total": total})
        except Exception as e:
            self._json_response({"success": False, "error": str(e)}, 500)

    def handle_product_status(self):
        """POST /product-status {kind:'video'|'album', key, status} → đổi trạng thái duyệt/đăng."""
        try:
            b = self._read_json_body()
            kind = (b.get("kind") or "video").strip()
            key = (b.get("key") or "").strip()
            status = (b.get("status") or "").strip()
            ki = int(b.get("zernio_ki") or 0)
            account_id = (b.get("account_id") or "").strip()
            if status not in ("pending", "posted", "failed", "cancelled"):
                self._json_response({"success": False, "error": "status không hợp lệ"}, 400)
                return
            # Admin duyệt "đã đăng" → đăng TikTok thật qua Zernio key + account đã chọn.
            if kind == "video" and status == "posted":
                rec = next((p for p in _load_products() if p.get("video_url") == key), None)
                owner = (rec or {}).get("user", "")
                if _is_publish_user(owner):
                    res = _do_publish(key, _caption_for((rec or {}).get("topic", ""), owner),
                                      owner, ki=ki, account_id=account_id)
                    self._json_response({"success": True,
                                         "posted": bool(res.get("success")),
                                         "error": res.get("error", "")})
                    return
            if kind == "album" and status == "posted":
                rec = next((a for a in _load_albums() if a.get("dir") == key), None)
                owner = (rec or {}).get("user", "")
                if _is_publish_user(owner):
                    res = _do_publish_album(key, owner, ki=ki, account_id=account_id)
                    self._json_response({"success": True,
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
                res = scrape_news(kw or DEFAULT_KEYWORD, hts if isinstance(hts, list) else None,
                                  api_key=_user_apify("tintuc"))
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
            from tools.script_prompts import get_script_prompt, default_persona, DEFAULT_LINK_PROMPT
            rec = get_script_prompt(employee)
            self._json_response({"success": True, "employee": employee,
                                 "prompt": rec["prompt"], "examples": rec["examples"],
                                 "link_prompt": rec["link_prompt"],
                                 "default_prompt": default_persona(employee),
                                 "default_link_prompt": DEFAULT_LINK_PROMPT})
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
            set_script_prompt(employee, body.get("prompt", ""), body.get("examples", ""),
                              body.get("link_prompt", ""))
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

    def handle_user_keys_get(self):
        """GET /user-keys → nv staff: số key Zernio đã có; tin tức: Apify. Không trả giá trị key."""
        keys = _load_user_keys()
        users = _load_users()
        items = []
        for uid, u in users.items():
            if u.get("role") == "admin":
                continue
            k = keys.get(uid) or {}
            zk = k.get("zernio_keys")
            if not isinstance(zk, list):
                zk = [k["zernio_key"]] if (k.get("zernio_key") or "").strip() else []
            zk = [x for x in zk if (x or "").strip()]
            items.append({"user": uid, "name": u.get("name", uid),
                          "role": u.get("role", "staff"),
                          "zernio_count": len(zk),
                          "apify_set": bool((k.get("apify_key") or "").strip())})
        self._json_response({"success": True, "items": items})

    def handle_user_keys_save(self):
        """POST /user-keys {user, zernio_keys?: [..], apify_key?}. Ô ẩn (•) giữ key cũ theo index."""
        try:
            data = self._read_json_body()
            uid = (data.get("user") or "").strip()
            urec = _load_users().get(uid)
            if not urec:
                self._json_response({"success": False, "error": f"Tài khoản không tồn tại: {uid}"}, 400)
                return
            keys = _load_user_keys()
            rec = keys.get(uid) or {}
            # migrate key đơn cũ → list
            old = rec.get("zernio_keys")
            if not isinstance(old, list):
                old = [rec["zernio_key"]] if (rec.get("zernio_key") or "").strip() else []
                rec.pop("zernio_key", None)
            # zernio_keys: mảng ô từ UI; ô ẩn (chỉ • *) = giữ key cũ cùng index; rỗng = bỏ
            if isinstance(data.get("zernio_keys"), list):
                newk = []
                for i, v in enumerate(data["zernio_keys"]):
                    v = (v or "").strip()
                    if set(v) <= {"•", "*"} and v:      # ẩn → giữ cũ
                        if i < len(old) and old[i].strip():
                            newk.append(old[i].strip())
                    elif v:
                        newk.append(v)
                rec["zernio_keys"] = newk
            # apify: chỉ dùng cho kênh tin tức
            av = (data.get("apify_key") or "").strip()
            if av and not (set(av) <= {"•", "*"}):
                rec["apify_key"] = "" if av.lower() == "xoa" else av
            keys[uid] = rec
            _save_user_keys(keys)
            self._json_response({"success": True})
        except Exception as e:
            self._json_response({"success": False, "error": str(e)}, 500)

    def handle_zernio_accounts(self):
        """GET /zernio-accounts?user= → các tài khoản TikTok của nv (gộp qua các key Zernio).
        Trả [{ki, account_id, name}] để admin chọn account đăng."""
        try:
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            user = (q.get("user", [""])[0] or "").strip()
            from tools import publisher
            out = []
            for ki, key in enumerate(_user_zernio_keys(user)):
                for a in publisher.list_tiktok_accounts(key):
                    if a.get("id"):
                        out.append({"ki": ki, "account_id": a["id"], "name": a.get("name", "TikTok")})
            self._json_response({"success": True, "accounts": out})
        except Exception as e:
            self._json_response({"success": False, "error": str(e), "accounts": []}, 500)

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
                import hashlib
                cache = base_dir / "_cache"; cache.mkdir(parents=True, exist_ok=True)
                # key theo đường dẫn tương đối — nhiều album dùng chung tên file (aiimg_00.png)
                rel = fp.relative_to(base_dir).as_posix()
                cp = cache / f"{w}_{hashlib.md5(rel.encode('utf-8')).hexdigest()[:12]}.jpg"
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

    # DISABLE_BACKGROUND_JOBS=1: chạy nhiều server song song — chỉ 1 server giữ
    # automation (daily, news); các server khác vẫn render/web đủ.
    if os.getenv("DISABLE_BACKGROUND_JOBS", "").strip() in ("", "0", "false"):
        _start_news_scheduler()
        _start_daily_scheduler()
    else:
        print("[Server] Background jobs TẮT (DISABLE_BACKGROUND_JOBS).", file=sys.stderr)
    _start_render_worker()
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
                        res = scrape_news(api_key=_user_apify("tintuc"))
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


# ── Tự động mỗi ngày 7h: 5 kịch bản video + 5 album ảnh cho mỗi nv ────────────
DAILY_AUTO_ENABLED = False   # TẮT TẠM: không tự tạo album + kịch bản. Bật lại = True.
DAILY_SLOT_HOUR = 7
DAILY_N_ALBUMS = 5
DAILY_N_SCRIPTS = 5


def _daily_auto_job(only_users: list | None = None):
    """7h mỗi ngày: tạo trước 5 album ảnh + 5 kịch bản chờ cho mỗi nv (tin tức: kịch bản),
    lưu vào 'Ảnh'/'Video' để người dùng vào chỉ việc thả clip."""
    from tools.script_drafts import add_draft
    users = _load_users()
    made_albums, made_scripts = [], []

    for uid, u in users.items():
        if u.get("role") not in ("staff", "news"):
            continue
        if only_users and uid not in only_users:
            continue
        # 1) album ảnh (staff có handle album) — 5 bộ, xoay vòng các mẫu
        albs = _albums_for(uid)
        if albs:
            import random
            n_ok = 0
            for i in range(DAILY_N_ALBUMS):
                pick = albs[i % len(albs)] if len(albs) > 1 else albs[0]
                res = _generate_album(pick["id"], uid, auto=True)
                if res.get("success"):
                    n_ok += 1
                else:
                    print(f"[daily] album lỗi {uid}: {res.get('error')}", file=sys.stderr)
            if n_ok:
                made_albums.append(f"{u.get('name', uid)} ×{n_ok}")
        # 2) kịch bản chờ — 5 cái
        n_sc = 0
        for _ in range(DAILY_N_SCRIPTS):
            try:
                if u.get("role") == "staff":
                    from tools.listreview_content import build_prefill
                    pf = build_prefill(uid, regen=True)
                    if pf.get("scenes"):
                        add_draft(uid, pf["scenes"], pf.get("hook_style", "hook_red"),
                                  pf.get("badge_mode", "none"), pf.get("transition", "fade"),
                                  pf.get("overlay_engine", "pil"), pf.get("style", ""),
                                  pf.get("generated_by", "auto"))
                        n_sc += 1
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
                        n_sc += 1
            except Exception as e:
                print(f"[daily] kịch bản lỗi {uid}: {e}", file=sys.stderr)
        if n_sc:
            made_scripts.append(f"{u.get('name', uid)} ×{n_sc}")

    print("[daily] Tự động hôm nay: album=" + (", ".join(made_albums) if made_albums else "không có")
          + " | kịch bản chờ=" + (", ".join(made_scripts) if made_scripts else "không có"),
          file=sys.stderr)


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
                try:
                    from tools.storage_cleanup import run as _cleanup_run
                    _cleanup_run(days=5)
                except Exception as ce:
                    print(f"[daily] storage cleanup lỗi: {ce}", file=sys.stderr)
        except Exception as e:
            print(f"[daily] scheduler lỗi: {e}", file=sys.stderr)
        _t.sleep(60)


def _start_daily_scheduler():
    if not DAILY_AUTO_ENABLED:
        print("[Server] Daily auto TẮT (DAILY_AUTO_ENABLED=False) — không tự tạo album/kịch bản.", file=sys.stderr)
        return
    threading.Thread(target=_daily_scheduler, daemon=True).start()
    print(f"[Server] Daily auto scheduler bật ({DAILY_SLOT_HOUR}h).", file=sys.stderr)


if __name__ == "__main__":
    main()
