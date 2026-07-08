"""
generate_muoi-dalat-travel-guide.py — Auto-generate Muoi Dalat Travel Guide album.

Usage:
    python -X utf8 "generate_muoi-dalat-travel-guide.py" [--seed N] [--out path]

Generates 6 slides:
  00_cover          — full-bleed photo cover
  01_tip_venue_1    — accommodation tips + 2 hotel thumbnails
  02_tip_venue_2    — restaurant tips + 3 food thumbnails
  03_tip_venue_3    — food/specialty tips + 3 food thumbnails
  04_tip_venue_4    — café tips + 3 café thumbnails
  05_tip_venue_5    — activities tips + 3 activity thumbnails
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from tools.venue_picker import VenuePicker

# Import file has a hyphen in name, must use importlib
import importlib
import importlib.util

_RENDERER_PATH = Path(__file__).parent / "tools" / "muoi-dalat-travel-guide_renderer.py"
_spec = importlib.util.spec_from_file_location("muoi_dalat_travel_guide_renderer", _RENDERER_PATH)
_mod  = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

render_cover       = _mod.render_cover
render_tip_venue_1 = _mod.render_tip_venue_1
render_tip_venue_2 = _mod.render_tip_venue_2
render_tip_venue_3 = _mod.render_tip_venue_3
render_tip_venue_4 = _mod.render_tip_venue_4
render_tip_venue_5 = _mod.render_tip_venue_5

TEMPLATE_ID = "muoi-dalat-travel-guide"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate Muoi Dalat Travel Guide album (6 slides)."
    )
    parser.add_argument("--seed", type=int, default=None,
                        help="Random seed for reproducible venue picking.")
    parser.add_argument("--out", default="",
                        help="Output directory. Defaults to output/albums/muoi-dalat-travel-guide_output")
    args = parser.parse_args()

    out_dir = args.out or str(
        Path(__file__).parent / "output" / "albums" / "muoi-dalat-travel-guide_output"
    )
    p = Path(out_dir)
    p.mkdir(parents=True, exist_ok=True)

    picker = VenuePicker(seed=args.seed)

    def img(v: dict) -> str:
        return picker.image(v) if v else ""

    # ── Pick venues by category ────────────────────────────────────────────────
    # Cover — scenic or any venue with photo
    cover_v     = picker.pick_one(co_nguoi="có")
    if not cover_v:
        cover_v = picker.pick_one()

    # Accommodation
    hotels      = picker.pick_n(2, loai_quan="khách sạn")
    hotel_names = [v["name"] for v in hotels]
    hotel_imgs  = [img(v) for v in hotels]

    # Restaurants (for slides 2 and 3)
    restaurants  = picker.pick_n(6, loai_quan="quán ăn")
    rest_names   = [v["name"] for v in restaurants]
    rest_imgs    = [img(v) for v in restaurants]
    # Background for restaurant slides
    rest_bg_v    = picker.pick_one(loai_quan="quán ăn")
    if not rest_bg_v:
        rest_bg_v = cover_v

    # Cafes (slide 4)
    cafes        = picker.pick_n(6, loai_quan="quán cà phê")
    cafe_names   = [v["name"] for v in cafes]
    cafe_imgs    = [img(v) for v in cafes]
    cafe_bg_v    = picker.pick_one(loai_quan="quán cà phê")
    if not cafe_bg_v:
        cafe_bg_v = cover_v

    # Activities (slide 5)
    activities   = picker.pick_n(3, loai_quan="tham quan")
    act_names    = [v["name"] for v in activities]
    act_imgs     = [img(v) for v in activities]
    act_bg_v     = picker.pick_one(loai_quan="tham quan")
    if not act_bg_v:
        act_bg_v = cover_v

    # Hero inset for activities from a different activity venue
    hero_v       = picker.pick_one(loai_quan="tham quan")
    hero_img     = img(hero_v) if hero_v else ""
    hero_cap     = hero_v["name"] if hero_v else ""

    # ── Render slides ──────────────────────────────────────────────────────────
    paths = []

    # Slide 00 — Cover
    out0 = str(p / f"{TEMPLATE_ID}_00_cover.png")
    print(f"[00] Cover ({cover_v['name'] if cover_v else 'placeholder'}) → {out0}")
    paths.append(render_cover(
        bg_path=img(cover_v),
        out_path=out0,
        title_lines=["KHÁM PHÁ", "ĐÀ LẠT", "TOÀN TẬP"],
        subtitle="[ Hướng dẫn du lịch Đà Lạt ]",
    ))

    # Slide 01 — Accommodation
    out1 = str(p / f"{TEMPLATE_ID}_01_tip_venue_1.png")
    print(f"[01] Accommodation tip → {out1}")
    paths.append(render_tip_venue_1(
        bg_path=img(cover_v),
        out_path=out1,
        title="LƯU TRÚ Ở ĐÂU?",
        tip_text=(
            "Đặt phòng sớm để có giá tốt, đặc biệt dịp lễ và cuối tuần. "
            "Nên chọn homestay hoặc khách sạn khu trung tâm để tiện đi lại. "
            "Đà Lạt có nhiều lựa chọn từ bình dân đến sang trọng."
        ),
        section_label="MẤY CHỖ LƯU TRÚ",
        venues=hotel_names if hotel_names else ["Khách sạn trung tâm", "Homestay view đẹp"],
        thumb_paths=hotel_imgs[:2],
        thumb_captions=[v["name"] for v in hotels[:2]],
    ))

    # Slide 02 — Restaurants (two-column)
    out2 = str(p / f"{TEMPLATE_ID}_02_tip_venue_2.png")
    print(f"[02] Restaurants tip → {out2}")
    paths.append(render_tip_venue_2(
        bg_path=img(rest_bg_v),
        out_path=out2,
        title="ĂN Ở ĐÂU NGON?",
        tip_text=(
            "Đà Lạt có nhiều quán ăn ngon giá hợp lý. "
            "Tránh xa mấy quán cạnh chợ Đêm nếu muốn ăn no mà không tốn nhiều. "
            "Đặc sản nên thử: bánh mì xíu mại, phở bò, lẩu bò."
        ),
        section_label="QUÁN ĂN GỢI Ý",
        venues=rest_names[:6] if rest_names else ["Quán phở A", "Bánh mì B", "Lẩu C", "Cơm D"],
        thumb_paths=rest_imgs[:3],
        thumb_captions=[v["name"] for v in restaurants[:3]],
    ))

    # Slide 03 — Food specialties with price highlights
    out3 = str(p / f"{TEMPLATE_ID}_03_tip_venue_3.png")
    print(f"[03] Food specialties → {out3}")
    food_venues_s3 = restaurants[3:] if len(restaurants) > 3 else restaurants
    paths.append(render_tip_venue_3(
        bg_path=img(rest_bg_v),
        out_path=out3,
        title="ĂN GÌ Ở ĐÀ LẠT?",
        tip_text=(
            "Đặc sản Đà Lạt rất đa dạng. "
            "Nhớ thử bánh mì xíu mại [15.000đ], bơ, dâu tây và các món nướng chợ Đêm. "
            "Nhiều quán ngon, view đẹp ngay trung tâm không phải đi xa."
        ),
        section_label="QUÁN ĐẶC SẢN",
        venues=[v["name"] for v in food_venues_s3[:6]]
              if food_venues_s3 else ["Xíu Mại A", "Bơ Tươi B", "Dâu Tây C", "Lẩu Bò D"],
        thumb_paths=[img(v) for v in food_venues_s3[:3]],
        thumb_captions=[v["name"] for v in food_venues_s3[:3]],
        price_note="Giá trung bình: 40.000 – 120.000đ / người",
    ))

    # Slide 04 — Cafés
    out4 = str(p / f"{TEMPLATE_ID}_04_tip_venue_4.png")
    print(f"[04] Cafés → {out4}")
    paths.append(render_tip_venue_4(
        bg_path=img(cafe_bg_v),
        out_path=out4,
        title="CAFE VIEW ĐẸP",
        tip_text=(
            "Đà Lạt có hàng trăm quán cà phê view đẹp, không khí mát mẻ. "
            "Đến sớm để chọn bàn đẹp và tránh đông vào cuối tuần. "
            "Cà phê chồn, cà phê muối, và bánh croissant là must-try."
        ),
        section_label="QUÁN CÀ PHÊ GỢI Ý",
        venues=cafe_names[:6] if cafe_names else ["Cafe A", "Cafe B", "Cafe C", "Cafe D"],
        thumb_paths=cafe_imgs[:3],
        thumb_captions=[v["name"] for v in cafes[:3]],
    ))

    # Slide 05 — Activities
    out5 = str(p / f"{TEMPLATE_ID}_05_tip_venue_5.png")
    print(f"[05] Activities → {out5}")
    paths.append(render_tip_venue_5(
        bg_path=img(act_bg_v),
        out_path=out5,
        title="VUI CHƠI GÌ?",
        tip_text=(
            "Đà Lạt không chỉ là cà phê và sống ảo. "
            "Có thể trekking, chèo SUP, cắm trại, hoặc đạp xe quanh hồ. "
            "Nhiều hoạt động miễn phí chỉ cần đôi giày tốt."
        ),
        section_label="ĐỊA ĐIỂM HOẠT ĐỘNG",
        venues=act_names[:4] if act_names else ["Langbiang", "Hồ Tuyền Lâm", "Thung Lũng Tình Yêu"],
        thumb_paths=act_imgs[:3],
        thumb_captions=[v["name"] for v in activities[:3]],
        hero_inset_path=hero_img,
        hero_inset_caption=hero_cap,
    ))

    # ── Done ──────────────────────────────────────────────────────────────────
    print(f"\n{len(paths)} slides generated:")
    for s in paths:
        print(f"  file:///{Path(s).as_posix()}")


if __name__ == "__main__":
    main()
