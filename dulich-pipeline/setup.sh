#!/usr/bin/env bash
# setup.sh — Cai dat 1 lan (macOS/Linux). Yeu cau: da cai Python 3.10+.
# Chay:  bash setup.sh
set -e
cd "$(dirname "$0")"

echo "== 1/5 Kiem tra Python =="
if ! command -v python3 >/dev/null 2>&1; then
  echo "Chua co Python3. macOS: 'brew install python'  hoac tai tai https://www.python.org/downloads/"
  exit 1
fi
python3 --version

echo "== 2/5 Tao moi truong .venv =="
[ -d .venv ] || python3 -m venv .venv

echo "== 3/5 Cai thu vien (vai phut) =="
./.venv/bin/python -m pip install --upgrade pip -q
./.venv/bin/python -m pip install -r requirements.txt

echo "== 4/5 Cai trinh duyet Chromium (Playwright, ~150MB) =="
./.venv/bin/python -m playwright install chromium

echo "== 5/5 FFmpeg + file .env =="
if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "   Chua co FFmpeg. Thu cai bang Homebrew..."
  if command -v brew >/dev/null 2>&1; then brew install ffmpeg; else
    echo "   Chua co Homebrew. Cai tai https://brew.sh roi chay: brew install ffmpeg"
  fi
else echo "   FFmpeg OK"; fi
[ -f .env ] || { cp .env.example .env; echo "   Da tao .env (chay FREE; dien API key sau neu can)."; }

echo ""
echo "XONG! Chay app:  bash start.sh"
