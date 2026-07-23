# -*- coding: utf-8 -*-
"""
generate_vy1.py — Generate vy1 album: 7 slides matching vy1 template format.
Usage:
  python -X utf8 generate_vy1.py [--seed N] [--out path]   # generate mới
  python -X utf8 generate_vy1.py --spec path/to/_spec.json  # render từ spec đã chỉnh

Slides:
  00_cover    — full-screen bg + hook headline
  01_cafe     — 2x2 grid cà phê / food mix
  02_checkin  — 2x2 grid tham quan
  03_hotel    — 2x2 grid khách sạn
  04_food1    — 2x2 grid quán ăn
  05_food2    — 2x2 grid quán ăn
  06_list     — bullet list of all food venues + bottom 4 thumbnails

Sau khi generate, script lưu _spec.json trong output folder.
Mở file đó, chỉnh text/venue, rồi chạy lại với --spec để render lại.
"""
from __future__ import annotations
import sys, random, argparse, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from tools.venue_picker import VenuePicker, album_bg
from tools.venues_db import get_venues, resolve_image, get_all
from tools.vy1_renderer import (
    render_cover, render_grid_slide, render_food_list_slide, HOOK_HEADLINES,
)


def _pick_bg() -> str:
    # Ảnh nền không phải của quán → lấy random từ kho ảnh chung (không trùng).
    return album_bg()


def _add_resolved(venues: list) -> list:
    return [{**v, "_resolved_path": resolve_image(v)} for v in venues]


def _fill_to_4(picker: VenuePicker, primary_cat: str,
               fallbacks: list | None = None) -> list:
    avail = [v for v in picker._all
             if v.get("loai_quan") == primary_cat and v["name"] not in picker._used]
    result = picker.pick_n(min(4, len(avail)), loai_quan=primary_cat) if avail else []
    if len(result) < 4 and fallbacks:
        for cat in fallbacks:
            needed = 4 - len(result)
            result.extend(picker.pick_n(needed, loai_quan=cat))
            if len(result) >= 4:
                break
    return result[:4]


def _venues_by_names(names: list[str]) -> list:
    """Tra cứu venue dicts từ danh sách tên."""
    db = {v["name"]: v for v in get_all()}
    return [db[n] for n in names if n in db]


def _save_spec(p: Path, hook: str, cover_bg: str, list_bg: str,
               grid_slides: list, all_food: list) -> Path:
    spec = {
        "_note": "Chỉnh file này rồi chạy: python -X utf8 generate_vy1.py --spec <path>",
        "hook": hook,
        "cover_bg": cover_bg,
        "list_bg": list_bg,
        "grid_slides": grid_slides,
    }
    spec_path = p / "_spec.json"
    with open(spec_path, "w", encoding="utf-8") as f:
        json.dump(spec, f, ensure_ascii=False, indent=2)
    return spec_path


def _render_from_spec(spec: dict, p: Path) -> list:
    """Render 7 slides từ spec dict đã được chỉnh sửa."""
    paths = []
    hook = spec.get("hook", HOOK_HEADLINES[0])
    cover_bg = spec.get("cover_bg", _pick_bg())
    list_bg = spec.get("list_bg", _pick_bg())

    # Slide 0: Cover
    out0 = str(p / "vy1_00_cover.png")
    print(f"[1/7] Cover → {out0}")
    paths.append(render_cover(cover_bg, hook, out0))

    # Grid slides 1-5
    slide_files = ["vy1_01_cafe.png", "vy1_02_checkin.png", "vy1_03_hotel.png",
                   "vy1_04_food1.png", "vy1_05_food2.png"]
    for i, (s, fname) in enumerate(zip(spec.get("grid_slides", []), slide_files), 2):
        label = s.get("label", "")
        venues = _add_resolved(_venues_by_names(s.get("venues", [])))
        out = str(p / fname)
        print(f"[{i}/7] {label} ({len(venues)} venues) → {out}")
        paths.append(render_grid_slide(venues, label, out))

    # Slide 6: Food list
    all_food = _add_resolved(get_venues(loai_quan="quán ăn"))
    out6 = str(p / "vy1_06_list.png")
    print(f"[7/7] Food list ({len(all_food)} venues) → {out6}")
    paths.append(render_food_list_slide(list_bg, all_food, all_food[:4], out6))

    return paths


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--out", default="")
    parser.add_argument("--spec", default="", help="Path tới _spec.json để render lại")
    args = parser.parse_args()

    out_dir = args.out or str(Path(__file__).parent / "output" / "albums" / "vy1-demo")
    p = Path(out_dir)
    p.mkdir(parents=True, exist_ok=True)

    # ── Mode: render từ spec đã chỉnh ─────────────────────────────────────────
    if args.spec:
        spec_path = Path(args.spec)
        with open(spec_path, encoding="utf-8") as f:
            spec = json.load(f)
        paths = _render_from_spec(spec, p)
        print(f"\n✓ Render từ spec xong — {len(paths)} slides:")
        for s in paths:
            print(f"  file:///{Path(s).as_posix()}")
        return

    # ── Mode: generate mới ngẫu nhiên ─────────────────────────────────────────
    if args.seed is not None:
        random.seed(args.seed)

    picker = VenuePicker(seed=args.seed)
    paths = []

    from tools.album_titles import ai_cover_texts
    hook = ai_cover_texts("vy1", {"hook": random.choice(HOOK_HEADLINES)})["hook"]
    cover_bg = _pick_bg()
    list_bg = _pick_bg()

    # Cover
    out0 = str(p / "vy1_00_cover.png")
    print(f"[1/7] Cover → {out0}")
    paths.append(render_cover(cover_bg, hook, out0))

    # Grid slides — lưu info để write spec
    grid_specs = []

    cafes = _fill_to_4(picker, "quán cà phê", ["quán ăn"])
    print(f"[2/7] Cafe grid: {[v['name'] for v in cafes]}")
    paths.append(render_grid_slide(_add_resolved(cafes), "cà phê chillchill",
                                   str(p / "vy1_01_cafe.png")))
    grid_specs.append({"label": "cà phê chillchill", "venues": [v["name"] for v in cafes]})

    checkin = _fill_to_4(picker, "điểm checkin free", ["điểm checkin"])
    print(f"[3/7] Check-in grid: {[v['name'] for v in checkin]}")
    paths.append(render_grid_slide(_add_resolved(checkin), "Check-in free",
                                   str(p / "vy1_02_checkin.png")))
    grid_specs.append({"label": "Check-in free", "venues": [v["name"] for v in checkin]})

    hotels = _fill_to_4(picker, "khách sạn", ["điểm checkin free"])
    print(f"[4/7] Hotel grid: {[v['name'] for v in hotels]}")
    paths.append(render_grid_slide(_add_resolved(hotels), "Lưu trú xịn",
                                   str(p / "vy1_03_hotel.png")))
    grid_specs.append({"label": "Lưu trú xịn", "venues": [v["name"] for v in hotels]})

    food1 = _fill_to_4(picker, "quán ăn", ["quán cà phê"])
    print(f"[5/7] Food grid 1: {[v['name'] for v in food1]}")
    paths.append(render_grid_slide(_add_resolved(food1), "Quán ăn ngon",
                                   str(p / "vy1_04_food1.png")))
    grid_specs.append({"label": "Quán ăn ngon", "venues": [v["name"] for v in food1]})

    food2 = _fill_to_4(picker, "quán ăn", ["quán cà phê"])
    print(f"[6/7] Food grid 2: {[v['name'] for v in food2]}")
    paths.append(render_grid_slide(_add_resolved(food2), "Đặc sản Đà Lạt",
                                   str(p / "vy1_05_food2.png")))
    grid_specs.append({"label": "Đặc sản Đà Lạt", "venues": [v["name"] for v in food2]})

    # Food list
    all_food = _add_resolved(get_venues(loai_quan="quán ăn"))
    print(f"[7/7] Food list ({len(all_food)} venues)")
    paths.append(render_food_list_slide(list_bg, all_food, all_food[:4],
                                        str(p / "vy1_06_list.png")))

    # Lưu spec
    spec_path = _save_spec(p, hook, cover_bg, list_bg, grid_specs, all_food)
    print(f"\n✓ Album xong — {len(paths)} slides:")
    for s in paths:
        print(f"  file:///{Path(s).as_posix()}")
    print(f"\n📋 Spec đã lưu: {spec_path}")
    print("   Mở file đó, chỉnh text/venue, rồi chạy:")
    print(f"   python -X utf8 generate_vy1.py --spec \"{spec_path}\"")


if __name__ == "__main__":
    main()
