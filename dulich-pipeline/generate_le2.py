"""
generate_le2.py — Tạo album Lê 2 từ spec ổn định trong data/album_specs.
Usage: python -X utf8 generate_le2.py [--spec path/to/spec.json] [--out path]

Mặc định đọc spec từ data/album_specs/le2.json và xuất PNG vào
output/albums/le2-demo. Thư mục output có thể được archive/xóa tự động,
vì vậy không được dùng nó để lưu input bắt buộc của template.
"""
from __future__ import annotations
import sys, json, argparse
from pathlib import Path

ROOT = Path(__file__).parent
DEFAULT_SPEC_PATH = ROOT / "data" / "album_specs" / "le2.json"
DEFAULT_OUTPUT_DIR = ROOT / "output" / "albums" / "le2-demo"

sys.path.insert(0, str(ROOT))
from tools.mle23_renderer import render_cover, render_venue_list


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--spec",
        default=str(DEFAULT_SPEC_PATH),
    )
    parser.add_argument("--out", default="")
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args(argv)
    import random
    if args.seed is not None:
        random.seed(args.seed)

    spec_path = Path(args.spec)
    if not spec_path.exists():
        print(f"[ERROR] Spec không tồn tại: {spec_path}", file=sys.stderr)
        return 2

    with open(spec_path, encoding="utf-8") as f:
        spec = json.load(f)

    # RANDOM hoá từ thư viện: cả DANH SÁCH QUÁN lẫn ảnh nền mỗi slide
    # (spec cũ cố định quán + chứa path ảnh D:\ đã chết → lần nào cũng y hệt).
    from tools.venues_db import get_all
    from tools.venue_picker import VenuePicker, CHOI_CATS
    allv = get_all()

    def _sample(cats: list[str], n: int) -> list[dict]:
        pool = [v for v in allv if (v.get("loai_quan") or "").strip() in cats]
        random.shuffle(pool)
        return VenuePicker.seeding_first(pool)[:n]   # quán 'cần seeding' lên đầu list

    def _sig(v: dict) -> str:
        return (v.get("signature") or v.get("feature") or "").strip()

    _CATS = {"quan_an": (["quán ăn"], 8),
             "khach_san": (["khách sạn"], 8),
             "checkin": (list(CHOI_CATS), 5)}   # check-in + cà phê (khớp pill "& CÀ PHÊ")
    slides = spec.get("slides") or {}
    for key, s in slides.items():
        if not isinstance(s, dict):
            continue
        picked = None
        if key in _CATS:
            cats, n = _CATS[key]
            picked = _sample(cats, n)
            if picked:
                s["venues"] = [{"name": v["name"], "signature": _sig(v),
                                "address": (v.get("address") or "").strip()} for v in picked]
        # nền: slide có list quán → ảnh 1 quán trong slide; slide cover (không quán) → ảnh chung
        if picked:
            bgv = random.choice(picked)
            s["bg_venue"] = bgv["name"]
            s["bg_image"] = VenuePicker.image(bgv) or ""
        else:
            s["bg_venue"] = ""
            s["bg_image"] = VenuePicker.album_cover_bg()

    out_dir = Path(args.out) if args.out else DEFAULT_OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    slides_spec = spec.get("slides", {})
    cover_spec = slides_spec.get("cover", {})
    from tools.album_titles import ai_cover_texts
    hook = ai_cover_texts("le2", {
        "percent": "99%", "title": "khách du lịch",
        "line1": "/chưa biết những điều này",
        "line2": "hoặc chưa từng trải nghiệm /",
    })
    cover_meta = {
        "month_tag":  spec.get("month_tag", "Tháng 6"),
        "handle_tag": spec.get("handle_tag", "@thamhiemdalat"),
        **hook,
    }

    paths = []
    idx = 0

    # Slide 0: Cover
    bg = cover_spec.get("bg_image", "")
    out0 = str(out_dir / "le2_00_cover.png")
    print(f"[{idx}] Cover → {out0}")
    paths.append(render_cover(bg, out0, spec=cover_meta))
    idx += 1

    # Slides 1-N: venue list slides from spec order
    SLIDE_ORDER = ["quan_an", "khach_san", "checkin"]
    for key in SLIDE_ORDER:
        s = slides_spec.get(key)
        if not s:
            continue
        bg_i = s.get("bg_image", "")
        pill = s.get("pill_text", key.upper())
        venues = s.get("venues", [])
        out_n = str(out_dir / f"le2_{idx:02d}_{key}.png")
        print(f"[{idx}] {pill} ({len(venues)} venues) → {out_n}")
        paths.append(render_venue_list(bg_i, pill, venues, out_n))
        idx += 1

    print(f"\n✓ {len(paths)} slides:")
    for s in paths:
        print(f"  file:///{Path(s).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
