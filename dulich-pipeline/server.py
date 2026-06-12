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
from http.server import HTTPServer, BaseHTTPRequestHandler

# Configure UTF-8 encoding for Windows console to avoid print crashes
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

PORT = 7788
UPLOAD_TEMP_DIR = Path(__file__).parent / "output" / "temp_uploads"
UPLOAD_TEMP_DIR.mkdir(parents=True, exist_ok=True)


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
        elif self.path == "/preview":
            self.handle_preview()
        elif self.path == "/open-folder":
            self.handle_open_folder()
        elif self.path == "/download-file":
            self.handle_download_file()
        elif self.path == "/health":
            self._json_response({"status": "ok", "port": PORT})
        else:
            self._json_response({"error": f"Unknown path: {self.path}"}, 404)

    def do_GET(self):
        if self.path == "/health":
            self._json_response({"status": "ok", "port": PORT})
        elif self.path.startswith("/output/"):
            # Serve output files statically for preview/playback
            file_path = Path(__file__).parent / self.path.lstrip("/")
            if file_path.exists() and file_path.is_file():
                ext = file_path.suffix.lower()
                mime_map = {".mp4": "video/mp4", ".mov": "video/quicktime",
                            ".wav": "audio/wav", ".mp3": "audio/mpeg",
                            ".srt": "text/plain"}
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
            if sid in files:
                filename, file_bytes = files[sid]
                ext = Path(filename).suffix or ".mp4"
                dest = job_temp / f"{sid}{ext}"
                with open(str(dest), "wb") as f:
                    f.write(file_bytes)
                scene_uploads.append({"scene_id": sid, "file_path": str(dest)})
                size_mb = len(file_bytes) / 1024 / 1024
                print(f"[Server]   ✓ Saved {sid}: {filename} ({size_mb:.1f}MB) → {dest}", file=sys.stderr)
            else:
                # No file uploaded for this scene → placeholder
                scene_uploads.append({"scene_id": sid, "file_path": ""})
                print(f"[Server]   ⚠ {sid}: no file uploaded → placeholder", file=sys.stderr)

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

        # Run assembly
        try:
            # Force reload agents/tools modules so updates to video_renderer / hook_effects / personal_video_agent take effect without restarting server
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
            self._json_response({
                "success": True,
                "video_path": result.get("video_path", ""),
                "audio_path": result.get("audio_path", ""),
                "job_id": job_id,
            })
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(f"[Server] ❌ Lỗi assembly: {e}\n{tb}", file=sys.stderr)
            self._json_response({
                "success": False,
                "error": str(e),
                "traceback": tb,
            }, 500)
        finally:
            # Cleanup temp upload dir after delay
            def cleanup():
                import time
                time.sleep(60)
                shutil.rmtree(str(job_temp), ignore_errors=True)
            threading.Thread(target=cleanup, daemon=True).start()


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

    class ReusableHTTPServer(HTTPServer):
        allow_reuse_address = True

    print("""
+------------------------------------------------------+
|    DuLich Pipeline -- Local Assembly Server          |
|    Endpoint: POST http://localhost:7788/assemble     |
+------------------------------------------------------+
""", file=sys.stderr)

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


if __name__ == "__main__":
    main()
