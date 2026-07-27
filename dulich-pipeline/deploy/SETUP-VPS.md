# Setup VPS — checklist (làm trong phiên SSH)

VPS 10GB disk → output tự dọn sau 5 ngày (backup Drive trước khi xóa).

## 1. Cài cơ bản
```bash
apt update && apt install -y git python3.11-venv ffmpeg curl
useradd -m dulich
git clone https://github.com/vubaolinh123/CreatorAppDuLich.git /opt/CreatorAppDuLich
cd /opt/CreatorAppDuLich && git checkout thanhthuduc99
cd dulich-pipeline
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
chown -R dulich:dulich /opt/CreatorAppDuLich
```
Lưu ý: KHÔNG cần node_modules / dulich-desktop / dulich-dashboard — chỉ dùng dulich-pipeline.

## 2. Cấu hình
- Copy `.env` từ máy local lên `/opt/CreatorAppDuLich/dulich-pipeline/.env` (scp).
- Copy `credentials.json` (Google Service Account) vào cùng folder.
- Set `PUBLIC_BASE_URL=https://<domain>` (bắt buộc cho Zernio đăng TikTok).
- `GOOGLE_DRIVE_FOLDER_ID`: ID folder Drive đã share cho email service account.

## 3. systemd
```bash
sudo -u dulich .venv/bin/python -X utf8 tools/migrate_auth.py --source auto --dry-run
sudo -u dulich .venv/bin/python -X utf8 tools/migrate_auth.py --source auto
sudo -u dulich .venv/bin/python -X utf8 tools/migrate_pipeline.py
cp deploy/dulich.service deploy/dulich-worker.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now dulich dulich-worker
curl http://localhost:7788/health
systemctl status dulich dulich-worker --no-pager
```

`dulich` chỉ phục vụ HTTP/upload. `dulich-worker` xử lý hàng đợi SQLite bền vững
(render video, tạo ảnh, publish). Vì vậy restart web hoặc logout không làm mất job.
Mặc định chỉ có 1 heavy worker để tránh FFmpeg/Whisper tranh RAM/CPU; 2 network
worker dành cho publish. Chỉ tăng `HEAVY_JOB_WORKERS` sau khi đo RAM thực tế.
Mỗi job nằm trong process group riêng; thao tác hủy/timeout sẽ kill cả FFmpeg con.

Các file JSON cũ được backup vào `data/migration-backups/` trước khi import.
Có thể kiểm tra/khôi phục dữ liệu ở dạng JSON bằng:

```bash
sudo -u dulich .venv/bin/python -X utf8 tools/migrate_pipeline.py --export
```

## 4. Cloudflare Tunnel (public URL, không cần mở port)
```bash
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o cf.deb && dpkg -i cf.deb
cloudflared tunnel login
cloudflared tunnel create dulich
cloudflared tunnel route dns dulich app.<domain>
# /etc/cloudflared/config.yml: tunnel + credentials-file + ingress → http://localhost:7788
cloudflared service install && systemctl enable --now cloudflared
```
Sau đó set `PUBLIC_BASE_URL=https://app.<domain>` trong .env, restart cả hai service:

```bash
systemctl restart dulich dulich-worker
```

## 5. Dọn disk (đã tự động)
- Scheduler bảo trì độc lập chạy mỗi giờ, kể cả khi `DAILY_AUTO_ENABLED=False`.
- Upload/job IPC hết hạn được dọn mỗi giờ. Sau `MAINTENANCE_HOUR`, output cũ hơn `OUTPUT_RETENTION_DAYS` → upload Drive `DuLichApp/archive/...` → chỉ xóa local khi upload thành công.
- Cùng scheduler sẽ đối soát các bài Zernio `publishing/unknown` đã có post ID.
- Chạy tay / kiểm tra: `.venv/bin/python -X utf8 tools/storage_cleanup.py --dry-run`
- Manifest file đã archive: `data/archive_manifest.json` (kèm link Drive).

## 6. Update code sau này
```bash
bash deploy/deploy.sh
```

Script deploy dừng worker trước, backup/import dữ liệu, cài lại hai unit rồi mới
khởi động. Migration auth chạy idempotent trước migration pipeline; nếu nguồn
legacy đã scrub nhưng database auth chưa đủ tài khoản, deploy sẽ dừng thay vì
bật một app không đăng nhập được. Sau deploy phải thấy cả `dulich` và
`dulich-worker` ở trạng thái active.

## Key cần có trước khi deploy
1. `credentials.json` service account + share folder Drive cho email SA + `GOOGLE_DRIVE_FOLDER_ID`.
2. `.env` đầy đủ (OPENROUTER, OPENAI, VBEE, APIFY, ZERNIO, PUBLIC_BASE_URL).
3. Domain trỏ Cloudflare (cho tunnel).
