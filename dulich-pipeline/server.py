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
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler

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
        elif self.path == "/health":
            self._json_response({"status": "ok", "port": PORT})
        else:
            self._json_response({"error": f"Unknown path: {self.path}"}, 404)

    def do_GET(self):
        if self.path == "/health":
            self._json_response({"status": "ok", "port": PORT})
        else:
            self._json_response({"error": "Not found"}, 404)

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
                    voice_id="hn_female_lananh",
                    hook_style=hook_style,
                    hook_text=hook_text or script.get("hook", ""),
                    template_ratio=template_ratio,
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
            from agents.personal_video_agent import run_assemble_video
            print(f"[Server] Bắt đầu ghép video với FFmpeg...", file=sys.stderr)
            result = run_assemble_video(
                job_id=job_id,
                scene_uploads=scene_uploads,
                transition=transition,
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
