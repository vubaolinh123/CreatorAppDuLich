# -*- coding: utf-8 -*-
"""
generate_uyen1tip.py — "Travel Tips" infographic carousel.
7 slides: cover + intro + 5 tip slides.
Usage: python -X utf8 generate_uyen1tip.py [--seed N] [--out path]
"""
from __future__ import annotations
import sys, argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from tools.venue_picker import VenuePicker, CHECKIN_CATS
from tools.uyen1tip_renderer import render_cover, render_intro, render_tip

SLIDE_DEFS = [
    {
        "title": "KO QUÁ TIN VÀO ẢNH MẠNG 100%",
        "bullets": [
            "1 SỐ ĐIỂM CHECK-IN NỔI TIẾNG TRÊN MẠNG NHƯNG NGOÀI ĐỜI NHỎ HOẶC KO NHƯ MONG ĐỢI",
            "NÊN XEM REVIEW THỰC TẾ TỪ NHIỀU NGUỒN, CÓ VID CÀNG TỐT",
        ],
        "section": "ĐỊA ĐIỂM CHECK-IN HOT HIT DẠO NÀY",
        "loai_quan": ("điểm checkin", "điểm checkin free"),
        "seeding_first": False, "n_venues": 10, "n_cols": 2,
    },
    {
        "title": "KO PHẢI LÚC NÀO CŨNG SĂN DC MÂY",
        "bullets": [
            "KO CHECK THỜI TIẾT MÀ CỨ THẾ ĐI, ĐẾN NƠI KO CÓ MÂY VỪA TỐN SỨC, TỐN TGIAN",
            "XEM KĨ THỜI TIẾT, CHỌN NGÀY NẮNG SAU MƯA MÂY SẼ DÀY HƠN. ĐI MẤY QUÁN SĂN MÂY GẦN TRUNG TÂM LÀ OKI",
        ],
        "section": "ĐỊA ĐIỂM SĂN MÂY ĐẸP, GẦN TRUNG TÂM",
        "loai_quan": "điểm săn mây", "n_venues": 4, "n_cols": 1,
    },
    {
        "title": "KO DC QUÊN MẤY DỊCH VỤ NÀY",
        "bullets": [
            "NÊN BOOK PHÒNG TRƯỚC NHẤT LÀ MÙA CAO ĐIỂM LỄ, TẾT NẾU KO DỄ BỊ ÉP GIÁ",
            "TÌNH TRẠNG LỪA ĐẢO NHIỀU NÊN MNG BOOK QUA APP CHO CHẮC, BOOK TRƯỚC 2 TUẦN LÀ HỢP LÍ",
        ],
        "section": "CHỖ Ở",
        "loai_quan": "khách sạn", "n_venues": 5, "n_cols": 1,
        "extra_section": {
            "label": "DI CHUYỂN",
            "items": [
                "HL: 03345 672 571 — THUÊ XE MÁY GIÁ TỐT",
                "XE GA 150K/ 24H. GIAO NHẬN TẬN NƠI",
            ],
        },
    },
    {
        "title": "KO DC QUÊN ĐỒ DÙNG CẦN THIẾT",
        "bullets": [
            "ĐÀ LẠT DẠO NÀY NẮNG MƯA THẤT THƯỜNG",
            "SÁNG SỚM VÀ BAN ĐÊM KHÁ LẠNH, ĐÂU ĐÓ CHỈ 17 DO C",
            "NHIỆT ĐỘ TB TRONG NGÀY TẦM 23-25 DO C",
            "CHECK THỜI TIẾT TRƯỚC ĐỂ CBI QUẦN ÁO PHÙ HỢP",
        ],
        "section": "CHECK LIST ĐỒ DÙNG CẦN THIẾT",
        "loai_quan": None, "n_venues": 0, "n_cols": 1,
        "static_items": [
            "QUẦN ÁO ẤM, PHỤ KIỆN: KHĂN CHOÀNG, MŨ, TÚI, MẮT KÍNH, BOOTS,...",
            "ĐỒ CÁ NHÂN: KCN, THUỐC SAY XE, ĐAU BỤNG, TÚI NILONG ĐỰNG ĐỒ DƠ,...",
            "SẠC ĐT, SẠC DỰ PHÒNG, TRIPOD,...",
            "CCCD, BLXM, 1 ÍT TIỀN MẶT,...",
        ],
    },
    {
        "title": "KO ĂN UỐNG KHI CHƯA HỎI GIÁ",
        "bullets": [
            "KO RIÊNG GÌ Ở ĐÀ LẠT, TUI THẤY Ở ĐÂU CŨNG Z HẾT Á NÊN PHẢI HỎI GIÁ TRƯỚC KHI ĂN",
            "CHỌN QUÁN CÓ MENU RÕ RÀNG, ĐỌC KĨ REVIEW Ở GG MAPS, CÓ ĐÁNH GIÁ TỐT",
            "HẠN CHẾ ĂN UỐNG Ở CHỢ",
        ],
        "section": "MÍ QUÁN MÀ TUI MUỐN RCM CHO MNG",
        "loai_quan": "quán ăn", "n_venues": 8, "n_cols": 2,
    },
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    picker = VenuePicker(seed=args.seed)
    from tools.album_titles import ai_cover_texts
    from tools.uyen1tip_renderer import INTRO_TEXT_VN
    _t = ai_cover_texts("uyen1", {
        "intro": INTRO_TEXT_VN,
        **{f"t{i+1}": s["title"] for i, s in enumerate(SLIDE_DEFS)},
    })
    for i, s in enumerate(SLIDE_DEFS):
        s["title"] = _t[f"t{i+1}"]
    out_dir = args.out or str(
        Path(__file__).parent / "output" / "albums" / "uyen1tip_demo"
    )
    p = Path(out_dir)
    p.mkdir(parents=True, exist_ok=True)

    paths = []

    # 0 — Intro (bỏ slide cover không tiêu đề theo feedback NV)
    intro_v = picker.pick_one(loai_quan=CHECKIN_CATS) or picker.pick_one()
    paths.append(render_intro(
        picker.image(intro_v),
        str(p / "uyen1tip_00_intro.png"),
        text=_t["intro"],
    ))
    print(f"[0] Intro")

    # 1-5 — Tip slides
    for i, sdef in enumerate(SLIDE_DEFS):
        # bg: any available venue (will be heavily overlaid, track=False to preserve pool)
        bg_v = picker.pick_one(track=False) or intro_v

        # Pick venues first to avoid depleting pool before frame pick
        venues = []
        n = sdef.get("n_venues", 0)
        if n > 0 and not sdef.get("static_items"):
            venues = picker.pick_n(n, loai_quan=sdef.get("loai_quan"),
                                   seeding_first=sdef.get("seeding_first", True))

        # Frame photo: use first venue's image if available, else pick separately
        if venues:
            frame_v = venues[0]
        else:
            frame_lq = sdef.get("loai_quan") or CHECKIN_CATS
            frame_v = picker.pick_one(loai_quan=frame_lq, track=False) or bg_v

        out_name = f"uyen1tip_0{i + 1}_tip{i}.png"
        paths.append(render_tip(
            picker.image(bg_v),
            picker.image(frame_v),
            sdef,
            venues,
            str(p / out_name),
        ))
        print(f"[{i + 1}] Tip: {sdef['title'][:42]}")
        if venues:
            print(f"     venues: {', '.join(v['name'] for v in venues[:4])}{'...' if len(venues) > 4 else ''}")

    print(f"\n✓ {len(paths)} slides -> {out_dir}")
    for s in paths:
        print(f"  file:///{Path(s).as_posix()}")


if __name__ == "__main__":
    main()
