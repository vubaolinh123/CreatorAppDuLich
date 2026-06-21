# Hướng dẫn tích hợp Supabase + Đăng bài TikTok/Facebook

## 📋 Tóm tắt thay đổi

### 1. Dulich Pipeline (http://localhost:7788)

#### Files đã thay đổi:
- **`.env`** - Thêm Supabase credentials
- **`server.py`** - Thêm endpoint `/publish-to-dashboard` + login qua Supabase
- **`web/index.html`** - Thêm nút 📤 "Đăng lên Dashboard" trên mỗi video
- **`config.py`** - Thêm Supabase config
- **`tools/supabase_client.py`** - Client mới cho Supabase

#### Flow mới:
1. Tạo video → Render xong
2. Bấm nút 📤 trên video trong Library
3. Video metadata được gửi lên Supabase `content` table
4. Dashboard nhận và hiển thị video

---

### 2. Dulich Dashboard (http://localhost:3000)

#### Files mới:
- **`lib/supabase.ts`** - Supabase client + types
- **`app/api/publish-social/route.ts`** - API đăng bài TikTok/Facebook
- **`supabase-schema.sql`** - SQL schema cho Supabase

#### Files đã thay đổi:
- **`.env.local`** - Thêm Supabase + TikTok/Facebook credentials
- **`app/api/videos/route.ts`** - Dùng Supabase thay MongoDB
- **`app/api/videos/[id]/route.ts`** - Dùng Supabase
- **`app/dashboard/page.tsx`** - Dashboard mới với stats
- **`app/dashboard/videos/page.tsx`** - Video management với nút duyệt/đăng bài

---

## 🚀 Hướng dẫn cài đặt

### Bước 1: Tạo Supabase Tables

1. Vào Supabase Dashboard: https://supabase.com/dashboard
2. Chọn project của bạn
3. Vào **SQL Editor**
4. Copy và chạy nội dung file `dulich-dashboard/supabase-schema.sql`

### Bước 2: Cấu hình Environment Variables

#### Dulich Pipeline (`dulich-pipeline/.env`)
```env
SUPABASE_URL=https://dqvakhhuhzacqdrgryzr.supabase.co
SUPABASE_PUBLISHABLE_KEY=sb_publishable_UOy6gt1qtpH8d_ceZMklHg_e_GZmQtD

# TikTok (điền sau)
TIKTOK_ACCESS_TOKEN=

# Facebook (điền sau)
FACEBOOK_ACCESS_TOKEN=
FACEBOOK_PAGE_ID=
```

#### Dulich Dashboard (`dulich-dashboard/.env.local`)
```env
NEXT_PUBLIC_SUPABASE_URL=https://dqvakhhuhzacqdrgryzr.supabase.co
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=sb_publishable_UOy6gt1qtpH8d_ceZMklHg_e_GZmQtD

# TikTok (điền sau)
TIKTOK_ACCESS_TOKEN=

# Facebook (điền sau)
FACEBOOK_ACCESS_TOKEN=
FACEBOOK_PAGE_ID=
```

### Bước 3: Chạy ứng dụng

#### Terminal 1 - Dashboard
```bash
cd dulich-dashboard
npm run dev
```

#### Terminal 2 - Pipeline
```bash
cd dulich-pipeline
.venv\Scripts\python.exe server.py
```

---

## 📖 Hướng dẫn sử dụng

### Tạo và đăng video từ Pipeline:

1. Mở http://localhost:7788
2. Đăng nhập (tài khoản: `nv1`, mật khẩu: `123`)
3. Nhập chủ đề → Tạo kịch bản
4. Thả clip video vào các scene
5. Bấm **🎬 Tạo video**
6. Đợi render xong
7. Vào **📚 Thư viện**
8. Bấm nút **📤** trên video để đăng lên Dashboard

### Duyệt và đăng bài từ Dashboard:

1. Mở http://localhost:3000/dashboard/videos
2. Xem danh sách video từ Pipeline
3. Chọn video → Bấm **Duyệt** hoặc **Từ chối**
4. Sau khi duyệt, bấm nút **TikTok** hoặc **Facebook** để đăng bài

---

## 🔑 API Keys cần thiết

### Supabase (đã có)
- ✅ NEXT_PUBLIC_SUPABASE_URL
- ✅ NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY

### TikTok (cần tạo)
1. Vào https://developers.tiktok.com/
2. Tạo app → Lấy Access Token
3. Thêm vào `.env`

### Facebook (cần tạo)
1. Vào https://developers.facebook.com/
2. Tạo app → Lấy Page Access Token
3. Thêm vào `.env`

---

## 📊 Database Schema (Supabase)

### Table: users
```sql
id, username, password, role, name, hook_style, voice, created_at
```

### Table: content
```sql
id, user_id, content_type, status, title, topic, script, 
drive_url, local_path, thumbnail_url, metadata, job_id, 
hook_style, hook_text, created_at, updated_at
```

### Table: publish_logs
```sql
id, content_id, platform, platform_post_id, post_url, 
status, error_message, published_at
```

---

## ⚠️ Lưu ý

1. **Google Drive**: Chưa tích hợp tự động upload. Video hiện lưu local path.
2. **TikTok API**: Cần Submit App Review để dùng Content Posting API
3. **Facebook API**: Cần Page Access Token có quyền đăng bài
4. **Supabase Free Tier**: Giới hạn 500MB storage, 50K monthly active users
