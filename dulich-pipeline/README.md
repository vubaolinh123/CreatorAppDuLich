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
Job render/ảnh/publish được lưu trong SQLite WAL (`data/pipeline.sqlite3`) và
chạy bởi `worker.py`; production tách web và worker thành hai service.

Upload video dùng từng chunk 8 MB, có resume theo offset và kiểm tra bằng ffprobe.
Mỗi tài khoản có giới hạn riêng, nên một nhân viên không thể chiếm toàn bộ hàng
đợi của 5 nhân viên còn lại. Dữ liệu video/album/bản nháp được ghi transaction.
Mỗi job chạy trong process group riêng: hủy hoặc timeout sẽ dừng cả cây
FFmpeg/Whisper. Disk maintenance chạy độc lập theo giờ/ngày, không phụ thuộc
tính năng tự tạo nội dung. Publish Zernio lưu post ID, dùng request ID chống
trùng và đối soát trạng thái trước khi retry.

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
| `MAX_ACTIVE_JOBS_PER_USER` | Số job giữ chỗ/upload/chờ/chạy tối đa mỗi tài khoản (mặc định 4) |
| `MAX_GLOBAL_ACTIVE_JOBS` | Tổng job video đang hoạt động toàn hệ thống (mặc định 20) |
| `MAX_UPLOAD_JOB_MB` | Tổng dung lượng một phiên upload (mặc định 1536 MB) |
| `HEAVY_JOB_WORKERS` | Số worker render/ảnh; production mặc định 1 |
| `NETWORK_JOB_WORKERS` | Số worker publish; production mặc định 2 |
| `HEAVY_JOB_TIMEOUT_SECONDS` | Timeout toàn bộ cây render, mặc định 1800 giây |
| `OUTPUT_RETENTION_DAYS` | Số ngày giữ output local trước khi archive Drive |
| `ZERNIO_API_BASE_URL` | API Zernio dùng để đăng và đối soát trạng thái |

## Tài khoản

`data/users.json` chỉ còn metadata của admin, nv1-5
(Lê/Uyên/Hiền/Vy/Muối) và tintuc. Alias đăng nhập/hash mật khẩu nằm trong
`data/auth.sqlite3`; nhiều tài khoản nội bộ có thể dùng chung một login name,
password sẽ ánh xạ về đúng vai trò. Trường `album` là prefix mẫu album của từng
người; `publish: "tiktok"` bật đăng bài (đang gắn nv1).

## Deploy VPS

Xem `deploy/SETUP-VPS.md` (hai systemd service + Cloudflare Tunnel). Chạy
`tools/migrate_pipeline.py` trước lần bật worker đầu tiên. Disk nhỏ:
`tools/storage_cleanup.py` tự đẩy output cũ hơn 5 ngày lên Google Drive rồi mới
xóa local (chạy daily trong server).

## Ghi chú

- `_legacy/` — script/template cũ không còn wired vào app, giữ để tham khảo.
- Không commit `.env`, `credentials.json`.
