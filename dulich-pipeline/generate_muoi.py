"""
generate_muoi.py — Generate Muối-style album: 6 slides.
Usage: python -X utf8 generate_muoi.py [--seed N] [--out path]

Slides:
  00_cover   — photo + yellow uppercase title
  01_hotel   — tip: book phòng trước + hotels + transport
  02_checkin — tip: đừng tin ảnh mạng + checkin spots
  03_food    — tip: tránh hàng chặt chém + quán ăn
  04_cafe    — tip: chọn cafe + quán cà phê
  05_play    — tip: hoạt động + tham quan
"""
from __future__ import annotations
import sys, random, argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from tools.venue_picker import VenuePicker
from tools.muoi_renderer import (
    render_cover, render_tip_slide,
    HOOK_HEADLINES,
)

ANH_DIR = Path(__file__).parent.parent / "anh video du lich"
_THUMBS_LOCAL   = Path(__file__).parent.parent / "thumbs"
_THUMBS_SIBLING = (
    Path(__file__).parent.parent.parent.parent
    / "he thong edit video du lich" / "CreatorAppDuLich" / "thumbs"
)
THUMBS = _THUMBS_LOCAL if _THUMBS_LOCAL.exists() else _THUMBS_SIBLING


def _pick_bg() -> str:
    imgs = list(ANH_DIR.glob("*.JPG")) + list(ANH_DIR.glob("*.jpg"))
    imgs = [p for p in imgs if p.stat().st_size > 50_000]
    return str(random.choice(imgs)) if imgs else ""


def _resolve_thumb(venue: dict) -> str:
    name = venue.get("name", "")
    pth = THUMBS / f"{name}.jpg"
    if pth.exists():
        return str(pth)
    img = venue.get("image_path", "")
    if img:
        alt = THUMBS / Path(img).name
        if alt.exists():
            return str(alt)
    return ""


def _pick_n(picker: VenuePicker, cat: str, n: int = 8, fallback: str | None = None) -> list:
    avail = [v for v in picker._all if v.get("loai_quan") == cat and v["name"] not in picker._used]
    items = picker.pick_n(min(n, len(avail)), loai_quan=cat) if avail else []
    if len(items) < n and fallback:
        items += picker.pick_n(n - len(items), loai_quan=fallback)
    return [{**v, "_resolved_path": _resolve_thumb(v)} for v in items[:n]]


TIP_SLIDES = [
    {
        "slug": "hotel",
        "title": "KHÔNG QUÊN\nBOOK PHÒNG TRƯỚC",
        "tips": [
            "Mùa cao điểm như Lễ, Tết, cuối tuần dễ bị ép giá",
            "Book trước 1-2 tuần để có giá tốt và vị trí đẹp",
            "Nên chọn chỗ gần trung tâm để tiện di chuyển",
        ],
        "subheader": "MẤY CHỖ LƯU TRÚ ĐÁNG THỬ",
        "cat": "khách sạn",
        "fallback": None,
        "n_venues": 8,
        "n_thumbs": 2,
    },
    {
        "slug": "checkin",
        "title": "KHÔNG NÊN\nQUÁ TIN VÀO ẢNH MẠNG",
        "tips": [
            "Thực tế đôi khi không giống ảnh trên mạng",
            "Đọc review thực tế trước khi đến",
            "Một số điểm hot nhưng ngoài đời nhỏ hơn tưởng",
        ],
        "subheader": "ĐIỂM CHECK-IN THỰC SỰ ĐẸP",
        "cat": "tham quan",
        "fallback": None,
        "n_venues": 8,
        "n_thumbs": 3,
    },
    {
        "slug": "food",
        "title": "KHÔNG ĂN UỐNG\nMÀ CHƯA HỎI GIÁ",
        "tips": [
            "Hỏi giá trước khi gọi món, nhất là quán không menu",
            "Tránh hàng rong gần điểm du lịch dễ bị chặt chém",
            "Đọc review Google Maps trước khi vào quán",
        ],
        "subheader": "QUÁN ĂN GIÁ HỢP LÝ",
        "cat": "quán ăn",
        "fallback": None,
        "n_venues": 8,
        "n_thumbs": 3,
    },
    {
        "slug": "cafe",
        "title": "KHÔNG BIẾT NÊN\nĐI QUÁN CAFE NÀO",
        "tips": [
            "Lên TikTok/Instagram tìm quán nhưng đọc review kỹ",
            "Quán bán view thường nước không ngon bằng",
            "Hỏi người địa phương để tìm quán thật sự ngon",
        ],
        "subheader": "QUÁN CAFE ĐÁNG ĐẾN",
        "cat": "quán cà phê",
        "fallback": None,
        "n_venues": 8,
        "n_thumbs": 3,
    },
    {
        "slug": "play",
        "title": "KHÔNG BIẾT\nĐI CHƠI GÌ",
        "tips": [
            "Đà Lạt nhiều chỗ chơi nhưng hơi xa trung tâm",
            "Dịp lễ tết đông nên xếp hàng lâu, đi sớm",
            "Thuê xe máy để chủ động khám phá tự do hơn",
        ],
        "subheader": "HOẠT ĐỘNG KHÔNG NÊN BỎ QUA",
        "cat": "tham quan",
        "fallback": None,
        "n_venues": 6,
        "n_thumbs": 3,
    },
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--out", default="")
    args = parser.parse_args()
    if args.seed is not None:
        random.seed(args.seed)

    picker = VenuePicker(seed=args.seed)
    out_dir = args.out or str(Path(__file__).parent / "output" / "albums" / "muoi_demo")
    p = Path(out_dir)
    paths = []

    hook = random.choice(HOOK_HEADLINES)
    out0 = str(p / "muoi_00_cover.png")
    print(f"[1/6] Cover → {out0}")
    paths.append(render_cover(_pick_bg(), hook, out0))

    for i, cfg in enumerate(TIP_SLIDES, start=2):
        venues = _pick_n(picker, cfg["cat"], cfg["n_venues"], cfg.get("fallback"))
        thumbs = venues[:cfg["n_thumbs"]]
        out_n = str(p / f"muoi_{i-1:02d}_{cfg['slug']}.png")
        print(f"[{i}/6] {cfg['slug']} → {out_n}")
        paths.append(render_tip_slide(
            _pick_bg(),
            cfg["title"],
            cfg["tips"],
            cfg["subheader"],
            venues,
            thumbs,
            out_n,
        ))

    print(f"\n✓ Album xong — {len(paths)} slides:")
    for s in paths:
        print(f"  file:///{Path(s).as_posix()}")


if __name__ == "__main__":
    main()
