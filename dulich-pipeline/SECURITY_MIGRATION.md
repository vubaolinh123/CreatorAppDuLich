# Triển khai auth/RBAC an toàn

Không `git pull` bản mới làm mất `password` legacy trước khi tạo
`data/auth.sqlite3`. Trên máy production, chép riêng hai file
`tools/auth_store.py` và `tools/migrate_auth.py` lên trước, rồi chạy:

```bash
python tools/migrate_auth.py --source auto --dry-run
python tools/migrate_auth.py --source auto
```

Sau khi thấy đủ tài khoản, cấu hình `.env`:

```dotenv
APP_ORIGIN=https://ten-mien-that
PUBLIC_BASE_URL=https://ten-mien-that
MEDIA_SIGNING_SECRET=<chuoi-ngau-nhien-it-nhat-32-ky-tu>
AUTH_COOKIE_SECURE=1
```

Sau đó mới cập nhật toàn bộ source và restart service. Smoke test theo thứ tự:

1. Đăng nhập từng tài khoản, refresh vẫn giữ phiên.
2. Nhân viên chỉ thấy video/album/draft của chính mình.
3. Admin thấy đủ dữ liệu và duyệt thử một mục.
4. Phát/tua video qua `/media/...`.
5. Đăng thử một mục Zernio để xác nhận signed URL.

Khi smoke test đạt:

```bash
python tools/migrate_auth.py --source json --replace --scrub-json
```

Chỉ dùng lệnh cuối nếu file JSON production vẫn còn password legacy. Nếu nguồn
legacy là Supabase, chạy thủ công `deploy/legacy_users_cleanup.sql` sau khi đã
xác nhận không ứng dụng nào khác còn dùng bảng đó.

`data/auth.sqlite3` và `MEDIA_SIGNING_SECRET` là dữ liệu production riêng,
không commit và không đặt trong thư mục được web server phục vụ.
