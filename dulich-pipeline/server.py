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
import time
import hmac
import hashlib
import shutil
import tempfile
import threading
import subprocess
from pathlib import Path
from http.cookies import SimpleCookie
from http.server import HTTPServer, ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, quote, unquote, urlencode, urlparse

# Configure UTF-8 encoding for Windows console to avoid print crashes
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Load only this app's .env. Never walk into a parent project and mutate an
# unrelated environment file when the pipeline .env has not been created yet.
_DOTENV_FILE = Path(
    os.getenv("PIPELINE_ENV_PATH") or (Path(__file__).parent / ".env")
).resolve()
_DOTENV_PATH = str(_DOTENV_FILE)
try:
    from dotenv import load_dotenv

    if _DOTENV_FILE.exists():
        load_dotenv(_DOTENV_FILE)
except Exception:
    pass

from tools.pipeline_store import (
    PipelineStoreError,
    QueueLimitError,
    UploadValidationError,
    get_pipeline_store,
)
from tools.process_control import popen_group_kwargs, terminate_process_tree

PIPELINE_STORE = get_pipeline_store()

# ── Cài đặt API key trong app (trang Settings) ──────────────────────────────
# Ghi đúng file .env đang được load; nếu chưa có thì dùng .env cạnh server.py.
ENV_PATH = _DOTENV_FILE

# Gemini image recreation is paused by default. Re-enable only through an
# explicit production configuration change after its API key is restored.
AI_IMAGE_FROM_LINK_ENABLED = (
    os.getenv("ENABLE_GEMINI_AI_IMAGE", "").strip().lower()
    in {"1", "true", "yes"}
)

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


def _generate_album(
    album: str,
    user: str = "",
    auto: bool = False,
    title_prompt: str = "",
    job_id: str = "",
) -> dict:
    """Chạy script CLI dựng 1 album ảnh (tránh lặp seed 10 lần gần nhất), lưu record. Dùng chung
    cho endpoint /assemble-image và bộ tự tạo ảnh hàng ngày."""
    cfg = IMAGE_ALBUMS.get(album)
    if not cfg:
        return {"success": False, "error": f"Album không hợp lệ: {album}"}
    if job_id:
        existing = _find_album(job_id)
        if existing:
            return {"success": True, **_album_view(existing), "deduplicated": True}
    base = Path(__file__).parent
    script_abs = base / cfg["script"]
    if not script_abs.exists():
        return {"success": False, "error": f"Thiếu script: {cfg['script']}"}

    suffix = job_id[:16] if job_id else uuid.uuid4().hex[:8]
    out_dir = base / "output" / "albums" / f"app_{album}_{suffix}"
    if job_id:
        shutil.rmtree(out_dir, ignore_errors=True)
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
        shutil.rmtree(out_dir, ignore_errors=True)
        return {"success": False, "error": "Quá thời gian (300s)."}

    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip()[-1200:]
        print(f"[Server] ❌ tạo ảnh {album} lỗi (rc={proc.returncode}):\n{tail}", file=sys.stderr)
        shutil.rmtree(out_dir, ignore_errors=True)
        return {"success": False, "error": tail or "Script lỗi"}

    files = sorted(out_dir.glob("*.png"))
    if not files:
        shutil.rmtree(out_dir, ignore_errors=True)
        return {"success": False, "error": "Script chạy xong nhưng không có ảnh PNG."}

    if seed is not None:
        _remember_seed(album, seed)

    images = [{"name": f.name, "url": _to_output_url(str(f))} for f in files]
    dir_rel = str(out_dir.relative_to(base)).replace("\\", "/")
    rec = {
        "id": job_id or uuid.uuid4().hex[:20],
        "job_id": job_id,
        "user": user,
        "album": album,
        "label": cfg.get("label", album),
        "dir": dir_rel,
        "images": images,
        "auto": auto,
    }
    try:
        import time as _t
        saved = _append_album({**rec, "time": _t.time()})
    except Exception as _e:
        print(f"[Server] album log lỗi: {_e}", file=sys.stderr)
        shutil.rmtree(out_dir, ignore_errors=True)
        return {"success": False, "error": "Không thể lưu album."}
    return {"success": True, **_album_view(saved)}


def _generate_ai_album_from_link(user: str, url: str, job_id: str = "") -> dict:
    """Create and persist a recreated TikTok carousel for one durable job."""
    if not AI_IMAGE_FROM_LINK_ENABLED:
        return {
            "success": False,
            "error": "Tính năng tạo lại ảnh bằng Gemini đang tạm dừng.",
        }
    if job_id:
        existing = _find_album(job_id)
        if existing:
            return {"success": True, **_album_view(existing), "deduplicated": True}

    from tools.ai_image_gen import recreate_all_from_tiktok

    with _HEAVY_LOCK:
        result = recreate_all_from_tiktok(url, handle="@dalatnow")
    if not result.get("success"):
        return {"success": False, "error": result.get("error", "AI không tạo được ảnh.")}
    base = Path(__file__).parent
    suffix = job_id[:16] if job_id else uuid.uuid4().hex[:8]
    out_dir = base / "output" / "albums" / f"app_aiimg_{suffix}"
    if job_id:
        shutil.rmtree(out_dir, ignore_errors=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    images = []
    try:
        for index, source in enumerate(result.get("paths") or []):
            source_path = Path(source)
            if not source_path.is_file():
                continue
            destination = out_dir / f"aiimg_{index:02d}.png"
            shutil.copy2(source_path, destination)
            images.append({"name": destination.name, "url": _to_output_url(str(destination))})
        if not images:
            raise RuntimeError("AI chạy xong nhưng không tạo được file ảnh.")
        saved = _append_album(
            {
                "id": job_id or uuid.uuid4().hex[:20],
                "job_id": job_id,
                "user": user,
                "album": "aiimg",
                "label": f"Tạo lại từ TikTok ({len(images)} ảnh)",
                "dir": str(out_dir.relative_to(base)).replace("\\", "/"),
                "images": images,
                "auto": False,
                "time": time.time(),
            }
        )
        return {
            "success": True,
            **_album_view(saved),
            "source_count": result.get("source_count"),
        }
    except Exception as exc:
        shutil.rmtree(out_dir, ignore_errors=True)
        return {"success": False, "error": str(exc)}


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
UPLOAD_TEMP_DIR = PIPELINE_STORE.upload_root
UPLOAD_TEMP_DIR.mkdir(parents=True, exist_ok=True)

WEB_INDEX = Path(__file__).parent / "web" / "index.html"

# Bound CPU/RAM-heavy work across worker threads and legacy synchronous tools.
# Default is one-at-a-time; raising HEAVY_JOB_WORKERS intentionally raises this
# semaphore too, so a larger VPS can opt into measured parallel rendering.
try:
    _HEAVY_SLOTS = max(1, int(os.getenv("HEAVY_JOB_WORKERS", "1") or 1))
except (TypeError, ValueError):
    _HEAVY_SLOTS = 1
_HEAVY_LOCK = threading.BoundedSemaphore(_HEAVY_SLOTS)

def _env_int(name: str, default: int, minimum: int = 1) -> int:
    try:
        return max(minimum, int(os.getenv(name, str(default)) or default))
    except (TypeError, ValueError):
        return max(minimum, default)


MAX_ACTIVE_JOBS_PER_USER = _env_int("MAX_ACTIVE_JOBS_PER_USER", 4)
MAX_GLOBAL_ACTIVE_JOBS = _env_int("MAX_GLOBAL_ACTIVE_JOBS", 20)
MAX_UPLOAD_FILE_BYTES = _env_int("MAX_UPLOAD_FILE_MB", 500) * 1024 * 1024
MAX_UPLOAD_JOB_BYTES = _env_int("MAX_UPLOAD_JOB_MB", 1536) * 1024 * 1024
MAX_UPLOAD_SESSIONS_PER_USER = _env_int("MAX_UPLOAD_SESSIONS_PER_USER", 4)
MAX_UPLOAD_CHUNK_BYTES = _env_int("MAX_UPLOAD_CHUNK_MB", 16) * 1024 * 1024
UPLOAD_DISK_RESERVE_BYTES = _env_int("UPLOAD_DISK_RESERVE_MB", 15360) * 1024 * 1024
MAX_LEGACY_MULTIPART_BYTES = _env_int("MAX_LEGACY_MULTIPART_MB", 64) * 1024 * 1024


def _validate_uploaded_media(upload: dict) -> None:
    """Reject renamed/corrupt files before they can consume a render worker."""
    if os.getenv("SKIP_UPLOAD_FFPROBE", "").strip() == "1":
        return
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise UploadValidationError(
            "Server thiếu ffprobe nên chưa thể xác thực video upload."
        )
    upload_root = PIPELINE_STORE.upload_root.resolve()
    for item in upload.get("files") or []:
        relative = str(item.get("relative_path") or "")
        path = (upload_root / relative).resolve()
        try:
            path.relative_to(upload_root)
        except ValueError as exc:
            raise UploadValidationError("Đường dẫn video upload không hợp lệ.") from exc
        try:
            probe = subprocess.run(
                [
                    ffprobe,
                    "-v",
                    "error",
                    "-select_streams",
                    "v:0",
                    "-show_entries",
                    "stream=codec_type",
                    "-of",
                    "json",
                    str(path),
                ],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise UploadValidationError(
                f"ffprobe quá thời gian khi kiểm tra video {item.get('original_name') or path.name}."
            ) from exc
        try:
            details = json.loads(probe.stdout or "{}")
        except json.JSONDecodeError:
            details = {}
        if probe.returncode != 0 or not details.get("streams"):
            raise UploadValidationError(
                f"File {item.get('original_name') or path.name} không phải video hợp lệ."
            )


HEAVY_JOB_KINDS = {
    "personal_video",
    "listreview_video",
    "album_image",
    "ai_image_from_link",
}
NETWORK_JOB_KINDS = {
    "publish_video",
    "publish_album",
    "publish_dashboard",
}
_ZERNIO_ACCOUNTS_CACHE: dict[str, tuple[float, list[dict]]] = {}
_ZERNIO_ACCOUNTS_CACHE_LOCK = threading.Lock()


def _is_transient_render_err(e) -> bool:
    """Lỗi tạm thời (đáng thử lại): timeout do server bận, không phải source hỏng."""
    low = str(e or "").lower()
    return any(
        marker in low
        for marker in (
            "quá thời gian",
            "timeout",
            "temporarily unavailable",
            "connection reset",
            "rate limit",
            "429",
        )
    )


def _is_uncertain_publish_err(e) -> bool:
    low = str(e or "").lower()
    return any(
        marker in low
        for marker in (
            "timeout",
            "timed out",
            "connection reset",
            "remote end closed",
            "mất kết nối",
        )
    )


class JobExecutionError(RuntimeError):
    def __init__(self, message: str, *, retryable: bool = False, uncertain: bool = False):
        super().__init__(message)
        self.retryable = retryable
        self.uncertain = uncertain


def _render_product_from_result(job: dict, result: dict, payload: dict) -> dict:
    if not result or not result.get("success"):
        message = (result or {}).get("error") or "Render không thành công."
        raise JobExecutionError(
            _friendly_error(message),
            retryable=_is_transient_render_err(message),
        )
    current = PIPELINE_STORE.get_job(job["id"])
    if current and current.get("cancel_requested"):
        raise JobExecutionError("Job đã được hủy.")
    video_url = _to_output_url(result.get("video_path", ""))
    thumb_url = _to_output_url(result.get("thumb_path", ""))
    preview_url = _to_output_url(result.get("preview_path", ""))
    saved = _append_product(
        {
            "job_id": job["id"],
            "user": job["owner"],
            "topic": payload.get("topic") or "Video",
            "hook_style": payload.get("hook_style", ""),
            "video_url": video_url,
            "thumb_url": thumb_url,
            "preview_url": preview_url,
            "time": time.time(),
        }
    )
    public = _product_view(saved)
    if payload.get("draft_id"):
        try:
            from tools.script_drafts import mark_used

            mark_used(payload["draft_id"])
        except Exception as exc:
            print(f"[jobs] mark draft lỗi: {exc}", file=sys.stderr)
    return {
        "product_id": saved["id"],
        "video_url": public["video_url"],
        "thumb_url": public.get("thumb_url", ""),
        "preview_url": public.get("preview_url", ""),
    }


def _uploaded_paths_by_scene(payload: dict) -> dict[str, list[str]]:
    grouped: dict[str, list[tuple[int, str]]] = {}
    for item in payload.get("upload_files") or []:
        field = str(item.get("field") or "")
        if "__" in field:
            scene_id, suffix = field.rsplit("__", 1)
            order = int(suffix) if suffix.isdigit() else 0
        else:
            scene_id, order = field, 0
        grouped.setdefault(scene_id, []).append((order, str(item.get("path") or "")))
    return {
        scene_id: [path for _, path in sorted(items) if path]
        for scene_id, items in grouped.items()
    }


def _hydrate_listreview_spec(payload: dict) -> dict:
    spec = json.loads(json.dumps(payload.get("spec") or {}))
    grouped = _uploaded_paths_by_scene(payload)
    intro = spec.get("intro") or {}
    intro["clips"] = grouped.get(str(intro.get("scene_id") or "intro"), grouped.get("intro", []))
    spec["intro"] = intro
    for index, spot in enumerate(spec.get("spots") or [], start=1):
        scene_id = str(spot.get("scene_id") or f"spot{index}")
        spot["clips"] = grouped.get(scene_id, [])
    outro = spec.get("outro") or {}
    outro["clips"] = grouped.get(str(outro.get("scene_id") or "outro"), grouped.get("outro", []))
    spec["outro"] = outro
    return spec


def _personal_scene_uploads(payload: dict, job_id: str) -> list[dict]:
    if payload.get("scene_uploads"):
        return payload["scene_uploads"]
    grouped = _uploaded_paths_by_scene(payload)
    session_dir = None
    files = payload.get("upload_files") or []
    if files:
        session_dir = Path(files[0]["path"]).resolve().parent
    uploads: list[dict] = []
    for scene in payload.get("scenes_meta") or []:
        scene_id = str(scene.get("scene_id") or "")
        paths = grouped.get(scene_id, [])
        if len(paths) <= 1:
            file_path = paths[0] if paths else ""
        else:
            concat_dest = str((session_dir or UPLOAD_TEMP_DIR) / f"{scene_id}_concat.mp4")
            file_path = concat_dest if _concat_scene_clips(paths, concat_dest) else paths[0]
        uploads.append({"scene_id": scene_id, "file_path": file_path})
    return uploads


def _execute_durable_job(job: dict) -> dict:
    """Run one leased job.  Called by embedded and systemd workers."""
    payload = job.get("payload") or {}
    kind = job.get("kind")
    if kind in {"personal_video", "listreview_video"}:
        existing = _find_product(job["id"])
        if existing:
            public = _product_view(existing)
            return {
                "product_id": existing["id"],
                "video_url": public["video_url"],
                "thumb_url": public.get("thumb_url", ""),
                "preview_url": public.get("preview_url", ""),
                "deduplicated": True,
            }
    if kind == "listreview_video":
        from tools.list_review_render import render_list_review

        spec = _hydrate_listreview_spec(payload) if payload.get("upload_files") else payload["spec"]
        spec["job_id"] = job["id"]
        with _HEAVY_LOCK:
            result = render_list_review(spec)
        return _render_product_from_result(job, result, payload)

    if kind == "personal_video":
        from agents.personal_video_agent import run_assemble_video

        with _HEAVY_LOCK:
            result = run_assemble_video(
                job_id=job["id"],
                scene_uploads=_personal_scene_uploads(payload, job["id"]),
                transition=payload.get("transition", "fade"),
                hook_style=payload.get("hook_style", "zoom_in"),
                hook_text=payload.get("hook_text", ""),
                hook_title=payload.get("hook_title", ""),
                hook_subtitle=payload.get("hook_subtitle", ""),
                video_type=payload.get("video_type", "personal"),
                voice_provider=payload.get("voice_mode", "gtts"),
                voice_id=payload.get("voice_id", ""),
            )
        if result and "success" not in result:
            result["success"] = bool(result.get("video_path"))
        return _render_product_from_result(job, result, payload)

    if kind == "album_image":
        result = _generate_album(
            payload["album"],
            job["owner"],
            auto=bool(payload.get("auto")),
            title_prompt=payload.get("title_prompt", ""),
            job_id=job["id"],
        )
        if not result.get("success"):
            raise JobExecutionError(
                result.get("error", "Không thể tạo album."),
                retryable=_is_transient_render_err(result.get("error")),
            )
        return result

    if kind == "ai_image_from_link":
        result = _generate_ai_album_from_link(
            job["owner"], payload["url"], job_id=job["id"]
        )
        if not result.get("success"):
            raise JobExecutionError(
                result.get("error", "Không thể tạo lại album AI."),
                retryable=_is_transient_render_err(result.get("error")),
            )
        return result

    if kind in {"publish_video", "publish_album"}:
        resource_id = payload["resource_id"]
        if kind == "publish_video":
            rec = _find_product(resource_id) or {}
            result = _do_publish(
                resource_id,
                _caption_for(rec.get("topic", ""), job["owner"]),
                job["owner"],
                ki=int(payload.get("zernio_ki") or 0),
                account_id=payload.get("account_id", ""),
                request_id=payload.get("provider_request_id", ""),
            )
        else:
            result = _do_publish_album(
                resource_id,
                job["owner"],
                ki=int(payload.get("zernio_ki") or 0),
                account_id=payload.get("account_id", ""),
                request_id=payload.get("provider_request_id", ""),
            )
        if not result.get("success"):
            safe_idempotent_retry = bool(payload.get("provider_request_id")) and (
                result.get("status") == "unknown"
                and int(job.get("attempts") or 0) < int(job.get("max_attempts") or 1)
            )
            raise JobExecutionError(
                result.get("error", "Đăng bài thất bại."),
                retryable=safe_idempotent_retry,
                uncertain=(
                    result.get("status") == "unknown"
                    and not safe_idempotent_retry
                ),
            )
        return result

    if kind == "publish_dashboard":
        result = _publish_dashboard_resource(payload["resource_id"], payload)
        if not result.get("success"):
            raise JobExecutionError(result.get("error", "Đăng Dashboard thất bại."))
        return result

    raise JobExecutionError(f"Loại job không được hỗ trợ: {kind}")


def _job_timeout_seconds(kind: str) -> int:
    if kind in NETWORK_JOB_KINDS:
        return _env_int("NETWORK_JOB_TIMEOUT_SECONDS", 180, 30)
    return _env_int("HEAVY_JOB_TIMEOUT_SECONDS", 1800, 60)


def _run_durable_job_isolated(job: dict) -> dict:
    """Run one job in a killable process group and monitor cancel/timeout."""
    result_dir = PIPELINE_STORE.db_path.parent / "job-results"
    result_dir.mkdir(parents=True, exist_ok=True)
    result_file = result_dir / (
        f"{job['id']}-{int(job.get('attempts') or 0)}-{uuid.uuid4().hex[:8]}.json"
    )
    env = os.environ.copy()
    env["PIPELINE_DB_PATH"] = str(PIPELINE_STORE.db_path)
    env["UPLOAD_TEMP_DIR"] = str(PIPELINE_STORE.upload_root)
    env["DISABLE_BACKGROUND_JOBS"] = "1"
    env["DISABLE_JOB_WORKER"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    command = [
        sys.executable,
        "-X",
        "utf8",
        str(Path(__file__).parent / "job_runner.py"),
        "--job-id",
        job["id"],
        "--result-file",
        str(result_file),
    ]
    process = subprocess.Popen(
        command,
        cwd=str(Path(__file__).parent),
        env=env,
        **popen_group_kwargs(),
    )
    timeout = _job_timeout_seconds(str(job.get("kind") or ""))
    deadline = time.monotonic() + timeout
    try:
        while process.poll() is None:
            current = PIPELINE_STORE.get_job(job["id"]) or {}
            if current.get("cancel_requested"):
                terminate_process_tree(process)
                raise JobExecutionError("Job đã được hủy.")
            if time.monotonic() >= deadline:
                terminate_process_tree(process)
                is_publish = str(job.get("kind") or "").startswith("publish_")
                safe_retry = (
                    is_publish
                    and bool((job.get("payload") or {}).get("provider_request_id"))
                    and int(job.get("attempts") or 0)
                    < int(job.get("max_attempts") or 1)
                )
                raise JobExecutionError(
                    f"Job vượt quá giới hạn {timeout} giây và đã bị dừng.",
                    retryable=(not is_publish) or safe_retry,
                    uncertain=is_publish and not safe_retry,
                )
            time.sleep(0.25)

        if not result_file.is_file():
            is_publish = str(job.get("kind") or "").startswith("publish_")
            safe_retry = (
                is_publish
                and bool((job.get("payload") or {}).get("provider_request_id"))
                and int(job.get("attempts") or 0)
                < int(job.get("max_attempts") or 1)
            )
            raise JobExecutionError(
                f"Tiến trình job dừng bất thường (exit={process.returncode}).",
                retryable=(not is_publish) or safe_retry,
                uncertain=is_publish and not safe_retry,
            )
        try:
            envelope = json.loads(result_file.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise JobExecutionError(
                "Không đọc được kết quả từ tiến trình job.",
                retryable=True,
            ) from exc
        if envelope.get("ok"):
            return envelope.get("result") or {}
        raise JobExecutionError(
            envelope.get("error") or "Tiến trình job thất bại.",
            retryable=bool(envelope.get("retryable")),
            uncertain=bool(envelope.get("uncertain")),
        )
    finally:
        if process.poll() is None:
            terminate_process_tree(process)
        result_file.unlink(missing_ok=True)


def _durable_worker_loop(kinds: set[str], label: str) -> None:
    worker_id = f"{label}-{os.getpid()}-{uuid.uuid4().hex[:8]}"
    recovery = PIPELINE_STORE.recover_stale_jobs(_env_int("JOB_LEASE_SECONDS", 120, 30))
    if recovery["recovered"] or recovery["failed"]:
        print(f"[jobs] recovery {recovery}", file=sys.stderr)
    while True:
        try:
            job = PIPELINE_STORE.claim_next(worker_id, kinds=kinds)
        except Exception as exc:
            print(f"[jobs] claim lỗi: {exc}", file=sys.stderr)
            time.sleep(2)
            continue
        if not job:
            time.sleep(1)
            continue
        stop_heartbeat = threading.Event()

        def heartbeat() -> None:
            while not stop_heartbeat.wait(10):
                try:
                    PIPELINE_STORE.heartbeat(job["id"], worker_id)
                except Exception as exc:
                    print(f"[jobs] heartbeat lỗi {job['id']}: {exc}", file=sys.stderr)

        pulse = threading.Thread(target=heartbeat, daemon=True)
        pulse.start()
        terminal_status = ""
        try:
            print(
                f"[jobs] bắt đầu {job['id']} kind={job['kind']} owner={job['owner']}",
                file=sys.stderr,
            )
            result = _run_durable_job_isolated(job)
            if (
                job["kind"] == "publish_video"
                and result.get("status") == "posted"
            ):
                record = _find_product((job.get("payload") or {}).get("resource_id", ""))
                if record:
                    _archive_video(record.get("video_url", ""))
            PIPELINE_STORE.complete_job(job["id"], worker_id, result)
            completed = PIPELINE_STORE.get_job(job["id"]) or {}
            terminal_status = str(completed.get("status") or "")
            print(f"[jobs] ✓ {job['id']}", file=sys.stderr)
        except JobExecutionError as exc:
            status = PIPELINE_STORE.fail_job(
                job["id"],
                worker_id,
                _friendly_error(exc),
                retryable=exc.retryable,
                uncertain=exc.uncertain,
            )
            terminal_status = status
            print(f"[jobs] ✗ {job['id']} → {status}: {exc}", file=sys.stderr)
        except Exception as exc:
            import traceback

            status = PIPELINE_STORE.fail_job(
                job["id"],
                worker_id,
                _friendly_error(exc),
                retryable=_is_transient_render_err(exc),
            )
            terminal_status = status
            print(
                f"[jobs] ✗ {job['id']} → {status}: {exc}\n{traceback.format_exc()}",
                file=sys.stderr,
            )
        finally:
            stop_heartbeat.set()
            pulse.join(timeout=1)
            if (
                terminal_status in {"done", "cancelled"}
                and job["kind"] in {"personal_video", "listreview_video"}
            ):
                try:
                    PIPELINE_STORE.cleanup_job_upload(job["id"])
                except Exception as exc:
                    print(f"[jobs] cleanup upload lỗi: {exc}", file=sys.stderr)
                legacy_temp = str((job.get("payload") or {}).get("legacy_temp_dir") or "")
                if legacy_temp:
                    try:
                        target = Path(legacy_temp).resolve()
                        if target.parent == UPLOAD_TEMP_DIR:
                            shutil.rmtree(target, ignore_errors=True)
                    except OSError:
                        pass


def run_durable_workers(queue_name: str = "all") -> list[threading.Thread]:
    """Start worker loops and return their threads (used by server.py and worker.py)."""
    threads: list[threading.Thread] = []
    specs: list[tuple[set[str], str, int]] = []
    if queue_name in {"all", "heavy"}:
        specs.append(
            (
                HEAVY_JOB_KINDS,
                "heavy",
                _env_int("HEAVY_JOB_WORKERS", 1),
            )
        )
    if queue_name in {"all", "network"}:
        specs.append(
            (
                NETWORK_JOB_KINDS,
                "network",
                _env_int("NETWORK_JOB_WORKERS", 2),
            )
        )
    for kinds, label, count in specs:
        for index in range(count):
            thread = threading.Thread(
                target=_durable_worker_loop,
                args=(kinds, f"{label}{index + 1}"),
                daemon=True,
            )
            thread.start()
            threads.append(thread)
    heartbeat = threading.Thread(
        target=_worker_process_heartbeat,
        args=(queue_name, sum(item[2] for item in specs)),
        daemon=True,
        name=f"worker-heartbeat-{queue_name}",
    )
    heartbeat.start()
    threads.append(heartbeat)
    return threads


def _worker_process_heartbeat(queue_name: str, worker_count: int) -> None:
    while True:
        try:
            PIPELINE_STORE.set_meta(
                "worker_heartbeat",
                json.dumps(
                    {
                        "timestamp": time.time(),
                        "pid": os.getpid(),
                        "queue": queue_name,
                        "workers": worker_count,
                    },
                    separators=(",", ":"),
                ),
            )
        except Exception as exc:
            print(f"[worker] heartbeat process lỗi: {exc}", file=sys.stderr)
        time.sleep(10)


def _start_render_worker() -> None:
    threads = run_durable_workers("all")
    print(f"[Server] Durable jobs bật ({len(threads)} worker).", file=sys.stderr)


def _job_client_view(job: dict) -> dict:
    """Return job state without exposing server paths or provider payloads."""
    payload = job.get("payload") or {}
    result = job.get("result") or {}
    status = job.get("status", "")
    legacy_status = "rendering" if status == "running" else status
    return {
        "job_id": job.get("id", ""),
        "kind": job.get("kind", ""),
        "user": job.get("owner", ""),
        "topic": payload.get("topic")
        or payload.get("album")
        or ("Đăng bài" if str(job.get("kind", "")).startswith("publish_") else "Job"),
        "status": legacy_status,
        "durable_status": status,
        "progress": int(job.get("progress") or 0),
        "error": job.get("error", ""),
        "time": float(job.get("created_at") or 0),
        "attempts": int(job.get("attempts") or 0),
        "cancel_requested": bool(job.get("cancel_requested")),
        "product_id": result.get("product_id", ""),
        "video_url": result.get("video_url", ""),
        "thumb_url": result.get("thumb_url", ""),
        "preview_url": result.get("preview_url", ""),
        "album_id": result.get("id", "") if job.get("kind") in {"album_image", "ai_image_from_link"} else "",
        "result_status": result.get("status", ""),
    }

def _to_output_url(abs_path: str) -> str:
    """Convert an absolute output file path into a URL servable by GET /output/..."""
    if not abs_path:
        return ""
    try:
        rel = os.path.relpath(abs_path, str(Path(__file__).parent))
        return "/" + rel.replace("\\", "/")
    except Exception:
        return ""


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = (BASE_DIR / "output").resolve()


def _resolve_under(base_dir: Path, requested: str, *, must_exist: bool = True) -> Path:
    """Resolve a client/data path without allowing absolute, traversal or symlink escape."""
    base = base_dir.resolve()
    raw = unquote(str(requested or "")).replace("\\", "/")
    candidate_path = Path(raw)
    if not raw or candidate_path.is_absolute() or "\x00" in raw:
        raise ValueError("invalid path")
    candidate = (base / candidate_path).resolve(strict=must_exist)
    try:
        candidate.relative_to(base)
    except ValueError as exc:
        raise ValueError("path escapes allowed directory") from exc
    return candidate


def _output_file_from_url(url: str) -> Path:
    parsed = urlparse(str(url or ""))
    if parsed.scheme or parsed.netloc or not parsed.path.startswith("/output/"):
        raise ValueError("not a local output URL")
    return _resolve_under(OUTPUT_DIR, parsed.path[len("/output/"):])


def _image_variant(file_path: Path, width: int) -> Path:
    if (
        width <= 0
        or width > 1600
        or file_path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}
    ):
        return file_path
    try:
        relative = file_path.relative_to(OUTPUT_DIR).as_posix()
        cache = OUTPUT_DIR / "_cache"
        cache.mkdir(parents=True, exist_ok=True)
        key = hashlib.sha256(f"{relative}:{width}".encode("utf-8")).hexdigest()[:20]
        cached = cache / f"{width}_{key}.jpg"
        if not cached.exists() or cached.stat().st_mtime < file_path.stat().st_mtime:
            from PIL import Image
            image = Image.open(file_path)
            if image.mode not in {"RGB", "L"}:
                image = image.convert("RGB")
            old_width, old_height = image.size
            if old_width > width:
                image = image.resize(
                    (width, max(1, round(old_height * width / old_width))),
                    Image.LANCZOS,
                )
            image.save(cached, "JPEG", quality=82)
        return cached if cached.exists() else file_path
    except Exception as exc:
        print(f"[media] resize failed for {file_path.name}: {exc}", file=sys.stderr)
        return file_path


def _stable_resource_id(kind: str, record: dict) -> str:
    existing = str(record.get("id") or "").strip()
    if existing:
        return existing
    source = (
        record.get("video_url")
        or record.get("dir")
        or record.get("job_id")
        or f"{record.get('user','')}:{record.get('time','')}"
    )
    return uuid.uuid5(uuid.NAMESPACE_URL, f"dulich:{kind}:{source}").hex[:20]


def _safe_identifier(value: str, prefix: str) -> str:
    clean = "".join(ch for ch in str(value or "") if ch.isalnum() or ch in {"_", "-"})
    return clean[:64] or f"{prefix}_{uuid.uuid4().hex[:12]}"


def _media_url(kind: str, resource_id: str, asset: str = "") -> str:
    suffix = f"/{quote(str(asset), safe='')}" if asset != "" else ""
    return f"/media/{kind}/{quote(str(resource_id), safe='')}{suffix}"


def _signed_media_url(kind: str, resource_id: str, asset: str = "", ttl: int = 7200) -> str:
    secret = (os.getenv("MEDIA_SIGNING_SECRET") or "").strip()
    if len(secret) < 32:
        raise RuntimeError("MEDIA_SIGNING_SECRET must contain at least 32 characters")
    suffix = f"/{quote(str(asset), safe='')}" if asset != "" else ""
    path = f"/media/public/{kind}/{quote(str(resource_id), safe='')}{suffix}"
    exp = int(time.time()) + max(60, min(int(ttl), 7200))
    message = f"GET\n{path}\n{exp}".encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()
    return f"{path}?{urlencode({'exp': exp, 'sig': signature})}"


def _verify_signed_media(path: str, query: dict[str, list[str]]) -> bool:
    secret = (os.getenv("MEDIA_SIGNING_SECRET") or "").strip()
    try:
        exp = int((query.get("exp") or ["0"])[0])
        signature = (query.get("sig") or [""])[0]
    except (TypeError, ValueError):
        return False
    now = int(time.time())
    if len(secret) < 32 or exp < now or exp > now + 7260:
        return False
    expected = hmac.new(
        secret.encode("utf-8"),
        f"GET\n{path}\n{exp}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(signature, expected)


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
AUTH_DB_FILE = Path(os.getenv("AUTH_DB_PATH") or (Path(__file__).parent / "data" / "auth.sqlite3"))
from tools.auth_store import AuthStore
AUTH_STORE = AuthStore(AUTH_DB_FILE)
AUTH_STORE.cleanup()
AUDIT_FILE = Path(__file__).parent / "data" / "security_audit.jsonl"
BACKUP_STATUS_FILE = Path(
    os.getenv("BACKUP_STATUS_PATH")
    or (Path(__file__).parent / "data" / "backups" / "status.json")
)
_AUDIT_LOCK = threading.Lock()
_TEMP_MEDIA: dict[str, dict] = {}
_TEMP_MEDIA_LOCK = threading.Lock()

# Stable account identity used by auth responses, render authorization and every
# admin filter.  Do not derive this order from recent content: an employee with
# zero videos (for example nv4/Vy) must remain visible.
CANONICAL_ROSTER = (
    ("nv1", "Lê", "staff", "hook_red"),
    ("nv2", "Uyên", "staff", "hook_green"),
    ("nv3", "Hiền", "staff", "hook_brown"),
    ("nv4", "Vy", "staff", "hook_serif"),
    ("nv5", "Muối", "staff", "hook_meo"),
    ("tintuc", "Tin tức", "news", "hook_news"),
)
CANONICAL_ACCOUNT_PROFILES = {
    username: {"username": username, "name": name, "role": role, "hook_style": hook}
    for username, name, role, hook in CANONICAL_ROSTER
}
NEWS_HOOK_STYLES = {"hook_news_green", "hook_news_purple", "hook_news_pink"}


def _canonical_profile(profile: dict | None) -> dict:
    """Overlay stable public identity fields without exposing auth internals."""
    result = dict(profile or {})
    username = str(result.get("username") or "")
    canonical = CANONICAL_ACCOUNT_PROFILES.get(username)
    if canonical:
        result.update(canonical)
    return result


def _public_roster() -> list[dict]:
    users = _load_users()
    roster = []
    for username, name, role, hook_style in CANONICAL_ROSTER:
        if username not in users:
            continue
        roster.append(
            {
                "username": username,
                "name": name,
                "role": role,
                "hook_style": hook_style,
            }
        )
    return roster


def _authoritative_render_payload(owner: str, role: str, kind: str, payload: dict) -> dict:
    """Bind every render to the authenticated account's canonical hook."""
    result = dict(payload or {})
    result.pop("user", None)
    result.pop("owner", None)
    result["owner"] = owner
    if role == "staff":
        result["hook_style"] = CANONICAL_ACCOUNT_PROFILES.get(owner, {}).get(
            "hook_style", "hook_red"
        )
    elif role == "news":
        requested = str(result.get("hook_style") or "")
        result["hook_style"] = (
            requested if requested in NEWS_HOOK_STYLES else "hook_news_pink"
        )
    return result


def _audit(actor: str, action: str, target: str = "", **details) -> None:
    event = {
        "time": int(time.time()),
        "actor": actor,
        "action": action,
        "target": target,
        "details": details,
    }
    try:
        with _AUDIT_LOCK:
            AUDIT_FILE.parent.mkdir(parents=True, exist_ok=True)
            with AUDIT_FILE.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event, ensure_ascii=False) + "\n")
            try:
                os.chmod(AUDIT_FILE, 0o600)
            except OSError:
                pass
    except Exception as exc:
        print(f"[security-audit] write failed: {exc}", file=sys.stderr)


def _register_temp_media(owner: str, file_path: str) -> str:
    path = Path(file_path).resolve(strict=True)
    path.relative_to(OUTPUT_DIR)
    token = uuid.uuid4().hex
    now = int(time.time())
    with _TEMP_MEDIA_LOCK:
        for key, item in list(_TEMP_MEDIA.items()):
            if int(item.get("expires_at", 0)) <= now:
                _TEMP_MEDIA.pop(key, None)
        _TEMP_MEDIA[token] = {
            "owner": owner,
            "path": str(path),
            "expires_at": now + 10 * 60,
        }
    return _media_url("temp", token)

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
    """Load public user profiles from SQLite; never load a plaintext password."""
    users = AUTH_STORE.users_dict()
    if users:
        return users
    # Metadata-only fallback helps render the migration/login screen, but cannot log in.
    try:
        legacy = json.loads(USERS_FILE.read_text(encoding="utf-8"))
        return {
            username: {
                key: value
                for key, value in (record or {}).items()
                if key not in {"password", "password_hash"}
            }
            for username, record in legacy.items()
        }
    except Exception:
        return {}


def _load_products() -> list:
    if not PIPELINE_STORE.resource_migration_done("video"):
        with _PROD_LOCK:
            if not PIPELINE_STORE.resource_migration_done("video"):
                try:
                    legacy = json.loads(PRODUCTS_FILE.read_text(encoding="utf-8"))
                    if not isinstance(legacy, list):
                        legacy = []
                except Exception:
                    legacy = []
                for item in legacy:
                    item["id"] = _stable_resource_id("video", item)
                PIPELINE_STORE.import_resources("video", legacy)
                PIPELINE_STORE.mark_resource_migration_done("video")
    return PIPELINE_STORE.list_resources("video")


def _append_product(rec: dict) -> dict:
    rec = dict(rec)
    rec.setdefault("id", rec.get("job_id") or uuid.uuid4().hex[:20])
    rec.setdefault("status", "pending")   # pending(chưa duyệt) | posted(đã đăng) | failed(đăng lỗi) | cancelled(hủy)
    _load_products()  # one-time legacy import before the first insert
    return PIPELINE_STORE.insert_resource_once("video", rec)[0]


def _set_product_status(key: str, status: str) -> bool:
    """Change a video status by opaque id (legacy URL accepted internally)."""
    record = _find_product(key)
    if not record:
        record = next((p for p in _load_products() if p.get("video_url") == key), None)
    if not record:
        return False
    return bool(PIPELINE_STORE.update_resource("video", record["id"], status=status))


def _find_product(resource_id: str) -> dict | None:
    _load_products()
    return PIPELINE_STORE.get_resource("video", resource_id)


def _product_view(record: dict) -> dict:
    item = dict(record)
    resource_id = _stable_resource_id("video", item)
    item["id"] = resource_id
    item["video_url"] = _media_url("video", resource_id)
    if item.get("thumb_url"):
        item["thumb_url"] = _media_url("video", resource_id, "thumb")
    if item.get("preview_url"):
        item["preview_url"] = _media_url("video", resource_id, "preview")
    item.pop("video_path", None)
    return item


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


def _health_snapshot() -> tuple[dict, int]:
    now = time.time()
    checks: dict[str, object] = {}
    errors: list[str] = []
    warnings: list[str] = []
    try:
        checks["pipeline"] = PIPELINE_STORE.health_snapshot()
        if not checks["pipeline"]["database_ok"]:
            errors.append("pipeline_database")
    except Exception as exc:
        checks["pipeline"] = {"database_ok": False}
        errors.append("pipeline_database")
        print(f"[health] pipeline database lỗi: {exc}", file=sys.stderr)

    try:
        auth_users = AUTH_STORE.user_count()
        checks["auth"] = {"database_ok": True, "users": auth_users}
        if auth_users < 6:
            errors.append("auth_accounts")
    except Exception as exc:
        checks["auth"] = {"database_ok": False, "users": 0}
        errors.append("auth_database")
        print(f"[health] auth database lỗi: {exc}", file=sys.stderr)

    try:
        disk = shutil.disk_usage(PIPELINE_STORE.db_path.parent)
        checks["disk"] = {
            "free_bytes": disk.free,
            "reserve_bytes": UPLOAD_DISK_RESERVE_BYTES,
        }
        if disk.free < UPLOAD_DISK_RESERVE_BYTES:
            errors.append("disk_reserve")
    except OSError as exc:
        checks["disk"] = {"free_bytes": 0}
        errors.append("disk")
        print(f"[health] disk lỗi: {exc}", file=sys.stderr)

    raw_worker = PIPELINE_STORE.get_meta("worker_heartbeat", "")
    try:
        worker = json.loads(raw_worker) if raw_worker else {}
    except ValueError:
        worker = {}
    worker_age = max(0, now - float(worker.get("timestamp") or 0))
    worker_ok = bool(worker) and worker_age <= _env_int(
        "WORKER_HEALTH_MAX_AGE_SECONDS", 35
    )
    checks["worker"] = {
        "ok": worker_ok,
        "age_seconds": round(worker_age, 1) if worker else None,
        "queue": worker.get("queue", ""),
        "workers": int(worker.get("workers") or 0),
    }
    if not worker_ok:
        errors.append("worker")

    maintenance_at = float(
        PIPELINE_STORE.get_meta("maintenance_last_success", "0") or 0
    )
    checks["maintenance"] = {
        "ok": maintenance_at > 0 and now - maintenance_at <= 2 * 86400,
        "age_seconds": round(max(0, now - maintenance_at), 1)
        if maintenance_at
        else None,
    }
    if not checks["maintenance"]["ok"]:
        warnings.append("maintenance")

    try:
        backup_status = json.loads(
            BACKUP_STATUS_FILE.read_text(encoding="utf-8")
        )
    except Exception:
        backup_status = {}
    backup_at = float(backup_status.get("timestamp") or 0)
    backup_age = max(0, now - backup_at) if backup_at else None
    local_backup_ok = bool(backup_status.get("ok")) and (
        backup_age is not None and backup_age <= 2 * 86400
    )
    offsite_backup_ok = bool(
        (backup_status.get("drive") or {}).get("ok")
    )
    checks["backup"] = {
        "local_ok": local_backup_ok,
        "offsite_ok": offsite_backup_ok,
        "age_seconds": round(backup_age, 1)
        if backup_age is not None
        else None,
    }
    if backup_at and not local_backup_ok:
        errors.append("backup_stale")
    elif not backup_at:
        warnings.append("backup_missing")
    if not offsite_backup_ok:
        warnings.append("backup_offsite")

    status = "ok" if not errors else "error"
    return {
        "status": status,
        "checks": checks,
        "errors": errors,
        "warnings": warnings,
    }, (200 if not errors else 503)


# ── Đăng bài (Zernio TikTok) ────────────────────────────────────────────────

# Key Zernio riêng từng tài khoản (admin nhập ở Cài đặt) — data/user_keys.json
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
    # One centrally managed Apify key only; never fall back to deleted or
    # per-user keys.
    return (os.getenv("APIFY_KEY_VIETCHINH") or "").strip()


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
    record = next((p for p in _load_products() if p.get("video_url") == video_url), None)
    if record:
        PIPELINE_STORE.update_resource("video", record["id"], **fields)


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


def _zernio_local_status(result: dict) -> str:
    post = result.get("provider_post") if isinstance(result.get("provider_post"), dict) else {}
    raw = str(result.get("provider_status") or post.get("status") or "").lower()
    platforms = post.get("platforms") if isinstance(post.get("platforms"), list) else []
    platform_states = {
        str(item.get("status") or "").lower()
        for item in platforms
        if isinstance(item, dict)
    }
    if raw == "published" or (platform_states and platform_states <= {"published"}):
        return "posted"
    if raw == "failed" or (platform_states and platform_states <= {"failed", "cancelled"}):
        return "failed"
    if raw in {"partial", "cancelled"}:
        return "unknown"
    return "publishing"


def _confirm_zernio_post(result: dict, api_key: str) -> dict:
    """Briefly poll accepted posts; hourly maintenance handles slower providers."""
    post_id = str(result.get("id") or "")
    if not result.get("success") or not post_id:
        return result
    if _zernio_local_status(result) in {"posted", "failed", "unknown"}:
        return result
    from tools import publisher

    deadline = time.monotonic() + _env_int("ZERNIO_CONFIRM_SECONDS", 45, 0)
    latest = result
    while time.monotonic() < deadline:
        time.sleep(3)
        checked = publisher.get_zernio_post(post_id, api_key=api_key)
        if not checked.get("success"):
            break
        latest = checked
        if _zernio_local_status(latest) in {"posted", "failed", "unknown"}:
            break
    return latest


def _update_publish_resource(kind: str, resource_id: str, **fields) -> dict | None:
    return PIPELINE_STORE.update_resource(kind, resource_id, **fields)


def _provider_error(result: dict) -> str:
    post = result.get("provider_post") if isinstance(result.get("provider_post"), dict) else {}
    for platform in post.get("platforms") or []:
        if isinstance(platform, dict) and platform.get("error"):
            return str(platform["error"])
    return str(result.get("error") or "")


def _do_publish(
    resource_id: str,
    caption: str,
    user: str,
    ki: int = 0,
    account_id: str = "",
    request_id: str = "",
) -> dict:
    """Publish one exact video through a short-lived signed media URL."""
    record = _find_product(resource_id)
    if not record:
        return {"success": False, "error": "Không tìm thấy video"}
    api_key = _user_zernio(user, ki)
    request_id = request_id or str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"dulich:publish:video:{resource_id}:{account_id or ki}",
        )
    )
    try:
        from tools import publisher
        if record.get("zernio_post_id") and (
            record.get("status") == "failed"
            or str(record.get("provider_status") or "").lower() == "failed"
        ):
            res = publisher.retry_zernio_post(
                record["zernio_post_id"],
                api_key=api_key,
            )
        else:
            res = publisher.post_to_tiktok(
                _signed_media_url("video", record["id"]),
                caption,
                api_key=api_key,
                account_id=account_id or None,
                request_id=request_id,
            )
    except Exception as e:
        res = {"success": False, "error": str(e)}
    if res.get("success") and res.get("id"):
        _update_publish_resource(
            "video",
            resource_id,
            status="publishing",
            zernio_post_id=res["id"],
            zernio_request_id=request_id,
            zernio_ki=ki,
            zernio_account_id=account_id,
            provider_status=res.get("provider_status", ""),
            provider_checked_at=time.time(),
        )
        res = _confirm_zernio_post(res, api_key)
        status = _zernio_local_status(res)
    elif res.get("success"):
        status = "unknown"
        res["error"] = "Zernio nhận request nhưng không trả post id để đối soát."
    else:
        status = "unknown" if _is_uncertain_publish_err(res.get("error")) else "failed"
    if status in {"failed", "unknown"}:
        res["success"] = False
    res["status"] = status
    _update_publish_resource(
        "video",
        resource_id,
        status=status,
        zernio_post_id=res.get("id") or record.get("zernio_post_id", ""),
        zernio_request_id=request_id,
        zernio_ki=ki,
        zernio_account_id=account_id,
        provider_status=res.get("provider_status", ""),
        provider_checked_at=time.time(),
        platform_url=res.get("platform_url", ""),
        publish_error=_provider_error(res),
        posted_at=time.time() if status == "posted" else record.get("posted_at"),
    )
    res.pop("provider_post", None)
    return res


def _do_publish_album(
    resource_id: str,
    user: str,
    ki: int = 0,
    account_id: str = "",
    request_id: str = "",
) -> dict:
    """Publish an album through exact, expiring signed image URLs."""
    rec = _find_album(resource_id)
    urls = [
        _signed_media_url("album", rec["id"], str(index))
        for index, image in enumerate((rec or {}).get("images") or [])
        if image.get("url")
    ]
    if not urls:
        return {"success": False, "error": "Album không có ảnh"}
    caption = _album_caption(rec)   # caption sáng tạo + hashtag theo chủ đề album (OpenRouter)
    api_key = _user_zernio(user, ki)
    request_id = request_id or str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"dulich:publish:album:{resource_id}:{account_id or ki}",
        )
    )
    try:
        from tools import publisher
        if rec.get("zernio_post_id") and (
            rec.get("status") == "failed"
            or str(rec.get("provider_status") or "").lower() == "failed"
        ):
            res = publisher.retry_zernio_post(
                rec["zernio_post_id"],
                api_key=api_key,
            )
        else:
            res = publisher.post_images_to_tiktok(
                urls,
                caption,
                api_key=api_key,
                account_id=account_id or None,
                request_id=request_id,
            )
    except Exception as e:
        res = {"success": False, "error": str(e)}
    if res.get("success") and res.get("id"):
        _update_publish_resource(
            "album",
            resource_id,
            status="publishing",
            zernio_post_id=res["id"],
            zernio_request_id=request_id,
            zernio_ki=ki,
            zernio_account_id=account_id,
            provider_status=res.get("provider_status", ""),
            provider_checked_at=time.time(),
        )
        res = _confirm_zernio_post(res, api_key)
        status = _zernio_local_status(res)
    elif res.get("success"):
        status = "unknown"
        res["error"] = "Zernio nhận request nhưng không trả post id để đối soát."
    else:
        status = "unknown" if _is_uncertain_publish_err(res.get("error")) else "failed"
    if status in {"failed", "unknown"}:
        res["success"] = False
    res["status"] = status
    _update_publish_resource(
        "album",
        resource_id,
        status=status,
        zernio_post_id=res.get("id") or rec.get("zernio_post_id", ""),
        zernio_request_id=request_id,
        zernio_ki=ki,
        zernio_account_id=account_id,
        provider_status=res.get("provider_status", ""),
        provider_checked_at=time.time(),
        platform_url=res.get("platform_url", ""),
        publish_error=_provider_error(res),
        posted_at=time.time() if status == "posted" else rec.get("posted_at"),
    )
    res.pop("provider_post", None)
    return res


def _publish_job_for_resource(kind: str, resource_id: str) -> dict | None:
    jobs = PIPELINE_STORE.list_jobs(
        kinds=[f"publish_{kind}"],
        limit=200,
    )
    return next(
        (
            job
            for job in jobs
            if (job.get("payload") or {}).get("resource_id") == resource_id
        ),
        None,
    )


def _reconcile_publish_resource(
    kind: str,
    resource_id: str,
    *,
    job: dict | None = None,
) -> dict:
    """Query Zernio before deciding whether a publish may be retried."""
    record = _find_product(resource_id) if kind == "video" else _find_album(resource_id)
    if not record:
        return {"success": False, "status": "unknown", "error": "Không tìm thấy nội dung."}
    post_id = str(record.get("zernio_post_id") or "")
    if not post_id:
        return {
            "success": False,
            "status": "unknown",
            "error": "Chưa có Zernio post id nên không thể đối soát tự động.",
        }
    job = job or _publish_job_for_resource(kind, resource_id)
    payload = (job or {}).get("payload") or {}
    ki = int(payload.get("zernio_ki", record.get("zernio_ki", 0)) or 0)
    owner = str(record.get("user") or (job or {}).get("owner") or "")
    from tools import publisher

    checked = publisher.get_zernio_post(post_id, api_key=_user_zernio(owner, ki))
    if not checked.get("success"):
        _update_publish_resource(
            kind,
            resource_id,
            status="unknown",
            provider_checked_at=time.time(),
            publish_error=checked.get("error", ""),
        )
        return {
            "success": False,
            "status": "unknown",
            "error": checked.get("error") or "Không đọc được trạng thái Zernio.",
        }

    status = _zernio_local_status(checked)
    error = _provider_error(checked)
    previous_status = str(record.get("status") or "")
    _update_publish_resource(
        kind,
        resource_id,
        status=status,
        provider_status=checked.get("provider_status", ""),
        provider_checked_at=time.time(),
        platform_url=checked.get("platform_url", ""),
        publish_error=error,
        posted_at=time.time() if status == "posted" else record.get("posted_at"),
    )
    if job and status == "posted":
        PIPELINE_STORE.resolve_external_job(
            job["id"],
            status="done",
            result={
                "success": True,
                "status": "posted",
                "id": post_id,
                "platform_url": checked.get("platform_url", ""),
                "reconciled": True,
            },
        )
    elif job and status == "failed":
        PIPELINE_STORE.resolve_external_job(
            job["id"],
            status="failed",
            error=error or "Zernio xác nhận đăng bài thất bại.",
            result={
                "success": False,
                "status": "failed",
                "id": post_id,
                "reconciled": True,
            },
        )
    if kind == "video" and status == "posted" and previous_status != "posted":
        _archive_video(record.get("video_url", ""))
    checked.pop("provider_post", None)
    return {
        "success": True,
        "status": status,
        "post_id": post_id,
        "platform_url": checked.get("platform_url", ""),
        "error": error,
    }


def _reconcile_pending_publishes(limit: int = 20) -> dict:
    checked = posted = failed = unknown = 0
    for kind, records in (("video", _load_products()), ("album", _load_albums())):
        for record in records:
            if checked >= max(1, int(limit)):
                return {
                    "checked": checked,
                    "posted": posted,
                    "failed": failed,
                    "unknown": unknown,
                }
            if (
                record.get("status") not in {"publishing", "unknown"}
                or not record.get("zernio_post_id")
            ):
                continue
            result = _reconcile_publish_resource(kind, record["id"])
            checked += 1
            status = result.get("status")
            posted += int(status == "posted")
            failed += int(status == "failed")
            unknown += int(status == "unknown")
    return {
        "checked": checked,
        "posted": posted,
        "failed": failed,
        "unknown": unknown,
    }


def _publish_dashboard_resource(resource_id: str, payload: dict | None = None) -> dict:
    """Idempotently upload one video to Drive/Supabase outside the HTTP request."""
    payload = payload or {}
    record = _find_product(resource_id)
    if not record:
        return {"success": False, "error": "Không tìm thấy video."}
    try:
        full_path = _output_file_from_url(record.get("video_url", ""))
    except (OSError, ValueError):
        return {"success": False, "error": "Video local không tồn tại."}
    if not full_path.exists():
        return {"success": False, "error": "Video local không tồn tại."}

    sb = _get_supabase()
    if not sb or not sb.url:
        return {"success": False, "error": "Supabase chưa được cấu hình."}
    # A retry or duplicate admin tab returns the already-created record.
    existing = sb.get_content_by_job_id(resource_id)
    if existing and existing.get("id"):
        return {
            "success": True,
            "content_id": existing["id"],
            "drive_url": existing.get("drive_url", ""),
            "deduplicated": True,
        }

    actual_drive_url = record.get("drive_link", "")
    if not actual_drive_url:
        try:
            from tools.drive_uploader import get_drive_uploader

            upload_result = get_drive_uploader().upload_video(str(full_path), resource_id)
            if upload_result.get("webViewLink"):
                actual_drive_url = upload_result["webViewLink"]
                _update_product(record.get("video_url", ""), drive_link=actual_drive_url)
            elif upload_result.get("error"):
                return {
                    "success": False,
                    "error": f"Google Drive: {upload_result['error']}",
                }
        except Exception as exc:
            return {"success": False, "error": f"Google Drive: {exc}"}

    content_data = {
        "user_id": record.get("user") or None,
        "content_type": payload.get("video_type", "video"),
        "status": "pending",
        "title": record.get("topic", ""),
        "topic": record.get("topic", ""),
        "script": payload.get("script", {}),
        "drive_url": actual_drive_url,
        "local_path": record.get("video_url", ""),
        "hook_style": record.get("hook_style", ""),
        "hook_text": payload.get("hook_text", ""),
        "job_id": resource_id,
        "video_type": payload.get("video_type", "video"),
    }
    created = sb.create_content(content_data)
    if created and created.get("id"):
        return {
            "success": True,
            "content_id": created["id"],
            "drive_url": actual_drive_url,
        }
    return {"success": False, "error": f"Lỗi Supabase: {created}"}


# Album ảnh đã tạo — lưu lại như "Tất cả video" (mở lại / xoá / tạo lại).
ALBUM_PRODUCTS_FILE = Path(__file__).parent / "output" / "album_products.json"
_ALBUM_PROD_LOCK = threading.Lock()


def _load_albums() -> list:
    if not PIPELINE_STORE.resource_migration_done("album"):
        with _ALBUM_PROD_LOCK:
            if not PIPELINE_STORE.resource_migration_done("album"):
                try:
                    legacy = json.loads(ALBUM_PRODUCTS_FILE.read_text(encoding="utf-8"))
                    if not isinstance(legacy, list):
                        legacy = []
                except Exception:
                    legacy = []
                for item in legacy:
                    item["id"] = _stable_resource_id("album", item)
                PIPELINE_STORE.import_resources("album", legacy)
                PIPELINE_STORE.mark_resource_migration_done("album")
    return PIPELINE_STORE.list_resources("album")


def _append_album(rec: dict) -> dict:
    rec = dict(rec)
    rec.setdefault("id", rec.get("job_id") or uuid.uuid4().hex[:20])
    rec.setdefault("status", "pending")
    _load_albums()
    return PIPELINE_STORE.insert_resource_once("album", rec)[0]


def _set_album_status(key: str, status: str) -> bool:
    """Change an album status by opaque id (legacy directory accepted internally)."""
    record = _find_album(key)
    if not record:
        record = next((a for a in _load_albums() if a.get("dir") == key), None)
    if not record:
        return False
    return bool(PIPELINE_STORE.update_resource("album", record["id"], status=status))


def _find_album(resource_id: str) -> dict | None:
    _load_albums()
    return PIPELINE_STORE.get_resource("album", resource_id)


def _album_view(record: dict) -> dict:
    item = dict(record)
    resource_id = _stable_resource_id("album", item)
    item["id"] = resource_id
    item["images"] = [
        {**image, "url": _media_url("album", resource_id, str(index))}
        for index, image in enumerate(item.get("images") or [])
    ]
    item.pop("dir", None)
    return item


def _delete_album(resource_id: str) -> bool:
    """Delete an album by id after resolving its stored directory under output/albums."""
    record = _find_album(resource_id)
    if not record:
        return False
    dir_rel = str(record.get("dir") or "").replace("\\", "/")
    if not dir_rel.startswith("output/albums/"):
        return False
    try:
        target = _resolve_under(OUTPUT_DIR / "albums", dir_rel[len("output/albums/"):])
    except ValueError:
        return False
    PIPELINE_STORE.delete_resource("album", resource_id)
    try:
        shutil.rmtree(str(target), ignore_errors=True)
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
    if content_length <= 0:
        raise UploadValidationError("Request upload rỗng.")
    if content_length > MAX_LEGACY_MULTIPART_BYTES:
        handler.close_connection = True
        raise UploadValidationError(
            "Endpoint upload cũ chỉ nhận tối đa "
            f"{MAX_LEGACY_MULTIPART_BYTES // (1024 * 1024)} MB; "
            "hãy tải bằng giao diện mới có chia nhỏ file."
        )
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
        """The web UI is same-origin; cross-origin preflight is not supported."""
        self.send_response(405)
        self.send_header("Allow", "GET, POST")
        self._cors_headers()
        self.end_headers()

    def _cors_headers(self):
        """Legacy name retained for call sites; now emits security headers, not CORS."""
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "same-origin")

    def _json_response(self, data: dict, status: int = 200, headers: dict | None = None):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self._cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for key, value in (headers or {}).items():
            if isinstance(value, (list, tuple)):
                for entry in value:
                    self.send_header(key, str(entry))
            else:
                self.send_header(key, str(value))
        self.end_headers()
        self.wfile.write(body)

    def _cookies(self) -> SimpleCookie:
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get("Cookie", ""))
        except Exception:
            pass
        return cookie

    def _session_token(self) -> str:
        morsel = self._cookies().get("dulich_session")
        return morsel.value if morsel else ""

    def _csrf_cookie(self) -> str:
        morsel = self._cookies().get("dulich_csrf")
        return morsel.value if morsel else ""

    def _cookie_flags(self, *, http_only: bool) -> str:
        origin = (os.getenv("APP_ORIGIN") or "").strip().lower()
        secure_env = (os.getenv("AUTH_COOKIE_SECURE") or "").strip().lower()
        forwarded_proto = (
            self.headers.get("X-Forwarded-Proto", "").split(",", 1)[0].strip().lower()
        )
        secure = secure_env in {"1", "true", "yes"} or (
            secure_env == ""
            and (origin.startswith("https://") or forwarded_proto == "https")
        )
        flags = "Path=/; SameSite=Strict"
        if http_only:
            flags += "; HttpOnly"
        if secure:
            flags += "; Secure"
        return flags

    def _load_auth(self) -> bool:
        session = AUTH_STORE.get_session(self._session_token())
        if not session:
            self._json_response({"error": "Bạn chưa đăng nhập hoặc phiên đã hết hạn."}, 401)
            return False
        self.auth_session = session
        self.auth_user = session["username"]
        self.auth_role = session["role"]
        return True

    def _origin_allowed(self) -> bool:
        origin = (self.headers.get("Origin") or "").rstrip("/")
        if not origin:
            return True
        configured = (os.getenv("APP_ORIGIN") or "").rstrip("/")
        if configured:
            return hmac.compare_digest(origin, configured)
        forwarded = (self.headers.get("X-Forwarded-Proto") or "").split(",", 1)[0].strip()
        scheme = forwarded if forwarded in {"http", "https"} else "http"
        expected = f"{scheme}://{self.headers.get('Host', '')}".rstrip("/")
        return hmac.compare_digest(origin, expected)

    def _require_csrf(self) -> bool:
        token = self.headers.get("X-CSRF-Token", "")
        if AUTH_STORE.csrf_matches(self.auth_session, token):
            return True
        self._json_response({"error": "CSRF token không hợp lệ."}, 403)
        return False

    def _forbid_unless(self, roles: set[str]) -> bool:
        if self.auth_role in roles:
            return False
        self._json_response({"error": "Bạn không có quyền thực hiện thao tác này."}, 403)
        return True

    def do_POST(self):
        path = urlparse(self.path).path
        self.path = path
        if not self._origin_allowed():
            self._json_response({"error": "Origin không được phép."}, 403)
            return
        if path == "/login":
            self.handle_login()
            return
        if path == "/health":
            self._json_response({"error": "Method not allowed"}, 405)
            return
        if path in {"/open-folder", "/download-file"}:
            self._json_response({"error": "Endpoint đã bị vô hiệu hóa; hãy dùng media resource ID."}, 410)
            return
        if not self._load_auth() or not self._require_csrf():
            return
        admin_only = {
            "/settings", "/user-keys", "/venues-delete", "/venue-image-delete",
            "/venues-scrape-all", "/images-delete", "/product-status",
            "/publish-to-dashboard", "/publish-reconcile",
        }
        news_only = {"/news-use", "/news-scrape", "/news-research"}
        if path in admin_only and self._forbid_unless({"admin"}):
            return
        if path in news_only and self._forbid_unless({"news", "admin"}):
            return
        if self.path == "/logout":
            self.handle_logout()
        elif self.path == "/uploads/init":
            self.handle_upload_init()
        elif self.path.startswith("/uploads/") and self.path.endswith("/complete"):
            self.handle_upload_complete()
        elif self.path == "/uploads/cancel":
            self.handle_upload_cancel()
        elif self.path == "/jobs":
            self.handle_job_create()
        elif self.path == "/jobs/cancel":
            self.handle_job_cancel()
        elif self.path == "/jobs/retry":
            self.handle_job_retry()
        elif self.path == "/publish-reconcile":
            self.handle_publish_reconcile()
        elif self.path == "/assemble":
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

    def do_PUT(self):
        path = urlparse(self.path).path
        self.path = path
        if not self._origin_allowed():
            self._json_response({"error": "Origin không được phép."}, 403)
            return
        if not self._load_auth() or not self._require_csrf():
            return
        if path.startswith("/uploads/"):
            self.handle_upload_chunk()
            return
        self._json_response({"error": f"Unknown path: {path}"}, 404)

    def do_GET(self):
        path = urlparse(self.path).path
        spa_paths = {
            "/", "/app", "/index.html", "/trang-chu", "/video",
            "/thu-vien", "/anh", "/cai-dat",
        }
        if path.startswith("/media/"):
            public = path.startswith("/media/public/")
            if not public and not self._load_auth():
                return
            self.handle_media(public=public)
            return
        if path.startswith("/output/"):
            self._json_response({"error": "Direct output paths are not available."}, 404)
            return
        is_public = (
            path in spa_paths
            or path == "/health"
            or path.startswith("/font/")
            or path.startswith("/hookframe/")
        )
        if not is_public and not self._load_auth():
            return
        if path in {"/settings", "/user-keys", "/stats", "/kpi"}:
            if self._forbid_unless({"admin"}):
                return
        if path.startswith("/news-pool") and self._forbid_unless({"news", "admin"}):
            return
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
        elif self.path.startswith("/album-zip/"):
            self.handle_album_zip()
        elif self.path.startswith("/hookframe/"):
            self._serve_hookframe(self.path[len("/hookframe/"):])
        elif self.path.startswith("/font/"):
            self._serve_font(self.path[len("/font/"):])
        elif self.path == "/health":
            payload, status = _health_snapshot()
            self._json_response(payload, status)
        elif self.path == "/session":
            self.handle_session()
        elif self.path.startswith("/uploads/"):
            self.handle_upload_status()
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
        else:
            self._json_response({"error": "Not found"}, 404)

    def handle_media(self, *, public: bool) -> None:
        """Resolve an opaque media id to one owned file and stream it safely."""
        parsed = urlparse(self.path)
        parts = [part for part in parsed.path.split("/") if part]
        offset = 2 if public else 1
        try:
            kind = parts[offset]
            resource_id = unquote(parts[offset + 1])
            asset = unquote(parts[offset + 2]) if len(parts) > offset + 2 else ""
        except IndexError:
            self._json_response({"error": "Media URL không hợp lệ."}, 404)
            return

        if public:
            if not _verify_signed_media(parsed.path, parse_qs(parsed.query)):
                self._json_response({"error": "Media URL đã hết hạn hoặc không hợp lệ."}, 403)
                return

        record: dict | None = None
        stored_url = ""
        if kind == "temp" and not public:
            with _TEMP_MEDIA_LOCK:
                temp = dict(_TEMP_MEDIA.get(resource_id) or {})
            if (
                not temp
                or int(temp.get("expires_at", 0)) <= int(time.time())
                or (self.auth_role != "admin" and temp.get("owner") != self.auth_user)
            ):
                self._json_response({"error": "Không tìm thấy media."}, 404)
                return
            try:
                file_path = Path(temp["path"]).resolve(strict=True)
                file_path.relative_to(OUTPUT_DIR)
            except (OSError, ValueError):
                self._json_response({"error": "Không tìm thấy media."}, 404)
                return
            self._stream_file(
                file_path,
                download=(parse_qs(parsed.query).get("download") or ["0"])[0] == "1",
            )
            return
        if kind == "video":
            record = _find_product(resource_id)
            key = {"": "video_url", "thumb": "thumb_url", "preview": "preview_url"}.get(asset)
            if key:
                stored_url = str((record or {}).get(key) or "")
        elif kind == "album":
            record = _find_album(resource_id)
            try:
                index = int(asset)
                stored_url = str(((record or {}).get("images") or [])[index].get("url") or "")
            except (ValueError, IndexError, AttributeError):
                stored_url = ""
        if not record or not stored_url:
            self._json_response({"error": "Không tìm thấy media."}, 404)
            return
        if not public and self.auth_role != "admin" and record.get("user") != self.auth_user:
            self._json_response({"error": "Không tìm thấy media."}, 404)
            return
        try:
            file_path = _output_file_from_url(stored_url)
        except (OSError, ValueError):
            self._json_response({"error": "Media không tồn tại trên server."}, 404)
            return
        try:
            width = int((parse_qs(parsed.query).get("w") or ["0"])[0])
        except (TypeError, ValueError):
            width = 0
        self._stream_file(
            _image_variant(file_path, width),
            download=(parse_qs(parsed.query).get("download") or ["0"])[0] == "1",
            public=public,
        )

    def _stream_file(self, file_path: Path, *, download: bool = False, public: bool = False) -> None:
        mime_map = {
            ".mp4": "video/mp4", ".mov": "video/quicktime",
            ".wav": "audio/wav", ".mp3": "audio/mpeg", ".srt": "text/plain",
            ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".webp": "image/webp", ".gif": "image/gif",
        }
        mime = mime_map.get(file_path.suffix.lower(), "application/octet-stream")
        size = file_path.stat().st_size
        start, end, use_range = 0, max(0, size - 1), False
        range_header = self.headers.get("Range", "")
        if size and range_header.startswith("bytes=") and "," not in range_header:
            try:
                left, right = range_header[6:].split("-", 1)
                if left.strip() == "":
                    start = max(0, size - int(right))
                else:
                    start = int(left)
                    if right.strip():
                        end = min(int(right), size - 1)
                use_range = 0 <= start <= end < size
            except (TypeError, ValueError):
                use_range = False
        if range_header and not use_range:
            self.send_response(416)
            self._cors_headers()
            self.send_header("Content-Range", f"bytes */{size}")
            self.end_headers()
            return
        length = end - start + 1 if size else 0
        self.send_response(206 if use_range else 200)
        self._cors_headers()
        self.send_header("Content-Type", mime)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "private, max-age=300" if not public else "public, max-age=120")
        if download:
            safe_name = file_path.name.replace('"', "_")
            self.send_header("Content-Disposition", f'attachment; filename="{safe_name}"')
        if use_range:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Connection", "close")
        self.end_headers()
        remaining = length
        with file_path.open("rb") as handle:
            if use_range:
                handle.seek(start)
            while remaining:
                chunk = handle.read(min(65536, remaining))
                if not chunk:
                    break
                try:
                    self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    break
                remaining -= len(chunk)
        self.close_connection = True

    def _read_json_body(self) -> dict:
        """Read and parse JSON body from request."""
        length = int(self.headers.get("Content-Length", 0))
        if length > 2 * 1024 * 1024:
            raise ValueError("JSON body vượt giới hạn 2 MB.")
        body = self.rfile.read(length)
        return json.loads(body.decode("utf-8")) if body else {}

    # ── Resumable streaming uploads + durable jobs ───────────────────────

    def handle_upload_init(self):
        try:
            body = self._read_json_body()
            kind = str(body.get("kind") or "")
            payload = body.get("payload")
            request_id = str(body.get("request_id") or "").strip()
            reserves_job = payload is not None or bool(request_id)
            if reserves_job and (not isinstance(payload, dict) or not request_id):
                self._json_response(
                    {
                        "success": False,
                        "error": "Thiếu payload hoặc mã yêu cầu để giữ chỗ hàng đợi.",
                    },
                    400,
                )
                return
            if reserves_job:
                if self.auth_role == "staff" and kind != "listreview_video":
                    self._json_response(
                        {
                            "success": False,
                            "error": "Nhân viên chỉ dùng luồng list-review.",
                        },
                        403,
                    )
                    return
                if self.auth_role == "news" and kind != "personal_video":
                    self._json_response(
                        {
                            "success": False,
                            "error": "Tài khoản tin tức chỉ dùng video thường.",
                        },
                        403,
                    )
                    return
                payload = _authoritative_render_payload(
                    self.auth_user, self.auth_role, kind, payload
                )
            session = PIPELINE_STORE.create_upload_session(
                owner=self.auth_user,
                kind=kind,
                files=body.get("files") if isinstance(body.get("files"), list) else [],
                max_file_bytes=MAX_UPLOAD_FILE_BYTES,
                max_job_bytes=MAX_UPLOAD_JOB_BYTES,
                max_active_sessions=MAX_UPLOAD_SESSIONS_PER_USER,
                reserve_free_bytes=UPLOAD_DISK_RESERVE_BYTES,
                payload=payload if reserves_job else None,
                idempotency_key=(
                    f"render-upload:{self.auth_user}:{request_id}"
                    if reserves_job
                    else ""
                ),
                active_job_limit=MAX_ACTIVE_JOBS_PER_USER,
                global_active_job_limit=MAX_GLOBAL_ACTIVE_JOBS,
                max_attempts=2,
            )
            self._json_response({"success": True, "upload": session}, 201)
        except QueueLimitError as exc:
            self._json_response({"success": False, "error": str(exc)}, 429)
        except UploadValidationError as exc:
            status = 507 if "dung lượng trống" in str(exc) else 400
            self._json_response({"success": False, "error": str(exc)}, status)
        except Exception as exc:
            self._json_response({"success": False, "error": str(exc)}, 500)

    def handle_upload_chunk(self):
        parts = [part for part in self.path.split("/") if part]
        if len(parts) != 3 or parts[0] != "uploads":
            self._json_response({"success": False, "error": "URL upload không hợp lệ."}, 404)
            return
        session_id, file_id = parts[1], parts[2]
        try:
            length = int(self.headers.get("Content-Length") or 0)
            offset = int(self.headers.get("X-Upload-Offset") or 0)
            result = PIPELINE_STORE.append_upload_chunk(
                session_id=session_id,
                file_id=file_id,
                owner=self.auth_user,
                offset=offset,
                length=length,
                source=self.rfile,
                max_chunk_bytes=MAX_UPLOAD_CHUNK_BYTES,
            )
            self._json_response({"success": True, **result})
        except UploadValidationError as exc:
            status = 409 if "Offset" in str(exc) or "không đồng nhất" in str(exc) else 400
            self._json_response({"success": False, "error": str(exc)}, status)
        except Exception as exc:
            self._json_response({"success": False, "error": str(exc)}, 500)

    def handle_upload_complete(self):
        parts = [part for part in self.path.split("/") if part]
        if len(parts) != 3 or parts[0] != "uploads" or parts[2] != "complete":
            self._json_response({"success": False, "error": "URL upload không hợp lệ."}, 404)
            return
        try:
            result = PIPELINE_STORE.complete_upload(parts[1], self.auth_user)
            try:
                _validate_uploaded_media(result)
            except UploadValidationError:
                PIPELINE_STORE.cancel_upload(parts[1], self.auth_user)
                raise
            job = PIPELINE_STORE.queue_reserved_upload(parts[1], self.auth_user)
            if job:
                result["status"] = "consumed"
                result["job_id"] = job["id"]
                result["job_status"] = job["status"]
                self._json_response(
                    {
                        "success": True,
                        "queued": True,
                        "job_id": job["id"],
                        "position": PIPELINE_STORE.queue_position(job["id"]),
                        "upload": result,
                        "job": _job_client_view(job),
                    }
                )
                return
            self._json_response({"success": True, "upload": result})
        except UploadValidationError as exc:
            message = str(exc)
            status = 415 if "video" in message.lower() or "ffprobe" in message.lower() else 409
            self._json_response({"success": False, "error": message}, status)
        except Exception as exc:
            self._json_response({"success": False, "error": str(exc)}, 500)

    def handle_upload_status(self):
        parts = [part for part in urlparse(self.path).path.split("/") if part]
        if len(parts) != 2 or parts[0] != "uploads":
            self._json_response({"success": False, "error": "URL upload không hợp lệ."}, 404)
            return
        result = PIPELINE_STORE.get_upload_session(
            parts[1],
            self.auth_user,
            is_admin=self.auth_role == "admin",
        )
        if not result:
            self._json_response({"success": False, "error": "Không tìm thấy upload."}, 404)
            return
        result["files"] = [
            {
                "id": item["id"],
                "field": item["field_name"],
                "name": item["original_name"],
                "size": item["expected_size"],
                "received": item["received_size"],
                "status": item["status"],
            }
            for item in result.get("files") or []
        ]
        if result.get("job_id"):
            job = PIPELINE_STORE.get_job(str(result["job_id"]))
            result["job_status"] = str((job or {}).get("status") or "")
        self._json_response({"success": True, "upload": result})

    def handle_upload_cancel(self):
        try:
            session_id = str((self._read_json_body() or {}).get("upload_id") or "")
            ok = PIPELINE_STORE.cancel_upload(
                session_id,
                self.auth_user,
                is_admin=self.auth_role == "admin",
            )
            self._json_response({"success": ok}, 200 if ok else 404)
        except Exception as exc:
            self._json_response({"success": False, "error": str(exc)}, 500)

    def handle_job_create(self):
        try:
            body = self._read_json_body()
            kind = str(body.get("kind") or "")
            upload_id = str(body.get("upload_id") or "")
            payload = body.get("payload") if isinstance(body.get("payload"), dict) else {}
            if kind not in {"personal_video", "listreview_video"}:
                self._json_response({"success": False, "error": "Loại job không hợp lệ."}, 400)
                return
            if self.auth_role == "staff" and kind != "listreview_video":
                self._json_response({"success": False, "error": "Nhân viên chỉ dùng luồng list-review."}, 403)
                return
            if self.auth_role == "news" and kind != "personal_video":
                self._json_response({"success": False, "error": "Tài khoản tin tức chỉ dùng video thường."}, 403)
                return
            payload = _authoritative_render_payload(
                self.auth_user, self.auth_role, kind, payload
            )
            job, created = PIPELINE_STORE.create_job_from_upload(
                session_id=upload_id,
                owner=self.auth_user,
                kind=kind,
                payload=payload,
                active_limit=MAX_ACTIVE_JOBS_PER_USER,
                max_attempts=2,
            )
            position = PIPELINE_STORE.queue_position(job["id"])
            self._json_response(
                {
                    "success": True,
                    "queued": True,
                    "created": created,
                    "job_id": job["id"],
                    "position": position,
                    "job": _job_client_view(job),
                },
                202,
            )
        except QueueLimitError as exc:
            self._json_response({"success": False, "error": str(exc)}, 429)
        except UploadValidationError as exc:
            self._json_response({"success": False, "error": str(exc)}, 409)
        except Exception as exc:
            import traceback

            print(f"[jobs] create lỗi: {exc}\n{traceback.format_exc()}", file=sys.stderr)
            self._json_response({"success": False, "error": str(exc)}, 500)

    def handle_job_cancel(self):
        try:
            job_id = str((self._read_json_body() or {}).get("job_id") or "")
            existing = PIPELINE_STORE.get_job(job_id)
            if (
                existing
                and str(existing.get("kind") or "").startswith("publish_")
                and existing.get("status") == "running"
            ):
                self._json_response(
                    {
                        "success": False,
                        "error": (
                            "Không thể hủy publish đang gửi ra nhà cung cấp; "
                            "hãy chờ hệ thống đối soát để tránh trạng thái mơ hồ."
                        ),
                    },
                    409,
                )
                return
            job = PIPELINE_STORE.cancel_job(
                job_id,
                self.auth_user,
                is_admin=self.auth_role == "admin",
            )
            if not job:
                self._json_response({"success": False, "error": "Không tìm thấy job."}, 404)
                return
            if job.get("status") == "cancelled":
                PIPELINE_STORE.cleanup_job_upload(job_id)
            self._json_response({"success": True, "job": _job_client_view(job)})
        except Exception as exc:
            self._json_response({"success": False, "error": str(exc)}, 500)

    def handle_job_retry(self):
        try:
            job_id = str((self._read_json_body() or {}).get("job_id") or "")
            job = PIPELINE_STORE.retry_job(
                job_id,
                self.auth_user,
                is_admin=self.auth_role == "admin",
                active_limit=MAX_ACTIVE_JOBS_PER_USER,
            )
            if not job:
                self._json_response(
                    {"success": False, "error": "Job không thể thử lại."}, 409
                )
                return
            self._json_response({"success": True, "job": _job_client_view(job)})
        except QueueLimitError as exc:
            self._json_response({"success": False, "error": str(exc)}, 429)
        except Exception as exc:
            self._json_response({"success": False, "error": str(exc)}, 500)

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
        """List products from the authenticated user's server-side identity."""
        q = parse_qs(urlparse(self.path).query)
        since = float((q.get("since") or ["0"])[0] or 0)
        limit = int((q.get("limit") or ["0"])[0] or 0)
        items = _load_products()
        if self.auth_role != "admin":
            items = [p for p in items if p.get("user") == self.auth_user]
        if since:
            items = [p for p in items if p.get("time", 0) >= since]
        items.sort(key=lambda x: x.get("time", 0), reverse=True)
        total = len(items)
        if limit > 0:
            items = items[:limit]
        self._json_response({"videos": [_product_view(item) for item in items], "total": total})

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
        """Authenticate against SQLite and issue an opaque HttpOnly session cookie."""
        try:
            data = self._read_json_body()
            u = (data.get("username") or "").strip()
            p = data.get("password") or ""
            if AUTH_STORE.user_count() == 0:
                self._json_response({
                    "ok": False,
                    "error": "Auth database chưa được migrate. Chạy tools/migrate_auth.py trước.",
                }, 503)
                return
            remote_ip = self.client_address[0] if self.client_address else ""
            acc, retry_after = AUTH_STORE.authenticate(u, p, remote_ip)
            if not acc:
                headers = {"Retry-After": str(retry_after)} if retry_after else None
                self._json_response(
                    {"ok": False, "error": "Sai tài khoản hoặc mật khẩu"},
                    429 if retry_after else 401,
                    headers=headers,
                )
                return
            token, csrf, profile = AUTH_STORE.create_session(acc["username"])
            public_profile = _canonical_profile(profile)
            max_age = AUTH_STORE.absolute_ttl
            cookie_headers = [
                f"dulich_session={token}; Max-Age={max_age}; "
                f"{self._cookie_flags(http_only=True)}",
                f"dulich_csrf={csrf}; Max-Age={max_age}; "
                f"{self._cookie_flags(http_only=False)}",
            ]
            _audit(public_profile["username"], "login")
            self._json_response({
                "ok": True,
                **public_profile,
                "roster": _public_roster(),
                "csrf_token": csrf,
            }, headers={"Set-Cookie": cookie_headers})
        except Exception as e:
            self._json_response({"ok": False, "error": str(e)}, 500)

    def handle_session(self):
        csrf = self._csrf_cookie()
        if not AUTH_STORE.csrf_matches(self.auth_session, csrf):
            self._json_response({"error": "Phiên CSRF không hợp lệ; vui lòng đăng nhập lại."}, 401)
            return
        self._json_response({
            "ok": True,
            **_canonical_profile(self.auth_session["profile"]),
            "roster": _public_roster(),
            "csrf_token": csrf,
            "expires_at": self.auth_session["expires_at"],
        })

    def handle_logout(self):
        AUTH_STORE.revoke_session(self._session_token())
        _audit(self.auth_user, "logout")
        expired = [
            f"dulich_session=; Max-Age=0; {self._cookie_flags(http_only=True)}",
            f"dulich_csrf=; Max-Age=0; {self._cookie_flags(http_only=False)}",
        ]
        self._json_response(
            {"success": True},
            headers={"Set-Cookie": expired},
        )

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
                owner = self.auth_user if self.auth_role == "news" else "tintuc"
                add_draft(owner, scenes, "hook_news", "none", "fade", "pil", "", "ai")
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
        """Removed: server-side folder opening is unsafe and useless through the tunnel."""
        self._json_response({"error": "Endpoint đã bị vô hiệu hóa."}, 410)

    def handle_download_file(self):
        """Removed: use an authorized /media URL with ?download=1."""
        self._json_response({"error": "Endpoint đã bị vô hiệu hóa."}, 410)

    def handle_preview(self):
        print("[Server] /preview — Nhận request nghe thử...", file=sys.stderr)
        try:
            data = self._read_json_body()
            provider = data.get("provider", "mock")
            voice_id = data.get("voice_id", "")
            text = data.get("text", "Xin chào.")

            from tools.voice_generator import VoiceGenerator
            gen = VoiceGenerator(provider=provider)
            output_name = f"preview_{provider}_{uuid.uuid4().hex[:12]}"
            
            # Force speed to 1.0 for previews
            audio_path = gen.generate_voice(
                text=text,
                voice_id=voice_id,
                output_name=output_name,
                speed=1.0
            )
            
            self._json_response({
                "success": True,
                "url_path": _register_temp_media(self.auth_user, audio_path),
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
        # Never trust a browser-generated id for filesystem or queue identity.
        legacy_upload_id = f"legacy_{uuid.uuid4().hex}"
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

        # API keys are server/admin settings only. Never accept per-request keys from staff.

        try:
            script = json.loads(fields.get("script", "{}"))
        except Exception:
            script = {"hook": "", "body": "", "cta": ""}

        try:
            scenes_meta = json.loads(fields.get("scenes_meta", "[]"))
        except Exception:
            scenes_meta = []

        print(f"[Server] Upload: {legacy_upload_id}, {len(scenes_meta)} scene(s), transition={transition}", file=sys.stderr)

        # Save uploaded files to temp dir
        job_temp = UPLOAD_TEMP_DIR / legacy_upload_id
        job_temp.mkdir(parents=True, exist_ok=True)

        scene_uploads = []
        for scene in scenes_meta:
            sid = scene.get("scene_id", "")
            sid_file = _safe_identifier(sid, "scene")

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
                dest = job_temp / f"{sid_file}_{k}{ext}"
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
                concat_dest = str(job_temp / f"{sid_file}_concat.mp4")
                if _concat_scene_clips(saved_paths, concat_dest):
                    scene_uploads.append({"scene_id": sid, "file_path": concat_dest})
                    print(f"[Server]   ✓ {sid}: nối {len(saved_paths)} clip → {concat_dest}", file=sys.stderr)
                else:
                    # Concat failed → fall back to first clip
                    scene_uploads.append({"scene_id": sid, "file_path": saved_paths[0]})
                    print(f"[Server]   ⚠ {sid}: concat lỗi, dùng clip đầu", file=sys.stderr)

        # Legacy compatibility: enqueue just like the chunked API.  The request
        # no longer waits for FFmpeg and the server, not the client, creates id.
        try:
            payload = {
                "topic": fields.get("topic", "") or hook_title or "Video",
                "script": script,
                "scene_uploads": scene_uploads,
                "transition": transition,
                "voice_mode": voice_mode,
                "voice_id": voice_id,
                "creator_id": creator_id,
                "template_ratio": template_ratio,
                "hook_style": hook_style,
                "hook_text": hook_text,
                "hook_title": hook_title,
                "hook_subtitle": hook_subtitle,
                "video_type": video_type,
                "legacy_temp_dir": str(job_temp),
            }
            job, _ = PIPELINE_STORE.create_job(
                kind="personal_video",
                owner=self.auth_user,
                payload=payload,
                active_limit=MAX_ACTIVE_JOBS_PER_USER,
            )
            self._json_response({
                "success": True,
                "queued": True,
                "job_id": job["id"],
                "position": PIPELINE_STORE.queue_position(job["id"]),
            }, 202)
        except QueueLimitError as exc:
            shutil.rmtree(str(job_temp), ignore_errors=True)
            self._json_response({"success": False, "error": str(exc)}, 429)
        except Exception as exc:
            shutil.rmtree(str(job_temp), ignore_errors=True)
            self._json_response({"success": False, "error": _friendly_error(exc)}, 500)

    def handle_assemble_listreview(self):
        """Luồng nhân viên (list-review, mẫu nv1): intro + N quán (tên+điểm+VO+clip) + outro."""
        print("[Server] /assemble-listreview — nhận request...", file=sys.stderr)
        try:
            fields, files = parse_multipart(self)
        except Exception as e:
            self._json_response({"success": False, "error": f"Lỗi đọc request: {e}"}, 400)
            return

        legacy_upload_id = f"legacy_{uuid.uuid4().hex}"
        user = self.auth_user
        hook_style = fields.get("hook_style", "hook_red")
        voice_provider = fields.get("voice_mode", "gtts")
        voice_id = fields.get("voice_id", "")
        try:
            spec_in = json.loads(fields.get("spec", "{}"))
        except Exception:
            spec_in = {}

        job_temp = UPLOAD_TEMP_DIR / legacy_upload_id
        job_temp.mkdir(parents=True, exist_ok=True)

        def _save_clips(scene_id: str) -> list:
            def _idx(fn):
                tail = fn.rsplit("__", 1)[1] if "__" in fn else "0"
                return int(tail) if tail.isdigit() else 0
            names = sorted([fn for fn in files if fn == scene_id or fn.startswith(scene_id + "__")], key=_idx)
            out = []
            safe_scene_id = _safe_identifier(scene_id, "scene")
            for k, fn in enumerate(names):
                filename, file_bytes = files[fn]
                ext = Path(filename).suffix or ".mp4"
                dest = job_temp / f"{safe_scene_id}_{k}{ext}"
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
            "job_id": legacy_upload_id, "hook_style": hook_style,
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

        # Legacy compatibility: persist in the same SQLite queue as the new API.
        try:
            _topic = intro.get("title", "") or "List review"
            job, _ = PIPELINE_STORE.create_job(
                kind="listreview_video",
                owner=user,
                payload={
                    "spec": spec,
                    "topic": _topic,
                    "hook_style": hook_style,
                    "draft_id": fields.get("draft_id", ""),
                    "legacy_temp_dir": str(job_temp),
                },
                active_limit=MAX_ACTIVE_JOBS_PER_USER,
            )
            position = PIPELINE_STORE.queue_position(job["id"])
            print(f"[Server] /assemble-listreview → queue {job['id']} (vị trí {position})", file=sys.stderr)
            self._json_response({"success": True, "queued": True,
                                 "job_id": job["id"], "position": position}, 202)
        except QueueLimitError as e:
            shutil.rmtree(str(job_temp), ignore_errors=True)
            self._json_response({"success": False, "error": str(e)}, 429)
        except Exception as e:
            import traceback
            print(f"[Server] ❌ queue lỗi: {e}\n{traceback.format_exc()}", file=sys.stderr)
            shutil.rmtree(str(job_temp), ignore_errors=True)
            self._json_response({"success": False, "error": _friendly_error(e)}, 500)

    def handle_render_jobs(self):
        """Return render jobs allowed by the authenticated identity."""
        owner = None if self.auth_role == "admin" else self.auth_user
        jobs = PIPELINE_STORE.list_jobs(owner=owner, limit=50)
        self._json_response({
            "success": True,
            "jobs": [_job_client_view(job) for job in jobs],
            "queue_len": PIPELINE_STORE.queue_length(),
        })

    def handle_assemble_image(self):
        """POST /assemble-image {album, user} → chạy script CLI dựng album ảnh, lưu lại, trả list ảnh PNG."""
        try:
            body = self._read_json_body()
            album = (body.get("album") or "").strip()
            title_prompt = (body.get("title_prompt") or "").strip()
            allowed = {item["id"] for item in _albums_for(self.auth_user)}
            if album not in allowed:
                self._json_response(
                    {"success": False, "error": "Bạn không có quyền dùng mẫu album này."},
                    403,
                )
                return
            job, _ = PIPELINE_STORE.create_job(
                kind="album_image",
                owner=self.auth_user,
                payload={
                    "album": album,
                    "topic": f"Album {album}",
                    "title_prompt": title_prompt[:500],
                    "auto": False,
                },
                active_limit=MAX_ACTIVE_JOBS_PER_USER,
            )
            self._json_response({
                "success": True,
                "queued": True,
                "job_id": job["id"],
                "position": PIPELINE_STORE.queue_position(job["id"]),
            }, 202)
        except QueueLimitError as e:
            self._json_response({"success": False, "error": str(e)}, 429)
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
            user = self.auth_user
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
            owner = self.auth_user if self.auth_role == "news" else "tintuc"
            sc = generate_script_ai(f"tin tức Đà Lạt: {title}", employee=owner)
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
            add_draft(owner, scenes, "hook_news", "none", "fade", "pil", "",
                      f"news:{url}" if url else "news")
            self._json_response({"success": True, "title": sc.get("title", title)})
        except Exception as e:
            import traceback
            print(f"[Server] news-use lỗi: {e}\n{traceback.format_exc()}", file=sys.stderr)
            self._json_response({"success": False, "error": str(e)}, 500)

    def handle_ai_image_from_link(self):
        """POST /ai-image-from-link {user, url} — bài ảnh carousel TikTok mẫu →
        AI vẽ lại Y HỆT TỪNG ảnh (Nano Banana Pro), đúng số lượng ảnh trong link, watermark @dalatnow."""
        if not AI_IMAGE_FROM_LINK_ENABLED:
            self._json_response(
                {
                    "success": False,
                    "error": "Tính năng tạo lại ảnh bằng Gemini đang tạm dừng.",
                },
                503,
            )
            return
        try:
            b = self._read_json_body()
            user = self.auth_user
            url = (b.get("url") or "").strip()
            if "tiktok.com" not in url:
                self._json_response({"success": False, "error": "Dán link bài ẢNH TikTok"}, 400)
                return

            bucket = int(time.time() // 600)
            idem = "ai-image:" + hashlib.sha256(
                f"{user}:{url}:{bucket}".encode("utf-8")
            ).hexdigest()
            job, created = PIPELINE_STORE.create_job(
                kind="ai_image_from_link",
                owner=user,
                payload={"url": url, "topic": "Tạo lại ảnh TikTok"},
                idempotency_key=idem,
                active_limit=MAX_ACTIVE_JOBS_PER_USER,
            )
            self._json_response({
                "success": True,
                "queued": True,
                "created": created,
                "job_id": job["id"],
                "position": PIPELINE_STORE.queue_position(job["id"]),
            }, 202)
        except QueueLimitError as e:
            self._json_response({"success": False, "error": str(e)}, 429)
        except Exception as e:
            import traceback
            print(f"[Server] ai-image-from-link lỗi: {e}\n{traceback.format_exc()}", file=sys.stderr)
            self._json_response({"success": False, "error": _friendly_error(e)}, 500)

    def handle_albums_get(self):
        """Return album templates allowed for the authenticated account."""
        try:
            self._json_response({"success": True, "albums": _albums_for(self.auth_user)})
        except Exception as e:
            self._json_response({"success": False, "error": str(e)}, 500)

    def handle_album_library(self):
        """GET /album-library?user=&role= → album đã tạo (lọc theo user nếu không phải admin)."""
        try:
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            since = float((q.get("since") or ["0"])[0] or 0)
            limit = int((q.get("limit") or ["0"])[0] or 0)
            items = sorted(_load_albums(), key=lambda a: a.get("time", 0), reverse=True)
            if self.auth_role != "admin":
                items = [a for a in items if a.get("user") == self.auth_user]
            if since:
                items = [a for a in items if a.get("time", 0) >= since]
            total = len(items)
            if limit > 0:
                items = items[:limit]
            self._json_response({
                "success": True,
                "albums": [_album_view(item) for item in items],
                "total": total,
            })
        except Exception as e:
            self._json_response({"success": False, "error": str(e)}, 500)

    def handle_product_status(self):
        """Admin-only status change by opaque resource id."""
        try:
            b = self._read_json_body()
            kind = (b.get("kind") or "video").strip()
            resource_id = (b.get("id") or "").strip()
            status = (b.get("status") or "").strip()
            ki = int(b.get("zernio_ki") or 0)
            account_id = (b.get("account_id") or "").strip()
            if kind not in {"video", "album"} or not resource_id:
                self._json_response({"success": False, "error": "resource id không hợp lệ"}, 400)
                return
            if status not in ("pending", "posted", "failed", "cancelled"):
                self._json_response({"success": False, "error": "status không hợp lệ"}, 400)
                return
            # External publish is always a durable background job.  Repeated
            # clicks/tabs share one idempotency key and therefore one Zernio POST.
            if status == "posted":
                rec = _find_product(resource_id) if kind == "video" else _find_album(resource_id)
                if not rec:
                    self._json_response({"success": False, "error": "Không tìm thấy nội dung."}, 404)
                    return
                owner = (rec or {}).get("user", "")
                if _is_publish_user(owner):
                    idem = f"publish:{kind}:{resource_id}:{account_id or ki}"
                    provider_request_id = str(
                        uuid.uuid5(uuid.NAMESPACE_URL, f"dulich:{idem}")
                    )
                    job, created = PIPELINE_STORE.create_job(
                        kind=f"publish_{kind}",
                        owner=owner or self.auth_user,
                        payload={
                            "resource_id": resource_id,
                            "topic": (rec or {}).get("topic") or (rec or {}).get("label") or "Đăng bài",
                            "zernio_ki": ki,
                            "account_id": account_id,
                            "requested_by": self.auth_user,
                            "provider_request_id": provider_request_id,
                        },
                        idempotency_key=idem,
                        max_attempts=2,
                    )
                    if (
                        not created
                        and rec.get("zernio_post_id")
                        and rec.get("status") in {"publishing", "unknown", "failed"}
                    ):
                        reconciled = _reconcile_publish_resource(
                            kind,
                            resource_id,
                            job=job,
                        )
                        job = PIPELINE_STORE.get_job(job["id"]) or job
                        if reconciled.get("status") == "posted":
                            self._json_response(
                                {
                                    "success": True,
                                    "posted": True,
                                    "status": "posted",
                                    "job_id": job["id"],
                                    "reconciled": True,
                                }
                            )
                            return
                        if reconciled.get("status") == "publishing":
                            self._json_response(
                                {
                                    "success": True,
                                    "queued": False,
                                    "posted": None,
                                    "status": "publishing",
                                    "job_id": job["id"],
                                    "reconciled": True,
                                },
                                202,
                            )
                            return
                    if not created and job["status"] == "unknown":
                        self._json_response(
                            {
                                "success": False,
                                "status": "unknown",
                                "job_id": job["id"],
                                "error": (
                                    "Chưa xác định Zernio đã nhận bài hay chưa. "
                                    "Hãy kiểm tra tài khoản TikTok trước khi thử lại."
                                ),
                            },
                            409,
                        )
                        return
                    if not created and job["status"] == "failed":
                        retried = PIPELINE_STORE.retry_job(
                            job["id"],
                            self.auth_user,
                            is_admin=True,
                        )
                        if retried:
                            job = retried
                    if job["status"] == "done":
                        self._json_response({
                            "success": True,
                            "posted": rec.get("status") == "posted",
                            "status": rec.get("status", "publishing"),
                            "job_id": job["id"],
                        })
                        return
                    if kind == "video":
                        _set_product_status(resource_id, "publishing")
                    else:
                        _set_album_status(resource_id, "publishing")
                    _audit(
                        self.auth_user,
                        "queue_publish",
                        resource_id,
                        kind=kind,
                        job_id=job["id"],
                        created=created,
                    )
                    self._json_response({
                        "success": True,
                        "queued": True,
                        "posted": None,
                        "status": "publishing",
                        "job_id": job["id"],
                    }, 202)
                    return
            ok = (
                _set_album_status(resource_id, status)
                if kind == "album"
                else _set_product_status(resource_id, status)
            )
            if ok:
                _audit(self.auth_user, "set_status", resource_id, kind=kind, status=status)
            self._json_response({"success": ok})
        except Exception as e:
            self._json_response({"success": False, "error": str(e)}, 500)

    def handle_publish_reconcile(self):
        try:
            body = self._read_json_body()
            kind = str(body.get("kind") or "")
            resource_id = str(body.get("id") or "")
            if kind not in {"video", "album"} or not resource_id:
                self._json_response(
                    {"success": False, "error": "resource id không hợp lệ"},
                    400,
                )
                return
            result = _reconcile_publish_resource(kind, resource_id)
            status = 200 if result.get("success") else 409
            _audit(
                self.auth_user,
                "reconcile_publish",
                resource_id,
                kind=kind,
                provider_status=result.get("status"),
            )
            self._json_response(result, status)
        except Exception as exc:
            self._json_response({"success": False, "error": str(exc)}, 500)

    def handle_news_scrape(self):
        """POST /news-scrape {keyword, hashtags[]} → cào YouTube tin Đà Lạt (video+shorts), lưu pool."""
        try:
            b = self._read_json_body()
            kw = (b.get("keyword") or "").strip()
            hts = b.get("hashtags")
            from tools.news_youtube import scrape_news, save_pool, DEFAULT_KEYWORD
            with _HEAVY_LOCK:
                owner = self.auth_user if self.auth_role == "news" else "tintuc"
                res = scrape_news(
                    kw or DEFAULT_KEYWORD,
                    hts if isinstance(hts, list) else None,
                    api_key=_user_apify(owner),
                )
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
        """Return own drafts, or all drafts for an admin."""
        try:
            q = parse_qs(urlparse(self.path).query)
            only_unused = (q.get("only_unused", ["0"])[0] == "1")
            from tools.script_drafts import list_drafts
            items = list_drafts(
                None if self.auth_role == "admin" else self.auth_user,
                only_unused=only_unused,
            )
            self._json_response({"success": True, "drafts": items})
        except Exception as e:
            self._json_response({"success": False, "error": str(e), "drafts": []}, 500)

    def handle_script_draft_use(self):
        """POST /script-drafts-use {id} → đánh dấu đã dùng, trả về scenes để nạp vào editor."""
        try:
            b = self._read_json_body()
            did = (b.get("id") or "").strip()
            from tools.script_drafts import get_draft, mark_used
            existing = get_draft(did)
            if not existing or (
                self.auth_role != "admin" and existing.get("user") != self.auth_user
            ):
                self._json_response({"success": False, "error": "Không tìm thấy kịch bản."}, 404)
                return
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
            did = (b.get("id") or "").strip()
            from tools.script_drafts import delete_draft, get_draft
            existing = get_draft(did)
            if not existing or (
                self.auth_role != "admin" and existing.get("user") != self.auth_user
            ):
                self._json_response({"success": False, "error": "Không tìm thấy kịch bản."}, 404)
                return
            ok = delete_draft(did)
            if ok:
                _audit(self.auth_user, "delete_draft", did)
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
        """Delete one album by id; staff can only delete their own album."""
        try:
            body = self._read_json_body()
            resource_id = (body.get("id") or "").strip()
            record = _find_album(resource_id)
            if not record or (
                self.auth_role != "admin" and record.get("user") != self.auth_user
            ):
                self._json_response({"success": False, "error": "Không tìm thấy album."}, 404)
                return
            ok = _delete_album(resource_id)
            if ok:
                _audit(self.auth_user, "delete_album", resource_id)
            self._json_response({"success": ok})
        except Exception as e:
            self._json_response({"success": False, "error": str(e)}, 500)

    def handle_venues_scrape_all(self):
        """POST /venues-scrape-all → cào APIFY cho các quán có < 8 ảnh (chạy tuần tự)."""
        if not _user_apify(self.auth_user):
            self._json_response(
                {"success": False, "error": "Thiếu APIFY_KEY_VIETCHINH."},
                400,
            )
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
            requested = (q.get("employee", [""])[0] or "").strip().lower()
            employee = requested if self.auth_role == "admin" and requested else self.auth_user
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
            requested = (body.get("employee") or "").strip().lower()
            employee = requested if self.auth_role == "admin" and requested else self.auth_user
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
            requested = (q.get("employee", [""])[0] or "").strip()
            employee = requested if self.auth_role == "admin" and requested else self.auth_user
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
        """GET /user-keys → số key Zernio theo nhân viên. Không trả giá trị key."""
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
                          "zernio_count": len(zk)})
        self._json_response({"success": True, "items": items})

    def handle_user_keys_save(self):
        """POST /user-keys {user, zernio_keys?: [..]}. Ô ẩn (•) giữ key cũ theo index."""
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
            # Per-user Apify keys are retired; APIFY_KEY_VIETCHINH is the
            # single source of truth.
            rec.pop("apify_key", None)
            keys[uid] = rec
            _save_user_keys(keys)
            _audit(self.auth_user, "update_user_keys", uid)
            self._json_response({"success": True})
        except Exception as e:
            self._json_response({"success": False, "error": str(e)}, 500)

    def handle_zernio_accounts(self):
        """GET /zernio-accounts?user= → các tài khoản TikTok của nv (gộp qua các key Zernio).
        Trả [{ki, account_id, name}] để admin chọn account đăng."""
        try:
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            requested = (q.get("user", [""])[0] or "").strip()
            user = requested if self.auth_role == "admin" and requested else self.auth_user
            from tools import publisher
            keys = _user_zernio_keys(user)
            digest = hashlib.sha256("|".join(keys).encode("utf-8")).hexdigest()
            cache_key = f"{user}:{digest}"
            with _ZERNIO_ACCOUNTS_CACHE_LOCK:
                cached = _ZERNIO_ACCOUNTS_CACHE.get(cache_key)
            if cached and time.time() - cached[0] < 300:
                out = cached[1]
            else:
                out = []
                for ki, key in enumerate(keys):
                    for a in publisher.list_tiktok_accounts(key):
                        if a.get("id"):
                            out.append({"ki": ki, "account_id": a["id"], "name": a.get("name", "TikTok")})
                with _ZERNIO_ACCOUNTS_CACHE_LOCK:
                    _ZERNIO_ACCOUNTS_CACHE[cache_key] = (time.time(), out)
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
            _audit(self.auth_user, "update_settings", changed_keys=sorted(updates.keys()))
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
            if (v or {}).get("id") is not None and self.auth_role != "admin":
                self._json_response(
                    {"success": False, "error": "Chỉ admin được sửa địa điểm dùng chung."},
                    403,
                )
                return
            saved = venues_db.save_venue(v or {})
            self._json_response({"success": True, "venue": self._venue_view(saved)})
        except Exception as e:
            self._json_response({"success": False, "error": str(e)}, 500)

    def handle_venue_delete(self):
        try:
            from tools import venues_db
            vid = (self._read_json_body() or {}).get("id")
            ok = venues_db.delete_by_id(int(vid)) if vid is not None else False
            if ok:
                _audit(self.auth_user, "delete_venue", str(vid))
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
            current = next((v for v in venues_db.get_all() if v["id"] == vid), None)
            if not current or path not in (current.get("images") or []):
                self._json_response({"success": False, "error": "Không tìm thấy ảnh."}, 404)
                return
            venues_db.remove_image(vid, path)
            try:
                fp = _resolve_under(THUMB_DIR, Path(path).name)
                fp.unlink(missing_ok=True)
            except (OSError, ValueError):
                pass
            _audit(self.auth_user, "delete_venue_image", str(vid))
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
        try:
            fp = _resolve_under(Path(base_dir), name)
        except (OSError, ValueError):
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
                try:
                    fp = _resolve_under(ALBUM_DIR, Path(rel).name)
                    fp.unlink(missing_ok=True)
                except (OSError, ValueError):
                    pass
                _audit(self.auth_user, "delete_shared_image", str(iid))
            self._json_response({"success": True})
        except Exception as e:
            self._json_response({"success": False, "error": str(e)}, 500)

    def _serve_album(self, name: str):
        self._serve_image(ALBUM_DIR, name)

    def handle_album_zip(self):
        """Download a saved album as one mobile-friendly ZIP response."""
        resource_id = unquote(urlparse(self.path).path[len("/album-zip/"):])
        record = _find_album(resource_id)
        if not record or (
            self.auth_role != "admin" and record.get("user") != self.auth_user
        ):
            self._json_response({"success": False, "error": "Không tìm thấy album."}, 404)
            return
        try:
            import zipfile

            archive = tempfile.SpooledTemporaryFile(max_size=16 * 1024 * 1024)
            added = 0
            with zipfile.ZipFile(
                archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6
            ) as bundle:
                for index, image in enumerate(record.get("images") or []):
                    try:
                        source = _output_file_from_url(image.get("url", ""))
                    except (OSError, ValueError):
                        continue
                    if source.is_file():
                        name = Path(image.get("name") or source.name).name
                        bundle.write(source, arcname=f"{index + 1:02d}_{name}")
                        added += 1
            if not added:
                archive.close()
                self._json_response({"success": False, "error": "Album không có file ảnh."}, 404)
                return
            length = archive.tell()
            archive.seek(0)
            safe_name = f"album-{resource_id[:12]}.zip"
            self.send_response(200)
            self._cors_headers()
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Disposition", f'attachment; filename="{safe_name}"')
            self.send_header("Content-Length", str(length))
            self.send_header("Cache-Control", "private, no-store")
            self.send_header("Connection", "close")
            self.end_headers()
            while chunk := archive.read(64 * 1024):
                self.wfile.write(chunk)
            archive.close()
            self.close_connection = True
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True
        except Exception as exc:
            self._json_response({"success": False, "error": str(exc)}, 500)

    def handle_publish_to_dashboard(self):
        """Queue an idempotent Drive/Supabase publish job."""
        try:
            data = self._read_json_body()
            resource_id = (data.get("id") or "").strip()
            record = _find_product(resource_id)
            if not record:
                self._json_response({"success": False, "error": "Không tìm thấy video."}, 404)
                return
            job, created = PIPELINE_STORE.create_job(
                kind="publish_dashboard",
                owner=record.get("user") or self.auth_user,
                payload={
                    "resource_id": resource_id,
                    "topic": record.get("topic") or "Dashboard",
                    "script": data.get("script", {}),
                    "hook_text": data.get("hook_text", ""),
                    "video_type": data.get("video_type", "video"),
                    "requested_by": self.auth_user,
                },
                idempotency_key=f"dashboard:{resource_id}",
                max_attempts=2,
            )
            if not created and job["status"] == "failed":
                retried = PIPELINE_STORE.retry_job(
                    job["id"],
                    self.auth_user,
                    is_admin=True,
                )
                if retried:
                    job = retried
            self._json_response({
                "success": True,
                "queued": job["status"] != "done",
                "created": created,
                "job_id": job["id"],
                "status": job["status"],
                "result": job.get("result") if job["status"] == "done" else {},
            }, 200 if job["status"] == "done" else 202)
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(f"[Server] /publish-to-dashboard error: {e}\n{tb}", file=sys.stderr)
            self._json_response({"success": False, "error": str(e)}, 500)


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
        _start_maintenance_scheduler()
    else:
        print("[Server] Background jobs TẮT (DISABLE_BACKGROUND_JOBS).", file=sys.stderr)
    if os.getenv("DISABLE_JOB_WORKER", "").strip().lower() in {"1", "true", "yes"}:
        print("[Server] Embedded job worker TẮT; dùng worker.py riêng.", file=sys.stderr)
    else:
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


# ── Bảo trì disk độc lập với tính năng tự tạo nội dung ──────────────────────
def _maintenance_scheduler(stop_event: threading.Event | None = None):
    """Clean uploads hourly and archive old output once daily."""
    stop = stop_event or threading.Event()
    interval = _env_int("MAINTENANCE_INTERVAL_SECONDS", 3600, 60)
    archive_hour = min(23, _env_int("MAINTENANCE_HOUR", 4, 0))
    last_archive_day = ""
    while not stop.is_set():
        now = time.localtime()
        day = f"{now.tm_year:04d}-{now.tm_mon:02d}-{now.tm_mday:02d}"
        archive_output = now.tm_hour >= archive_hour and day != last_archive_day
        try:
            from tools.maintenance import run_maintenance

            result = run_maintenance(
                PIPELINE_STORE,
                upload_ttl_hours=_env_int("UPLOAD_SESSION_TTL_HOURS", 24),
                output_retention_days=_env_int("OUTPUT_RETENTION_DAYS", 5),
                archive_output=archive_output,
            )
            result["publish_reconcile"] = _reconcile_pending_publishes(
                _env_int("PUBLISH_RECONCILE_BATCH", 20)
            )
            PIPELINE_STORE.set_meta("maintenance_last_success", str(time.time()))
            if archive_output:
                last_archive_day = day
            if (
                result.get("uploads_removed")
                or result.get("job_results_removed")
                or result.get("output")
            ):
                print(f"[maintenance] {result}", file=sys.stderr)
        except Exception as exc:
            print(f"[maintenance] lỗi: {exc}", file=sys.stderr)
        stop.wait(interval)


def _start_maintenance_scheduler() -> threading.Thread:
    thread = threading.Thread(
        target=_maintenance_scheduler,
        daemon=True,
        name="disk-maintenance",
    )
    thread.start()
    print("[Server] Disk maintenance bật độc lập.", file=sys.stderr)
    return thread


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
                try:
                    PIPELINE_STORE.create_job(
                        kind="album_image",
                        owner=uid,
                        payload={
                            "album": pick["id"],
                            "topic": f"Album tự động {pick['id']}",
                            "title_prompt": "",
                            "auto": True,
                        },
                        priority=-1,
                    )
                    n_ok += 1
                except Exception as exc:
                    print(f"[daily] queue album lỗi {uid}: {exc}", file=sys.stderr)
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
