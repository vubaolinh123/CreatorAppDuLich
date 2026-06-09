# DuLichAppWeb - Setup Guide

## Tổng quan dự án

DuLichApp là hệ thống tự động hóa sản xuất nội dung du lịch (video + caption) gồm 3 phần:

| Package | Công nghệ | Mô tả |
|---------|-----------|-------|
| `dulich-dashboard` | Next.js 14 | Dashboard quản lý creators, videos, analytics |
| `dulich-desktop` | Tauri 2 + React | Desktop app - video editor, sheets sync, drive upload |
| `dulich-pipeline` | Python + LangGraph | Pipeline AI tạo research → script → voice → image → video |

---

## Yêu cầu hệ thống

- **Node.js** >= 18.18
- **npm** >= 9
- **Python** >= 3.10
- **Rust** >= 1.75 (cho Tauri)
- **FFmpeg** >= 6.0 (cho video rendering)
- **Google Chrome** (cho Playwright scraper)

---

## Bước 1: Clone & cài dependencies

```bash
# Install root workspace dependencies
npm install

# Install dashboard dependencies
cd dulich-dashboard && npm install && cd ..

# Install desktop dependencies
cd dulich-desktop && npm install && cd ..

# Install pipeline dependencies
cd dulich-pipeline && pip install -r requirements.txt && cd ..
```

---

## Bước 2: API Keys & Google Cloud Setup

### 2.1 Google Cloud - OAuth 2.0 (Sheets + Drive + Gmail)

Tạo project tại [Google Cloud Console](https://console.cloud.google.com/):

1. **Enable APIs**: Google Sheets API, Google Drive API, Gmail API
2. **OAuth 2.0 Desktop App**:
   - Vào **APIs & Services → Credentials → Create Credentials → OAuth client ID**
   - Chọn **Desktop app**
   - Lưu **Client ID** và **Client Secret**
3. **Download credentials**:
   - Click vào OAuth Client vừa tạo → **Download JSON**
   - Đổi tên thành `credentials.json`, đặt vào `dulich-pipeline/`
4. **Lần chạy đầu tiên**: pipeline sẽ mở browser để authorize, lưu `token.json`

```
GOOGLE_CLIENT_ID=xxxxxxxxxxxx.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=xxxxxxxxxxxx
GOOGLE_SHEET_ID=<ID của Google Sheet làm data hub>
GOOGLE_CREDENTIALS_PATH=credentials.json
```

### 2.2 Google Sheet - Data Hub

Tạo Google Sheet với các tab: `trends`, `scripts`, `images`, `voices`, `videos`
- Sheet ID là phần giữa `/d/` và `/edit` trong URL
- Điền vào `GOOGLE_SHEET_ID`

### 2.3 Anthropic API (Claude)

Đăng ký tại [console.anthropic.com](https://console.anthropic.com/):

```
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxx
```

### 2.4 ElevenLabs API (Voice generation)

Đăng ký tại [elevenlabs.io](https://elevenlabs.io/):

```
ELEVENLABS_API_KEY=xxxxxxxxxxxx
```

Tạo 5 voices trên ElevenLabs dashboard, lấy Voice ID của từng voice:

```
CREATOR1_VOICE_ID=xxxxxxxxxxxx
CREATOR2_VOICE_ID=xxxxxxxxxxxx
CREATOR3_VOICE_ID=xxxxxxxxxxxx
CREATOR4_VOICE_ID=xxxxxxxxxxxx
CREATOR5_VOICE_ID=xxxxxxxxxxxx
```

### 2.5 NextAuth (Dashboard)

Tạo secret key cho NextAuth:

```bash
# Tạo random secret
openssl rand -base64 32
```

```
NEXTAUTH_SECRET=<random 32-char string>
NEXTAUTH_URL=http://localhost:3000
```

### 2.6 Google OAuth cho Dashboard (NextAuth)

Trong Google Cloud Console, thêm **Authorized redirect URI**:
```
http://localhost:3000/api/auth/callback/google
```

---

## Bước 3: Tạo file .env

### 3.1 dulich-pipeline/.env

```bash
cd dulich-pipeline
cp .env.example .env
```

Điền các key đã lấy ở Bước 2 vào `.env`:

```
# Anthropic API (Claude)
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxx

# ElevenLabs Voice API
ELEVENLABS_API_KEY=xxxxxxxxxxxx

# Creator voice IDs (từ ElevenLabs dashboard)
CREATOR1_VOICE_ID=xxxxxxxxxxxx
CREATOR2_VOICE_ID=xxxxxxxxxxxx
CREATOR3_VOICE_ID=xxxxxxxxxxxx
CREATOR4_VOICE_ID=xxxxxxxxxxxx
CREATOR5_VOICE_ID=xxxxxxxxxxxx

# Google Sheets (central data hub)
GOOGLE_SHEET_ID=<your-sheet-id>
GOOGLE_CREDENTIALS_PATH=credentials.json
```

### 3.2 dulich-dashboard/.env

```bash
cd ../dulich-dashboard
cp .env.example .env
```

```
# NextAuth
NEXTAUTH_SECRET=<random-secret>
NEXTAUTH_URL=http://localhost:3000

# Google API (NextAuth login)
GOOGLE_CLIENT_ID=xxxxxxxxxxxx.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=xxxxxxxxxxxx

# ElevenLabs
ELEVENLABS_API_KEY=xxxxxxxxxxxx

# Ayrshare (social media publishing - optional)
AYRSHARE_API_KEY=your-ayrshare-key
```

### 3.3 dulich-desktop/.env

```bash
cd ../dulich-desktop
cp .env.example .env  # nếu có, hoặc tạo mới
```

```
# Tauri - không cần API keys đặc biệt
# Kết nối với dashboard qua:
DASHBOARD_URL=http://localhost:3000
```

---

## Bước 4: Tạo Google Sheet Data Hub

Tạo Google Sheet mới với các sheet (tab):

| Tab | Mục đích |
|-----|----------|
| `trends` | Lưu trending topics |
| `scripts` | Scripts AI-generated |
| `images` | Image prompts + results |
| `voices` | Voiceover metadata |
| `videos` | Video metadata + URLs |

Copy Sheet ID vào `GOOGLE_SHEET_ID` ở `.env`

---

## Bước 5: Chạy dự án

### 5.1 Chạy Dashboard (Next.js)

```bash
cd dulich-dashboard
npm run dev
# → http://localhost:3000
```

### 5.2 Chạy Desktop App (Tauri)

```bash
cd dulich-desktop
npm run tauri:dev
# → Mở cửa sổ desktop app
```

### 5.3 Chạy Pipeline (Python)

```bash
cd dulich-pipeline

# Chạy với topic mặc định
python main.py

# Chạy với topic cụ thể
python main.py --topic "Da Nang travel"

# Chạy với sheet ID cụ thể
python main.py --topic "Da Nang travel" --sheet-id <your-sheet-id>
```

---

## Bước 6: Playwright (scraper)

```bash
cd dulich-pipeline
playwright install chromium
```

---

## Kiểm tra nhanh

```bash
# 1. Dashboard hoạt động
→ Mở http://localhost:3000, đăng nhập Google

# 2. Desktop app kết nối được sheets
→ Mở desktop app, kiểm tra sync với Google Sheet

# 3. Pipeline chạy được
cd dulich-pipeline
python main.py --topic "test"
# → Kiểm tra output trong ./output/
```

---

## API Keys Checklist

| Key | Dịch vụ | Bắt buộc | Lấy tại |
|-----|---------|----------|---------|
| `ANTHROPIC_API_KEY` | Anthropic (Claude AI) | ✅ | console.anthropic.com |
| `ELEVENLABS_API_KEY` | ElevenLabs (Voice) | ✅ | elevenlabs.io |
| `GOOGLE_CLIENT_ID` | Google OAuth | ✅ | console.cloud.google.com |
| `GOOGLE_CLIENT_SECRET` | Google OAuth | ✅ | console.cloud.google.com |
| `GOOGLE_SHEET_ID` | Google Sheets | ✅ | sheets.google.com |
| `GOOGLE_CREDENTIALS_PATH` | Google Auth file | ✅ | Download từ GCP |
| `CREATOR1-5_VOICE_ID` | ElevenLabs Voices | ✅ | elevenlabs.io/voice-lab |
| `NEXTAUTH_SECRET` | NextAuth | ✅ | `openssl rand -base64 32` |
| `NEXTAUTH_URL` | NextAuth | ✅ | localhost:3000 |
| `AYRSHARE_API_KEY` | Social publishing | ❌ | ayrshare.com |

---

## Troubleshooting

- **Pipeline lỗi `ANTHROPIC_API_KEY not set`**: Kiểm tra file `dulich-pipeline/.env`
- **Google Sheets 401**: Chạy lại pipeline để re-authorize, xóa `token.json` cũ
- **Tauri build lỗi**: Cài Rust toolchain `rustup default stable`
- **Playwright lỗi**: Chạy `playwright install chromium`
- **FFmpeg not found**: Cài từ [ffmpeg.org](https://ffmpeg.org/download.html) hoặc `choco install ffmpeg` (Windows)
