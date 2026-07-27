#!/usr/bin/env bash
# deploy.sh — cập nhật code + restart service trên VPS
set -e
cd /opt/CreatorAppDuLich
sudo systemctl stop dulich-worker 2>/dev/null || true
sudo systemctl stop dulich 2>/dev/null || true
git fetch origin
git checkout thanhthuduc99
git pull origin thanhthuduc99
cd dulich-pipeline
.venv/bin/pip install -r requirements.txt --quiet
sudo -u dulich .venv/bin/python -X utf8 tools/migrate_auth.py --source auto
sudo -u dulich .venv/bin/python -X utf8 tools/migrate_pipeline.py
sudo cp deploy/dulich.service deploy/dulich-worker.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl restart dulich dulich-worker
sleep 3
curl -s http://localhost:7788/health && echo " ✓ deploy OK"
