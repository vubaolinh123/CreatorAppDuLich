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
- Đặt key Service Account ngoài repository, ví dụ
  `/opt/CreatorAppDuLich/secrets/drive-service-account.json`, owner `dulich`,
  quyền `600`.
- Set `PUBLIC_BASE_URL=https://<domain>` (bắt buộc cho Zernio đăng TikTok).
- Service Account không có quota My Drive riêng. Tạo folder trong **Shared
  Drive**, thêm email Service Account với quyền Content manager, rồi đặt
  `GOOGLE_DRIVE_FOLDER_ID` và `GOOGLE_DRIVE_SHARED_DRIVE_ID`.
- Chạy `.venv/bin/python -X utf8 tools/check_drive.py`; chỉ deploy khi thấy
  `"ok": true` và `"can_add_children": true`.
- Giữ `GOOGLE_DRIVE_MAKE_PUBLIC=0` để archive/database backup không bị public.

## 3. systemd
```bash
sudo -u dulich .venv/bin/python -X utf8 tools/migrate_auth.py --source auto --dry-run
sudo -u dulich .venv/bin/python -X utf8 tools/migrate_auth.py --source auto
sudo -u dulich .venv/bin/python -X utf8 tools/migrate_pipeline.py
sudo -u dulich .venv/bin/python -X utf8 tools/backup_sqlite.py
cp deploy/dulich*.service deploy/dulich*.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now dulich dulich-worker dulich-backup.timer
curl --fail http://localhost:7788/health
systemctl status dulich dulich-worker --no-pager
```

`dulich` chỉ phục vụ HTTP/upload. `dulich-worker` xử lý hàng đợi SQLite bền vững
(render video, tạo ảnh, publish). Vì vậy restart web hoặc logout không làm mất job.
Mặc định chỉ có 1 heavy worker để tránh FFmpeg/Whisper tranh RAM/CPU; 2 network
worker dành cho publish. Chỉ tăng `HEAVY_JOB_WORKERS` sau khi đo RAM thực tế.
Mỗi job nằm trong process group riêng; thao tác hủy/timeout sẽ kill cả FFmpeg con.

Các file JSON cũ được backup vào `data/migration-backups/` trước khi import.
SQLite được snapshot nhất quán hằng ngày và upload Drive ở chế độ riêng tư.
Có thể chạy/kiểm tra thủ công bằng:

```bash
sudo -u dulich .venv/bin/python -X utf8 tools/migrate_pipeline.py --export
sudo -u dulich .venv/bin/python -X utf8 tools/backup_sqlite.py --upload-drive
systemctl status dulich-backup.timer --no-pager
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

Script deploy migrate auth trước khi checkout file người dùng đã scrub, kiểm tra
fast-forward, backup SQLite, cài unit, rồi yêu cầu cả service lẫn readiness
`/health` đạt. Nếu pip/migration/service/readiness lỗi, script tự trả code và
systemd unit về commit trước. Sau deploy phải thấy cả `dulich` và
`dulich-worker` ở trạng thái active.

## 7. Đặt lại mật khẩu dùng chung login name

Không ghi password vào `.env`, JSON trong repository hoặc command history.
Chạy tương tác trực tiếp trên VPS:

```bash
cd /opt/CreatorAppDuLich/dulich-pipeline
sudo -u dulich .venv/bin/python -X utf8 tools/reset_passwords.py \
  --interactive \
  --login-name appdalatnow \
  --accounts admin,tintuc,nv1,nv2,nv3,nv4,nv5 \
  --bootstrap-profiles data/users.json
```

Nhập và xác nhận từng password khi được hỏi. Lệnh đổi atomically cả alias/hash
và thu hồi mọi phiên đăng nhập cũ.

## Key cần có trước khi deploy
1. Key Service Account ngoài repo + Shared Drive đã cấp quyền +
   `GOOGLE_DRIVE_FOLDER_ID`.
2. `.env` đầy đủ (OPENROUTER, OPENAI, VBEE, APIFY, ZERNIO, PUBLIC_BASE_URL).
3. Domain trỏ Cloudflare (cho tunnel).
