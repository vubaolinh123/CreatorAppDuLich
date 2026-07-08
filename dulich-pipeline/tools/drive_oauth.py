"""
drive_oauth.py — Tạo token.json cho Google Drive bằng OAuth (chạy 1 lần trên máy có browser).
Cần file client_secret.json (OAuth client loại "Desktop app") đặt cạnh server.py.

Usage: python -X utf8 tools/drive_oauth.py
→ mở browser, đăng nhập tài khoản Google chứa folder lưu trữ, bấm Cho phép.
→ token.json được lưu; copy token.json lên VPS là xong.
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
CLIENT_SECRET = ROOT / "client_secret.json"
TOKEN = ROOT / "token.json"
SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def main():
    if not CLIENT_SECRET.exists():
        print(f"[oauth] Thiếu {CLIENT_SECRET} — tải JSON của OAuth client (Desktop app) từ Google Cloud Console.")
        sys.exit(1)
    from google_auth_oauthlib.flow import InstalledAppFlow
    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")
    TOKEN.write_text(creds.to_json(), encoding="utf-8")
    print(f"[oauth] ✓ Đã lưu {TOKEN}")


if __name__ == "__main__":
    main()
