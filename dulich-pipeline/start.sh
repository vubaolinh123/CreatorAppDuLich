#!/usr/bin/env bash
# start.sh — Chay app (macOS/Linux). Sau khi da chay setup.sh 1 lan.
cd "$(dirname "$0")"
if [ ! -d .venv ]; then echo "Chua setup. Chay: bash setup.sh truoc."; exit 1; fi
export PYTHONUTF8=1 PYTHONIOENCODING=utf-8
./.venv/bin/python server.py &
SVPID=$!
sleep 3
( open http://localhost:7788 2>/dev/null || xdg-open http://localhost:7788 2>/dev/null ) || true
echo "App da mo: http://localhost:7788   (Ctrl+C de tat)"
wait $SVPID
