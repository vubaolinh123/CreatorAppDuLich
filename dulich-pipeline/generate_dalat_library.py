"""
generate_dalat_library.py — Daily framework: tạo slides từ thư viện Đà Lạt.

Chế độ tự động (8am daily):
    python -X utf8 generate_dalat_library.py [--seed N]
    → Chọn venues từ DB, render 4 slides, lưu spec.json để admin review/sửa.

Re-render sau khi sửa spec:
    python -X utf8 generate_dalat_library.py --spec output/albums/mle23_output/YYYY-MM-DD_spec.json
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from tools.venue_picker import VenuePicker
from tools.venues_db import get_all, resolve_image
from tools.mle23_renderer import render_cover, render_venue_list

MAX_PER_SLIDE = 8
DEFAULT_SPEC = {
    "month_tag":  "Tháng 6",
    "handle_tag": "@thamhiemdalat",
}


def _sort_venues(venues: list) -> list:
    return sorted(venues, key=lambda v: 0 if v.get("loai") == "không seeding" else 1)


def _venue_entry(v: dict) -> dict:
    return {
        "name":      v.get("name", ""),
        "signature": v.get("signature", ""),
        "address":   v.get("address", ""),
    }


def build_spec_from_library(seed: int | None = None) -> dict:
    picker    = VenuePicker(seed=seed)
    all_venues = get_all()

    def bg_of(v):
        return resolve_image(v) if v else ""

    v_cover = picker.pick_one(co_nguoi="có")

    restaurants = _sort_venues([v for v in all_venues if v.get("loai_quan") == "quán ăn"])
    v_r = picker.pick_one(loai_quan="quán ăn")

    hotels = _sort_venues([v for v in all_venues if v.get("loai_quan") == "khách sạn"])
    v_h = picker.pick_one(loai_quan="khách sạn")

    checkin = [v for v in all_venues if v.get("loai_quan") in ("tham quan", "quán cà phê")]
    v_c = picker.pick_one(co_nguoi="có")

    return {
        "date":       str(date.today()),
        "month_tag":  DEFAULT_SPEC["month_tag"],
        "handle_tag": DEFAULT_SPEC["handle_tag"],
        "slides": {
            "cover": {
                "bg_venue": v_cover.get("name", "") if v_cover else "",
                "bg_image": bg_of(v_cover),
            },
            "quan_an": {
                "bg_venue":  v_r.get("name", "") if v_r else "",
                "bg_image":  bg_of(v_r),
                "pill_text": "ĂN GÌ Ở ĐÀ LẠT?",
                "venues":    [_venue_entry(v) for v in restaurants[:MAX_PER_SLIDE]],
            },
            "khach_san": {
                "bg_venue":  v_h.get("name", "") if v_h else "",
                "bg_image":  bg_of(v_h),
                "pill_text": "LƯU TRÚ Ở ĐÂU?",
                "venues":    [_venue_entry(v) for v in hotels[:MAX_PER_SLIDE]],
            },
            "checkin": {
                "bg_venue":  v_c.get("name", "") if v_c else "",
                "bg_image":  bg_of(v_c),
                "pill_text": "ĐIỂM CHECK-IN & CÀ PHÊ",
                "venues":    [_venue_entry(v) for v in checkin],
            },
        },
    }


def render_all(spec: dict, out_dir: Path) -> list[str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    cover_spec = {"month_tag": spec["month_tag"], "handle_tag": spec["handle_tag"]}
    paths = []

    sl = spec["slides"]

    out0 = str(out_dir / "lib_00_cover.png")
    paths.append(render_cover(sl["cover"]["bg_image"], out0, spec=cover_spec))
    print(f"[0] Cover")

    out1 = str(out_dir / "lib_01_quan_an.png")
    paths.append(render_venue_list(
        sl["quan_an"]["bg_image"],
        sl["quan_an"]["pill_text"],
        sl["quan_an"]["venues"],
        out1,
    ))
    print(f"[1] Quán ăn ({len(sl['quan_an']['venues'])} venues)")

    out2 = str(out_dir / "lib_02_khach_san.png")
    paths.append(render_venue_list(
        sl["khach_san"]["bg_image"],
        sl["khach_san"]["pill_text"],
        sl["khach_san"]["venues"],
        out2,
    ))
    print(f"[2] Khách sạn ({len(sl['khach_san']['venues'])} venues)")

    out3 = str(out_dir / "lib_03_checkin.png")
    paths.append(render_venue_list(
        sl["checkin"]["bg_image"],
        sl["checkin"]["pill_text"],
        sl["checkin"]["venues"],
        out3,
    ))
    print(f"[3] Tham quan + cà phê ({len(sl['checkin']['venues'])} venues)")

    return paths


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--out", default="")
    parser.add_argument("--spec", default="", help="Path to existing spec.json to re-render")
    args = parser.parse_args()

    out_dir = Path(args.out) if args.out else (
        Path(__file__).parent / "output" / "albums" / "mle23_output"
    )

    if args.spec:
        spec_path = Path(args.spec)
        with open(spec_path, encoding="utf-8") as f:
            spec = json.load(f)
        print(f"Re-rendering from spec: {spec_path}")
    else:
        spec = build_spec_from_library(seed=args.seed)
        today = spec["date"]
        spec_path = out_dir / f"{today}_spec.json"
        out_dir.mkdir(parents=True, exist_ok=True)
        with open(spec_path, "w", encoding="utf-8") as f:
            json.dump(spec, f, ensure_ascii=False, indent=2)
        print(f"Spec saved: {spec_path}")
        print(f"  (edit text/venues in this file, then re-run with --spec to update slides)")

    paths = render_all(spec, out_dir)

    print(f"\n{len(paths)} slides:")
    for s in paths:
        print(f"  file:///{Path(s).as_posix()}")


if __name__ == "__main__":
    main()
