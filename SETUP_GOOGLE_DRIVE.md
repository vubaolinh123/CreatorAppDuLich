# Hướng dẫn Setup Google Drive

## 📋 Tổng quan

Google Drive được dùng để lưu video thay vì lưu local, giúp:
- Tiết kiệm ổ cứng
- Truy cập từ mọi nơi
- Dễ dàng chia sẻ và đăng bài

---

## 🔧 Cách 1: Service Account (Khuyên dùng)

### Bước 1: Tạo Service Account

1. Vào [Google Cloud Console](https://console.cloud.google.com/)
2. Tạo project mới (hoặc chọn project có sẵn)
3. Bật **Google Drive API**:
   - Vào **APIs & Services** → **Library**
   - Tìm "Google Drive API" → Bấm **Enable**

4. Tạo Service Account:
   - Vào **APIs & Services** → **Credentials**
   - Bấm **Create Credentials** → **Service Account**
   - Nhập tên (vd: `dulich-uploader`)
   - Bấm **Create and Continue**
   - Bấm **Done**

5. Tạo key cho Service Account:
   - Vào Service Account vừa tạo
   - Bấm tab **Keys** → **Add Key** → **Create new key**
   - Chọn **JSON** → Bấm **Create**
   - File JSON sẽ được tải về (vd: `dulich-xxxx.json`)

### Bước 2: Đặt file credentials

1. Copy file JSON vừa tải về vào folder `dulich-pipeline/`
2. Đổi tên thành `credentials.json` (hoặc giữ nguyên tên)
3. Cập nhật `.env`:

```env
GOOGLE_SERVICE_ACCOUNT_PATH=credentials.json
```

### Bước 3: Chia sẻ folder (Quan trọng!)

Vì Service Account chạy riêng, bạn cần chia sẻ folder Google Drive cho nó:

1. Mở Google Drive → Tạo folder "DuLichApp"
2. Bấm chuột phải → **Share**
3. Copy email của Service Account (trong file JSON có field `client_email`)
4. Paste email vào → Chọn **Editor** → Bấm **Share**

---

## 🔧 Cách 2: OAuth2 (Cá nhân)

### Bước 1: Tạo OAuth2 Credentials

1. Vào [Google Cloud Console](https://console.cloud.google.com/)
2. Vào **APIs & Services** → **Credentials**
3. Bấm **Create Credentials** → **OAuth client ID**
4. Chọn **Web application**
5. Nhập tên
6. Thêm **Authorized redirect URIs**: `http://localhost:7788/callback`
7. Bấm **Create**
8. Copy **Client ID** và **Client Secret**

### Bước 2: Cập nhật `.env`

```env
GOOGLE_CLIENT_ID=your-client-id
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=http://localhost:7788/callback
```

### Bước 3: Authorization

1. Mở trình duyệt, truy cập:
```
https://accounts.google.com/o/oauth2/auth?client_id=YOUR_CLIENT_ID&redirect_uri=http://localhost:7788/callback&scope=https://www.googleapis.com/auth/drive.file&response_type=code&access_type=offline
```

2. Đăng nhập Google → Đồng ý cấp quyền
3. Được redirect về `localhost:7788/callback?code=XXXX`
4. Code sẽ được exchange thành `token.json`

---

## ✅ Kiểm tra

Chạy script test:

```bash
cd dulich-pipeline
python -c "
from tools.drive_uploader import get_drive_uploader
uploader = get_drive_uploader()
service = uploader._get_service()
if service:
    print('✓ Google Drive connected!')
    # Test upload
    # result = uploader.upload_video('output/videos/test.mp4', 'test-job')
    # print(result)
else:
    print('✗ Cannot connect to Google Drive')
"
```

---

## 📁 Cấu trúc folder trên Google Drive

```
DuLichApp/
├── Videos/
│   ├── job_abc123/
│   │   └── video.mp4
│   └── job_def456/
│       └── video.mp4
└── Images/
    └── ...
```

---

## ⚠️ Lưu ý

1. **Service Account**: Miễn phí, chạy后台 được, nhưng cần chia sẻ folder
2. **OAuth2**: Cần user login, token hết hạn sau 1 giờ (có refresh token)
3. **Google Drive Free Tier**: 15GB miễn phí
4. **File size limit**: Google Drive API giới hạn 5TB/file

---

## 🔗 Links hữu ích

- [Google Cloud Console](https://console.cloud.google.com/)
- [Google Drive API Docs](https://developers.google.com/drive/api/v3/reference-files/create)
- [Service Account Guide](https://cloud.google.com/iam/docs/service-accounts)
