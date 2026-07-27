# Đà Lạt Studio — dulich-pipeline

Web app nội bộ cho team làm video/ảnh du lịch Đà Lạt. 1 server Python duy nhất (stdlib, không framework) + SPA vanilla JS.

## Chạy

```bash
# Windows
.\setup.ps1     # lần đầu: tạo .venv + cài requirements
.\start.ps1     # chạy server + mở http://localhost:7788

# Mac/Linux
./setup.sh && ./start.sh
```

Server: `server.py` (ThreadingHTTPServer, port 7788). UI: `web/index.html`.

## Tính năng

- **Video list review**: upload source → AI viết kịch bản → voice (Vbee clone / Edge free) → phụ đề khớp voice (Whisper đọc audio, tách câu theo nghĩa bằng AI) → render ffmpeg.
- **Ảnh (10 mẫu album)**: mỗi nhân viên có mẫu riêng (le1/2, hien1/2, muoi1/2, vy1/2, uyen1/2). Nội dung + ảnh nền + title đều random từ thư viện địa điểm; title/hook do AI (OpenRouter DeepSeek) viết lại mỗi lần, có ô prompt gợi ý riêng.
- **Thư viện địa điểm**: `data/venues.json` + ảnh `data/thumbs/` (path tương đối, chạy được cả Mac).
- **Duyệt bài**: admin duyệt video/album trong app; nv1 duyệt là đăng TikTok qua Zernio.
- **Tin tức**: cào YouTube (APIFY) theo từ khóa/hashtag Đà Lạt, chỉ tin 24h, 3 mốc giờ/ngày.
- **Admin**: KPI ngày (5 video + 5 ảnh/nv, tin tức 10), duyệt bài, trạng thái đã đăng/đăng lỗi/chưa đăng/hủy.

## Cấu hình

Copy `.env.example` → `.env` rồi điền key (hoặc nhập trong trang Cài đặt của admin — tự ghi vào `.env`). Không có key vẫn chạy được với giọng free + nội dung mẫu. Key chính:

| Key | Dùng cho |
|---|---|
| `OPENROUTER_KEY` | AI viết kịch bản + title album |
| `OPENAI_API_KEY` | Whisper — phụ đề khớp voice |
| `VBEE_API_KEY` + `VBEE_APP_ID` | Giọng đọc clone tiếng Việt |
| `APIFY_API_KEY` | Cào tin YouTube |
| `ZERNIO_KEY` | Đăng TikTok |
| `PUBLIC_BASE_URL` | URL công khai (bắt buộc khi deploy để Zernio tải được video) |

## Tài khoản

`data/users.json` — admin, nv1-5 (Lê/Uyên/Hiền/Vy/Muối), tintuc. Trường `album` là prefix mẫu album của từng người; `publish: "tiktok"` bật đăng bài (đang gắn nv1).

## Deploy VPS

Xem `deploy/SETUP-VPS.md` (systemd + Cloudflare Tunnel). Disk nhỏ: `tools/storage_cleanup.py` tự đẩy output cũ hơn 5 ngày lên Google Drive rồi mới xóa local (chạy daily trong server).

## Ghi chú

- `_legacy/` — script/template cũ không còn wired vào app, giữ để tham khảo.
- Không commit `.env`, `credentials.json`.
