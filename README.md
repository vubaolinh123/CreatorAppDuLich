# DuLichApp — Hệ thống Tự động hóa Sản xuất Video Du lịch & Seeding Đa nền tảng

DuLichApp là giải pháp tự động hóa toàn diện quy trình sản xuất nội dung video ngắn du lịch (Shorts/Reels/TikTok) và album seeding ảnh 10 tỷ lệ phân giải khác nhau từ dữ liệu xu hướng thực tế. Hệ thống tích hợp sâu sắc giữa mô hình AI (Claude 3.5 Sonnet), giọng nói nhân tạo Tiếng Việt chất lượng cao (Vbee.ai), xử lý đồ họa nâng cao (FFmpeg, Pillow, Canva overlays) và quản lý phân phối đa kênh (Next.js Dashboard + Tauri Desktop App).

---

## 🏗️ Kiến trúc Hệ thống

Dự án được cấu trúc dưới dạng monorepo gồm 3 thành phần chính:

| Thư mục | Công nghệ | Mô tả chức năng |
|---------|-----------|-----------------|
| [`dulich-pipeline`](file:///d:/ProjectWeb/DuLichAppWeb/dulich-pipeline) | Python 3.10+, LangGraph, Pillow, FFmpeg | **AI Pipeline Engine**: Thu thập xu hướng, viết kịch bản tích hợp địa điểm seeding, tạo voice clone, căn chỉnh timing phụ đề SRT và render video hoàn chỉnh hoặc album ảnh seeding. |
| [`dulich-desktop`](file:///d:/ProjectWeb/DuLichAppWeb/dulich-desktop) | Tauri 2.0, React, TypeScript, Zustand | **Desktop Control Panel**: Phần mềm máy khách cho Creator. Cho phép tạo bài, review kịch bản, chỉnh hiệu ứng Hook mở đầu, phân tích video mẫu bằng AI, chọn thư mục video thô trực tiếp trên máy và stream log tiến trình thời gian thực. |
| [`dulich-dashboard`](file:///d:/ProjectWeb/DuLichAppWeb/dulich-dashboard) | Next.js 14, TailwindCSS, MongoDB Node Driver | **Web Management Dashboard**: Giao diện web trung tâm quản lý danh sách địa điểm seeding, xem xét/duyệt video đã tạo trên local, đếm số lượng video sản xuất của Creators, và xuất bản tự động đa nền tảng qua Ayrshare API. |

---

## 🛠️ Yêu cầu Cài đặt Phần mềm (Prerequisites từ A-Z)

Để chạy được toàn bộ dự án trên máy tính local (đặc biệt là môi trường **Windows**), bạn cần chuẩn bị và cài đặt các phần mềm nền tảng sau:

### 1. Nền tảng lập trình & runtime
* **Node.js (phiên bản >= 18.18)**: Dùng để chạy dev server cho Next.js Web và Vite React Desktop.
  * Tải từ: [nodejs.org](https://nodejs.org/en/download/) (Khuyên dùng bản LTS).
* **Python (phiên bản >= 3.10)**: Dùng để chạy engine AI và kết xuất file media.
  * Tải từ: [python.org/downloads](https://www.python.org/downloads/).
  * *Lưu ý*: Hãy tích chọn `"Add Python to PATH"` trong quá trình cài đặt.
* **Rust & Cargo (phiên bản stable >= 1.75)**: Yêu cầu bắt buộc để biên dịch nhân ứng dụng Desktop Tauri.
  * Tải từ: [rustup.rs](https://rustup.rs/).
* **C++ Build Tools**: Yêu cầu bởi Rust để biên dịch ứng dụng trên Windows.
  * Tải [Visual Studio Community](https://visualstudio.microsoft.com/vs/community/) -> Chọn gói cài đặt `"Desktop development with C++"`.

### 2. Tiện ích xử lý đa phương tiện & Cơ sở dữ liệu
* **MongoDB (Community Edition)**: Cơ sở dữ liệu lưu trữ cấu hình Creator, địa điểm Seeding và thông tin Videos/Albums.
  * Tải từ: [mongodb.com/try/download/community](https://www.mongodb.com/try/download/community).
  * Chạy MongoDB cục bộ mặc định tại cổng `27017` với tên cơ sở dữ liệu `dulichapp`.
* **FFmpeg (phiên bản >= 6.0)**: Công cụ kết xuất video, chèn nhạc và burn phụ đề.
  * Tải bản build Windows tại: [ffmpeg.org](https://ffmpeg.org/download.html) hoặc cài qua Chocolatey: `choco install ffmpeg`.
  * *Quan trọng*: Thư mục chứa file `ffmpeg.exe` phải được thêm vào cấu hình biến môi trường `PATH` của Windows.

---

## 🚀 Hướng dẫn Cài đặt Dự án (Setup từ A-Z)

### Bước 1: Khởi động MongoDB Local
Hãy đảm bảo dịch vụ MongoDB đang chạy trên máy tính của bạn:
```bash
# Kiểm tra dịch vụ MongoDB (trên Windows run Service hoặc CMD Admin)
net start MongoDB
```

### Bước 2: Cài đặt Dependencies cho Workspace
Mở Command Prompt / Terminal tại thư mục gốc dự án (`DuLichAppWeb`) và thực thi:
```bash
# 1. Cài đặt các gói phụ trợ tại thư mục gốc
npm install

# 2. Cài đặt thư viện cho Next.js Web Dashboard
cd dulich-dashboard && npm install && cd ..

# 3. Cài đặt thư viện cho Desktop App
cd dulich-desktop && npm install && cd ..

# 4. Tạo Virtual Environment và cài thư viện Python Pipeline
cd dulich-pipeline
python -m venv venv
# Kích hoạt ảo hóa (Windows):
venv\Scripts\activate
# Cài đặt thư viện:
pip install -r requirements.txt
# Cài đặt trình duyệt Playwright để crawl tin tức:
playwright install chromium
cd ..
```

---

## ⚙️ Cấu hình Biến Môi trường (.env)

Tạo và cấu hình các file `.env` ở các thư mục con tương ứng (tham khảo cấu trúc từ các file `.env.example` đi kèm):

### 1. Cấu hình AI Pipeline Engine: [`dulich-pipeline/.env`](file:///d:/ProjectWeb/DuLichAppWeb/dulich-pipeline/.env)
```env
# API Key của Anthropic (Claude AI - Bắt buộc cho Full Mode)
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxx

# Giọng nói nhân tạo Vbee.ai (Bắt buộc cho tiếng Việt TTS thật)
VBEE_API_KEY=your-vbee-api-key-here

# ElevenLabs API Key (Dùng làm tùy chọn secondary)
ELEVENLABS_API_KEY=your-elevenlabs-key

# Kết nối cơ sở dữ liệu local
MONGO_URI=mongodb://localhost:27017
MONGO_DB_NAME=dulichapp

# Đồng bộ với Dashboard
DASHBOARD_URL=http://localhost:3000
```

### 2. Cấu hình Web Dashboard: [`dulich-dashboard/.env.local`](file:///d:/ProjectWeb/DuLichAppWeb/dulich-dashboard/.env.local)
```env
# NextAuth
NEXTAUTH_SECRET=dulichapp-secret-key-change-in-production
NEXTAUTH_URL=http://localhost:3000

# API Keys
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxx
VBEE_API_KEY=your-vbee-api-key-here

# Ayrshare (Đăng bài MXH tự động - Để trống nếu dùng Mock mode)
AYRSHARE_API_KEY=your-ayrshare-key

# MongoDB local
MONGO_URI=mongodb://localhost:27017
MONGO_DB_NAME=dulichapp
```

---

## 💻 Hướng dẫn Vận hành & Phát triển

### 1. Chạy Web Dashboard
Web Dashboard dùng để quản lý Seeding và kiểm duyệt video/album từ xa.
```bash
cd dulich-dashboard
npm run dev
# Mở trình duyệt truy cập: http://localhost:3000
# Đăng nhập bằng tài khoản: admin@dulichapp.com / admin123
```

### 2. Chạy Desktop Client (Tauri + React)
Dành cho người tạo nội dung vận hành tại máy local:
```bash
cd dulich-desktop
npm run tauri:dev
# Tauri sẽ mở cửa sổ ứng dụng Desktop DuLichApp trực quan.
```

### 3. Chạy thử nghiệm Pipeline qua CLI (Python)
Bạn có thể chạy độc lập công cụ Python để sản xuất nội dung nhanh chóng:
```bash
cd dulich-pipeline
venv\Scripts\activate

# Tạo video cá nhân cho Creator Lan Anh bằng chế độ Mock (Không cần API Keys, không tốn chi phí)
python main.py --topic "Khám phá Hội An" --creator lan_anh --provider mock

# Tạo album ảnh seeding 10 tỷ lệ ảnh Canva frames
python main.py --action album --topic "Resort Phú Quốc" --title "Kỳ nghỉ hè tuyệt vời" --creator lan_anh
```

---

## 🧪 Các tính năng cao cấp đã được tích hợp
* **📁 Hộp thoại chọn thư mục/tệp tin**: Studio trên App Desktop cho phép bấm chọn trực tiếp thư mục video thô local qua File Explorer thay vì gõ tay.
* **📂 Mở thư mục chứa kết quả**: Phần kiểm tra File xuất hiển thị icon folder `📂`. Khi bấm vào sẽ tự động kích hoạt Windows Explorer mở đúng thư mục và tự động bôi đen (highlight) tệp tin Video hoặc Audio vừa kết xuất.
* **⚡ Hybrid Mock Mode**: Toàn bộ hệ thống đều hỗ trợ chế độ Mock từ API đăng bài MXH, viết kịch bản, sinh giọng nói silent, dựng video đen tượng trưng giúp lập trình viên hoặc người dùng test offline trơn tru từ đầu đến cuối mà không lo phát sinh chi phí hoặc lỗi kết nối.
