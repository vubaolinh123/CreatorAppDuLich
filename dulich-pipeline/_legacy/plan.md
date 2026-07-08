# DuLichAppWeb — System Architecture

## 1. Tổng quan hệ thống

DuLichAppWeb là hệ thống tự động hóa sản xuất nội dung du lịch, gồm 2 phần chính:
- **Desktop App** (Tauri v2): Chạy local, chỉnh sửa video, ghép ảnh, voice clone, quản lý file
- **Dashboard Web** (Next.js): Review & duyệt nội dung, đăng lên mọi nền tảng

## 2. Tech Stack

### 2.1 Desktop App — Tauri v2 + React + TypeScript

| Layer | Công nghệ | Lý do |
|-------|-----------|-------|
| Framework | Tauri v2 | Single binary ~3MB, cross-platform, Rust backend |
| Frontend | React 18 + TypeScript + Vite | Nhanh, nhỏ, dễ build |
| Video Composition | Remotion (React) | Tạo video declarative từ React components, batch render 10-20 video/ngày |
| Video Processing | Rust `ffmpeg-next` qua Tauri commands | Full codec support, native performance, chạy qua spawn_blocking |
| State Management | Zustand + Jotai | Zustand cho UI state chung, Jotai cho timeline editor atoms |
| API Cache | RTK Query | Cache Google Drive/Sheets data, auto invalidation |
| Local DB | `tauri-plugin-sql` (SQLite) | Lưu project metadata, clip metadata, job queue, cached Sheets |
| Image Processing | Canvas API (preview) + Rust `image` crate (production) | Preview nhanh, output chất lượng cao |
| Photo Layout | fabric.js | Drag-drop collage layout cho album ảnh |
| File System | `@tauri-apps/plugin-fs` | Async, secure, scoped directory access |
| Google Auth | OAuth loopback + `tauri-plugin-secure-storage` | OS keychain lưu credentials |
| Google APIs | Rust `reqwest` (file ops) + JS client (metadata) | Rust reliability cho large files |

### 2.2 Dashboard Web — Next.js 14 + shadcn/ui

| Layer | Công nghệ | Lý do |
|-------|-----------|-------|
| Framework | Next.js 14 App Router | SSR, RSC, API routes tích hợp |
| UI Library | shadcn/ui + Tailwind CSS | Component chất lượng cao, customizable |
| Auth | NextAuth.js v5 (Credentials provider) | 5 creator accounts + 1 admin, JWT session |
| Styling | Tailwind CSS v3 | Utility-first, nhỏ bundle |
| Real-time | Polling (30s) + Google Sheets webhook | Desktop app cập nhật Sheets → Dashboard đọc |
| Social Publish | Ayrshare API | 13 nền tảng, multi-user, scheduling, analytics |
| Video Preview | Plyr player + thumbnail generation | Hiển thị video từ Drive |

### 2.3 Multi-Agent AI Pipeline — LangGraph

| Agent | Model | Vai trò |
|-------|-------|---------|
| Research | Claude Sonnet | Scrape trends, phân tích xu hướng |
| Script | Claude Sonnet | Viết kịch bản, seeding integration |
| Video Engine | GPT-4o / Local | FFmpeg assembly, voiceover mix, subtitle |
| Caption | Claude Haiku | Hook, caption, hashtag (high volume, cheap) |
| Image | Claude Sonnet | Template matching, album generation |

### 2.4 Voice Cloning

| Service | Dùng cho | Lý do |
|---------|----------|-------|
| **ElevenLabs** (Primary) | 5 creator voices, global content | Industry-leading quality, Instant Clone, well-documented API |
| **Vbee.ai** (Vietnamese) | Content 100% tiếng Việt | Native Vietnamese TTS, best local quality |
| **Cost**: ~$30-150/tháng cho 5 creators (Creator plan $22/tháng) |

### 2.5 Social Publishing

| Service | Nền tảng | Lý do |
|---------|----------|-------|
| **Ayrshare API** | YouTube, TikTok, Instagram, Facebook, LinkedIn, X, Pinterest, Threads,... | 13+ platforms, single API, multi-user, scheduling |

### 2.6 Photo Sourcing

| Service | Dùng cho |
|---------|----------|
| **Pexels API** / **Unsplash API** | Free stock photos cho seeding content |

## 3. Kiến trúc hệ thống

```
┌─────────────────────────────────────────────────────────────────┐
│                    Hệ thống Multi-Agent (LangGraph)              │
│                                                                 │
│  ┌──────────┐    ┌──────────┐                                   │
│  │ Research  │    │  Script  │  ← Chạy PARALLEL                  │
│  │ Agent     │───▶│ Agent    │                                   │
│  └──────────┘    └──────────┘                                   │
│       │                │                                         │
│       └───────┬────────┘                                         │
│               ▼                                                  │
│        ┌──────────────┐                                         │
│        │ Video Engine │ ← Remotion + FFmpeg + Voice             │
│        │   Agent      │                                         │
│        └──────┬───────┘                                         │
│               ▼                                                  │
│        ┌──────────────┐                                         │
│        │  Caption     │ ← Hook + Caption + Hashtag             │
│        │   Agent      │                                         │
│        └──────┬───────┘                                         │
│               ▼                                                  │
│        ┌──────────────┐                                         │
│        │   Image      │ ← Album generation                      │
│        │   Agent      │                                         │
│        └──────────────┘                                         │
└─────────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
   ┌──────────┐        ┌──────────┐        ┌──────────┐
   │  Google  │        │  Google  │        │  Local   │
   │  Drive   │        │  Sheets  │        │  SQLite  │
   │ (source  │        │ (sync &  │        │  (cache) │
   │  files)  │        │  tracking│        │          │
   └──────────┘        └──────────┘        └──────────┘
                                    │
                                    ▼
                         ┌──────────────────┐
                         │  Next.js         │
                         │  Dashboard       │
                         │  (Admin review)  │
                         └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │  Ayrshare API    │
                         │  (13+ platforms) │
                         └──────────────────┘
```

## 4. Luồng dữ liệu chính

### 4.1 Luồng Video Tin/Trend (Kênh Tin Tức)

```
1. Cron trigger (6:00 AM) → LangGraph pipeline
2. Research Agent: Scrape trends → extract top destinations
3. Script Agent: Viết kịch bản 60s (hook 0-5s, showcase 5-40s, CTA 40-60s)
4. Video Engine: Remotion render frames → FFmpeg assemble → add voiceover (ElevenLabs TTS) → add subtitles
5. Caption Agent: Tạo hook variants, caption, hashtags
6. Lưu video + metadata → Google Drive (theo folder brief) + Google Sheets
7. Admin mở Dashboard → xem preview → bấm "Đăng" → Ayrshare publish
```

### 4.2 Luồng Video Cá Nhân (5 Bạn)

```
1. Creator mở Desktop App → nhập nội dung/script
2. AI edit theo template riêng: Hook hiệu ứng → Subtitle + Voice Clone (ElevenLabs)
3. Render local → Lưu Drive + Sheets
4. Admin duyệt → Publish qua Ayrshare
```

### 4.3 Luồng Album Ảnh Seeding

```
1. AI chọn template (từ 10 format có sẵn hoặc template mới)
2. Template định nghĩa: vị trí ảnh, nội dung, khung layout
3. AI lấy ảnh từ kho (Pexels/Unsplash) hoặc Drive
4. Canvas API render preview → Rust image crate export
5. Lưu + Review + Publish
```

## 5. Cấu trúc thư mục

```
DuLichAppWeb/
├── dulich-desktop/               # Tauri Desktop App
│   ├── src-tauri/
│   │   ├── src/
│   │   │   ├── commands/         # Tauri invoke commands
│   │   │   │   ├── video.rs      # FFmpeg video operations
│   │   │   │   ├── image.rs      # Image processing
│   │   │   │   ├── drive.rs      # Google Drive API
│   │   │   │   ├── sheets.rs     # Google Sheets API
│   │   │   │   └── auth.rs       # OAuth flow
│   │   │   └── lib.rs
│   │   ├── Cargo.toml
│   │   └── tauri.conf.json
│   ├── src/
│   │   ├── components/           # React components
│   │   │   ├── editor/           # Video editor UI
│   │   │   ├── timeline/         # Timeline editor
│   │   │   ├── canvas/           # Photo canvas editor
│   │   │   └── preview/          # Video preview
│   │   ├── stores/               # Zustand stores
│   │   ├── hooks/                # Custom React hooks
│   │   ├── services/             # API clients
│   │   └── App.tsx
│   └── package.json
│
├── dulich-dashboard/             # Next.js Dashboard
│   ├── app/
│   │   ├── (auth)/
│   │   │   ├── login/page.tsx
│   │   │   └── layout.tsx
│   │   ├── dashboard/
│   │   │   ├── page.tsx          # Overview
│   │   │   ├── videos/
│   │   │   │   ├── page.tsx      # Video list
│   │   │   │   └── [id]/page.tsx # Video detail + preview
│   │   │   ├── albums/
│   │   │   │   └── page.tsx
│   │   │   ├── seeding/
│   │   │   │   └── page.tsx      # Restaurant/Hotel management
│   │   │   ├── templates/
│   │   │   │   └── page.tsx      # Template management
│   │   │   ├── creators/
│   │   │   │   └── page.tsx      # 5 creator accounts
│   │   │   └── settings/
│   │   │       └── page.tsx
│   │   ├── api/
│   │   │   ├── auth/[...nextauth]/route.ts
│   │   │   ├── publish/route.ts  # Ayrshare publish
│   │   │   └── sync/route.ts     # Google Sheets sync
│   │   └── layout.tsx
│   ├── components/
│   │   ├── ui/                   # shadcn/ui components
│   │   ├── video-player.tsx
│   │   ├── review-queue.tsx
│   │   └── publish-panel.tsx
│   └── package.json
│
├── dulich-pipeline/              # LangGraph Multi-Agent Pipeline
│   ├── agents/
│   │   ├── research_agent.py
│   │   ├── script_agent.py
│   │   ├── video_agent.py
│   │   ├── caption_agent.py
│   │   └── image_agent.py
│   ├── graph/
│   │   └── pipeline.py           # LangGraph StateGraph definition
│   ├── tools/
│   │   ├── playwright_scraper.py # Trend scraping
│   │   ├── drive_uploader.py     # Drive upload
│   │   ├── sheets_sync.py        # Sheets sync
│   │   ├── voice_generator.py    # ElevenLabs/Vbee.ai
│   │   └── video_renderer.py     # Remotion + FFmpeg
│   └── config.py
│
├── plan.md                       # Detailed implementation plan
└── README.md
```

## 6. Google Sheets Schema (Central Data Store)

| Sheet | Purpose | Key Columns |
|-------|---------|-------------|
| `Videos` | Track tất cả videos | name, creator, date, drive_link, status, drive_id, published_platforms |
| `Albums` | Track photo albums | name, template_id, date, creator, drive_link, status |
| `Creators` | 5 creator accounts | name, email, voice_id, template_id, drive_folder |
| `Seeding` | Quán/Khách sạn | name, type, category, location, notes |
| `Templates` | Video templates | name, format, creator, config_json |
| `Queue` | Review queue | content_id, type, submitted_by, date, status, review_notes |

## 7. Google Drive Structure

```
DuLichApp/
├── 01_Source/                   # Raw media từ creator
│   ├── [CreatorName]/
│   └── [BriefID]/
├── 02_Render/                   # Video đã render
├── 03_Albums/                   # Album ảnh đã tạo
├── 04_Seeding/                  # Hình ảnh seeding
└── 05_Templates/                # Template source files
```

## 8. Security & Auth

- Desktop App: OAuth 2.0 loopback → lưu refresh token trong OS keychain
- Dashboard: NextAuth.js JWT, role-based (admin vs creator)
- Google APIs: Scoped OAuth (Drive + Sheets only)
- API Keys: Stored in env vars, never committed
- Local files: Tauri plugin-fs với scoped access

## 9. Deployment

- Desktop App: `tauri build` → single .exe/.dmg/.AppImage, user download + install
- Dashboard: Vercel / self-hosted (Docker), domain + SSL
- Pipeline: Có thể chạy local (creator máy) hoặc server nhỏ (cloud VM)
- Database: SQLite local (desktop) + Google Sheets (sync hub)
