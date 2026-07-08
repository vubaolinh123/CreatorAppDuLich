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
cp deploy/dulich.service /etc/systemd/system/
systemctl daemon-reload && systemctl enable --now dulich
curl http://localhost:7788/health
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
Sau đó set `PUBLIC_BASE_URL=https://app.<domain>` trong .env, restart dulich.

## 5. Dọn disk (đã tự động)
- Server chạy `tools/storage_cleanup.py` mỗi ngày (chung daily scheduler 6h): output cũ hơn 5 ngày → upload Drive `DuLichApp/archive/...` → xóa local. Upload fail thì giữ file.
- Chạy tay / kiểm tra: `.venv/bin/python -X utf8 tools/storage_cleanup.py --dry-run`
- Manifest file đã archive: `data/archive_manifest.json` (kèm link Drive).

## 6. Update code sau này
```bash
bash deploy/deploy.sh
```

## Key cần có trước khi deploy
1. `credentials.json` service account + share folder Drive cho email SA + `GOOGLE_DRIVE_FOLDER_ID`.
2. `.env` đầy đủ (OPENROUTER, OPENAI, VBEE, APIFY, ZERNIO, telegram_token, GROUP_ID).
3. Domain trỏ Cloudflare (cho tunnel).
