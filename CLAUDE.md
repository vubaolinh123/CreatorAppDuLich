# CLAUDE.md — Đà Lạt Studio

## Phạm vi làm việc
- **Chỉ làm việc trong `dulich-pipeline/`.** Đây là app chính (Python + vanilla JS SPA).
- Các folder khác ở repo root (`dulich-dashboard/`, `dulich-desktop/`, `node_modules/`,
  `Myle115/`, `Khung Hook video*`, `source video/`, `source-anh-moi/`, `anh video du lich/`)
  **KHÔNG đụng tới** trừ khi được yêu cầu rõ.
- `dulich-pipeline/_legacy/` là code cũ đã gỡ khỏi app — chỉ tham khảo, không sửa/không wire lại.

## Tìm hiểu code
- Nếu repo có `.codegraph/`, hãy dùng `codegraph explore "<câu hỏi>"` trước khi grep hoặc đọc
  nhiều file để tìm hiểu code.
- `dulich-pipeline/.codegraph/` đã có → ưu tiên `codegraph explore` cho câu hỏi về code.

## Kiến trúc (dulich-pipeline)
- `server.py` — 1 server Python duy nhất, `ThreadingHTTPServer` port **7788** (stdlib, không framework).
- `web/index.html` — toàn bộ giao diện SPA (vanilla JS, 1 file).
- `tools/` — logic chính:
  - `list_review_render.py` — render video list-review (VO → phụ đề khớp giọng → ffmpeg;
    segment chạy song song, có faststart, hàng đợi render nền).
  - `voice_generator.py` — TTS: `chirp` (Google Chirp 3 HD, nhanh) · `vbee` (clone) ·
    `edge`/`gtts` (free).
  - `ai_image_gen.py` — tạo/tạo-lại ảnh bằng Gemini 2.5 Flash Image (Nano Banana thường, ~1k/ảnh;
    đổi `MODEL` sang `gemini-3-pro-image-preview` nếu cần chữ tiếng Việt chuẩn hơn, ~3.5k/ảnh);
    `tiktok_photos.py` — tải ảnh bài mẫu TikTok (tikwm → yt-dlp → APIFY).
  - `listreview_content.py` (`_TEMPLATES` per-nv), `script_import.py` (kịch bản từ text/link),
    `publisher.py` (đăng TikTok Zernio), `news_youtube.py` (cào tin APIFY),
    `storage_cleanup.py` (dọn output cũ → Drive), `drive_uploader.py`, `venues_db.py`.
- `data/` — `users.json`, `venues.json` (thư viện quán), `user_keys.json` (key Zernio/Apify per-nv);
  records: `output/products.json` (video), `output/album_products.json` (album).
- Album generators ở root pipeline: `demo_mye26.py` (le1), `generate_le2.py`, `generate_hien*`,
  `generate_muoi*`, `generate_vy1.py`, `generate_uyen*` — wired trong `IMAGE_ALBUMS` (server.py).

## Chạy / restart local
- venv: `dulich-pipeline/.venv/Scripts/python.exe` (Windows).
- Chạy: `python -X utf8 server.py` từ `dulich-pipeline/`. Mở `http://localhost:7788`.
- **Trước khi restart server: kiểm tra không có ffmpeg đang chạy** (đang render) rồi mới
  kill python + start lại bằng `Start-Process` (đừng cắt ngang job render).

## Deploy
- Chạy production tại **https://app.dalatnow.vn** (VPS, systemd service `dulich`, nginx reverse
  proxy → :7788). Server cũ dulich.contentta.vn đã gỡ.
- Git: **push lên branch `thanhthuduc99`** (không push thẳng main). Deploy = pull trên VPS +
  `systemctl restart dulich`.

## .env & bí mật (KHÔNG commit)
- `.env`, `credentials.json`, `token.json`, `client_secret.json`, `data/user_keys.json` — đã gitignore.
- Key đang dùng: `OPENROUTER_KEY`, `OPENAI_API_KEY`, `GEMINI_KEY` (Gemini + Google TTS Chirp),
  `VBEE_API_KEY`/`VBEE_APP_ID`, `APIFY_API_KEY`, `ZERNIO_KEY`, `PUBLIC_BASE_URL`,
  `GOOGLE_DRIVE_FOLDER_ID`, `RENDER_WORKERS`.

## Quy ước
- Trả lời tiếng Việt, tone casual, câu ngắn. Code/log tiếng Anh.
- Không tự cài package mới khi chưa hỏi. Không xóa file lạ — hỏi trước.
- Hỏi lại khi không chắc thay vì đoán. Làm tối giản, đúng yêu cầu, không thêm thắt.
