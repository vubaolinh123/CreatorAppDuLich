#!/usr/bin/env bash
# deploy.sh — cập nhật code + restart service trên VPS
set -e
cd /opt/CreatorAppDuLich
git fetch origin
git checkout thanhthuduc99
git pull origin thanhthuduc99
cd dulich-pipeline
.venv/bin/pip install -r requirements.txt --quiet
sudo systemctl restart dulich
sleep 3
curl -s http://localhost:7788/health && echo " ✓ deploy OK"
