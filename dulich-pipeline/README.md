# App tạo video du lịch Đà Lạt

Tool tạo video review/tin tức Đà Lạt theo phong cách từng kênh (nv1–nv5 + tin tức).
Chạy local trên máy, mở bằng trình duyệt tại `http://localhost:7788`.

> **Chạy FREE 100%** — không cần API key nào. Dùng giọng đọc Google (gTTS) + FFmpeg + Chromium.
> Các key trả phí (AI viết script, quét tin tức, giọng xịn, phần ảnh) đều **tùy chọn**, điền sau vào `.env`.

---

## 1. Cài đặt (làm 1 lần)

**Cần có trước:** [Python 3.10+](https://www.python.org/downloads/) (khi cài nhớ tick **"Add Python to PATH"**).
FFmpeg script sẽ tự lo; nếu không được sẽ có hướng dẫn tải.

### Tải source về máy
Repo **private** → chọn 1 trong 3 cách:
- **GitHub Desktop** (dễ nhất cho người không rành): cài [desktop.github.com](https://desktop.github.com), đăng nhập, File → Clone repository → chọn repo.
- **Tải ZIP**: vào trang repo → nút `Code` → `Download ZIP` → giải nén.
- **Dòng lệnh** (nếu có git): `git clone https://github.com/<chu-repo>/<ten-repo>.git`

### Chạy script cài
Mở thư mục `dulich-pipeline` rồi:

- **Windows:** chuột phải `setup.ps1` → **Run with PowerShell**
  (hoặc mở PowerShell trong thư mục, gõ `./setup.ps1`)
- **macOS:** mở Terminal trong thư mục, gõ `bash setup.sh`

Script sẽ tự: tạo môi trường, cài thư viện, tải Chromium, kiểm FFmpeg, tạo `.env`.
Lần đầu mất ~5–15 phút (tải Chromium ~150MB).

---

## 2. Chạy app

- **Windows:** `./start.ps1` (hoặc double-click `start_app.bat`)
- **macOS:** `bash start.sh`

Trình duyệt tự mở `http://localhost:7788`. Đóng cửa sổ server là tắt app.

### Đăng nhập

| Tài khoản | Mật khẩu | Vai trò |
|-----------|----------|---------|
| `admin` | `admin123` | Quản lý (xem thống kê, tất cả video) |
| `nv1`…`nv5` | `123` | Nhân viên (mỗi người 1 phong cách kênh) |
| `tintuc` | `123` | Kênh tin tức |

Vào nhanh bằng link: `http://localhost:7788/#nv2`, `/#nv3`, `/#tintuc`, `/#admin`…
Đổi mật khẩu trong `data/users.json`.

---

## 3. Bật tính năng trả phí (tùy chọn)

Mở file `.env`, điền key tương ứng rồi khởi động lại app:

| Key | Bật cái gì | Thiếu thì sao |
|-----|------------|----------------|
| `OPENROUTER_KEY` | AI tự viết kịch bản nv1 | Dùng nội dung mẫu/clone |
| `APIFY_API_KEY` | Quét TikTok/FB cho tin tức | Tin tức tự động không chạy |
| `VBEE_API_KEY` / `ELEVENLABS_API_KEY` | Giọng đọc xịn hơn | Tự fallback gTTS/Edge (free) |
| `MONGO_URI` | Lưu DB | Tự fallback file `output/mock_db.json` |

Muốn cài thêm thư viện cho mấy tính năng này: `pip install -r requirements-optional.txt`.

> 🖼 **Phần Ảnh** đang phát triển — đã có nút "Ảnh (sắp ra mắt)" trong app, sẽ ráp vào sau.

---

## Gặp lỗi thường gặp
- **"python không phải lệnh"** → chưa cài Python hoặc chưa tick Add to PATH. Cài lại.
- **"ffmpeg not found"** khi render → cài FFmpeg (script có in hướng dẫn) rồi mở lại cửa sổ.
- **Port 7788 bận** → tắt app cũ đang chạy rồi mở lại.

---

## Album Template Pipeline

Hệ thống tạo ảnh carousel tự động từ database địa điểm Đà Lạt. Mỗi **template** gồm 2 file:

| File | Mô tả |
|------|-------|
| `tools/{name}_renderer.py` | Vẽ từng slide bằng Pillow — fonts, layout, màu |
| `generate_{name}.py` | Pick venues từ DB, gọi renderer, lưu PNG |

### Chạy một template

```bash
python -X utf8 generate_{name}.py [--seed N] [--out "output/albums/ten-folder"]
```

Bỏ `--seed` để pick venues ngẫu nhiên mỗi lần. Thêm `--seed 42` để reproduce cùng kết quả.

### Templates hiện có

| Template | Generator | Mô tả | Slides |
|----------|-----------|-------|--------|
| uyen1tip | `generate_uyen1tip.py` | Infographic "Travel Tips" — 5 mẹo du lịch + venue list | 7 |
| uyen2    | `generate_uyen2.py`    | Review diary — 3 quán ăn personal review | 5 |

### Shared utilities (`tools/render_utils.py`)

- `load_bg(path, W, H)` — load + crop/scale ảnh thành canvas 1080×1390
- `load_thumb(path, size)` — thumbnail
- `rounded_thumb(thumb, radius)` — bo góc ảnh
- `save_slide(canvas, layer, out_path)` — composite + lưu PNG
- `draw_pin_icon(draw, x, y, size, color)` — icon map pin
- `beviet_bold(size)` / `load_font(name, size)` — fonts

### Venue database (`data/venues.json`)

54 địa điểm Đà Lạt: 28 quán ăn, 21 khách sạn, 1 quán cà phê, 4 tham quan.

Thêm địa điểm mới:
```bash
python tools/venues_db.py add
```

### Thêm template mới

**Quy trình 3 bước:** phân tích mẫu → implement Python → tạo demo

1. Chuẩn bị folder ảnh mẫu (các slide PNG/JPG)
2. Invoke skill `/tao-album-template` trong Claude Code — skill sẽ tự phân tích, viết code, chạy demo, iterate cho đến khi bạn duyệt
3. Commit 2 files mới: `tools/{name}_renderer.py` + `generate_{name}.py`

**Tự implement thủ công:**

```
tools/{name}_renderer.py   — functions: render_cover(), render_{type}()
generate_{name}.py         — VenuePicker + gọi renderer + save slides
```

Convention:
- Canvas: 1080×1390px
- Cover: full-bleed photo, không text, pick_one(co_nguoi="có")
- Output file names: `{name}_00_cover.png`, `{name}_01_intro.png`...
- Background mặc định: ảnh thật không overlay — `load_bg()` trực tiếp
