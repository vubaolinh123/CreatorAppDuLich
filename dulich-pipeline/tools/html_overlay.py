"""
html_overlay.py — Render overlay TĨNH bằng HTML/CSS qua Chromium (Playwright) → PNG trong suốt 1080x1920.

Dùng cho luồng nhân viên nv2/nv3 (giống kênh gốc 99%): hiệu ứng pop/fade do FFmpeg lo,
HTML chỉ lo phần tạo hình tĩnh (bo góc, gradient, web-font, emoji màu của Segoe UI Emoji).

Cách dùng (gọi từ renderer qua SUBPROCESS để tránh thread/event-loop của Playwright sync):
    python -m tools.html_overlay <jobs.json>
trong đó jobs.json = list các job:
  {"kind":"hook","style":"nv2","out":"hook.png","lines":["NGƯỜI MỚI ĐI ĐÀ LẠT VỀ","KHUYÊN NGƯỜI SẮP ĐI"]}
  {"kind":"section","style":"nv2","out":"s1.png","title":"Chỗ ở","emoji":"🏡🌳","body":["dòng 1","dòng 2"]}
  {"kind":"section","style":"nv3","out":"s2.png","title":"","emoji":"","body":["dòng 1","dòng 2"]}

1 lần chạy = 1 browser, render hết mọi job rồi thoát.
"""
from __future__ import annotations

import sys
import json
import html as _html
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FONT_DIR = ROOT / "assets" / "fonts"
W, H = 1080, 1920


def _furl(name: str) -> str:
    return (FONT_DIR / name).as_uri()


def _font_face_css() -> str:
    return f"""
    @font-face {{ font-family:'Mont'; src:url('{_furl("Montserrat-VF.ttf")}'); font-weight:1 999; }}
    @font-face {{ font-family:'Baloo'; src:url('{_furl("Baloo2-VF.ttf")}'); font-weight:1 999; }}
    @font-face {{ font-family:'BVP'; src:url('{_furl("BeVietnamPro-Bold-full.ttf")}'); font-weight:1 999; }}
    @font-face {{ font-family:'Marker'; src:url('{_furl("MTDSummerShow.otf")}'); }}
    """


_EMOJI_STACK = "'Segoe UI Emoji','Noto Color Emoji','Apple Color Emoji'"


def _doc(body: str, style: str) -> str:
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
    {_font_face_css()}
    *{{margin:0;padding:0;box-sizing:border-box;}}
    html,body{{width:{W}px;height:{H}px;background:transparent;overflow:hidden;}}
    .stage{{position:relative;width:{W}px;height:{H}px;}}
    {style}
    </style></head><body><div class="stage">{body}</div></body></html>"""


def _esc(s: str) -> str:
    return _html.escape(s or "")


# ─────────────────────────────────────────────────────────────────────────────
# HOOK
# ─────────────────────────────────────────────────────────────────────────────

def _hook_nv2(lines: list[str]) -> str:
    rot = [-3, 2, -2, 1]
    line_html = "".join(
        f'<div class="hl" style="transform:rotate({rot[i % len(rot)]}deg)">{_esc(t)}</div>'
        for i, t in enumerate(lines)
    )
    style = f"""
    .stickers{{position:absolute;top:14%;left:50%;transform:translateX(-50%);
        font-size:130px;font-family:{_EMOJI_STACK};z-index:3;
        filter:drop-shadow(0 6px 10px rgba(0,0,0,.35));}}
    .hook{{position:absolute;top:23%;left:0;width:100%;text-align:center;}}
    .hl{{font-family:'Mont',{_EMOJI_STACK};font-weight:900;font-style:italic;
        font-size:82px;line-height:1.1;letter-spacing:0;white-space:nowrap;
        color:#FFD11A;
        -webkit-text-stroke:15px #2A1505;paint-order:stroke fill;
        filter:drop-shadow(0 9px 1px rgba(0,0,0,.32));
        display:block;margin:0 0 4px;text-transform:uppercase;}}
    """
    body = f'<div class="stickers">🐱👍</div><div class="hook">{line_html}</div>'
    return _doc(body, style)


def _hook_nv3(lines: list[str]) -> str:
    line_html = "".join(f"<div>{_esc(t)}</div>" for t in lines)
    # SVG filter làm cạnh marker lởm chởm như highlight giấy xé (feTurbulence + displacement)
    rough = """<svg width="0" height="0" style="position:absolute"><filter id="rough">
      <feTurbulence type="fractalNoise" baseFrequency="0.018 0.014" numOctaves="2" seed="7" result="n"/>
      <feDisplacementMap in="SourceGraphic" in2="n" scale="14" xChannelSelector="R" yChannelSelector="G"/>
    </filter></svg>"""
    style = f"""
    .wrap{{position:absolute;top:15%;left:50%;transform:translateX(-50%) rotate(-4deg);}}
    .bow{{position:absolute;top:-50px;left:-62px;font-size:100px;font-family:{_EMOJI_STACK};z-index:3;
        transform:rotate(-8deg);}}
    .daisy{{position:absolute;bottom:-50px;right:-70px;font-size:92px;font-family:{_EMOJI_STACK};z-index:3;}}
    .marker{{position:relative;display:inline-block;padding:14px 56px 22px;text-align:center;}}
    .marker::before{{content:"";position:absolute;inset:0;
        background:#FBE96B;border-radius:14px 28px 16px 30px;
        filter:url(#rough);box-shadow:0 6px 16px rgba(0,0,0,.16);z-index:-1;}}
    .marker div{{font-family:'Marker',{_EMOJI_STACK};font-size:104px;line-height:1.02;
        color:#262626;white-space:nowrap;position:relative;}}
    """
    body = (f'{rough}<div class="wrap"><span class="bow">🎀</span>'
            f'<div class="marker">{line_html}</div><span class="daisy">🌼</span></div>')
    return _doc(body, style)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION (tiêu đề + body)
# ─────────────────────────────────────────────────────────────────────────────

def _section_nv2(title: str, emoji: str, body: list[str],
                 align: str = "left", no_pill: bool = False) -> str:
    center = (align == "center")
    pill = ""
    if title:
        em = f'<span class="em">{_esc(emoji)}</span>' if emoji else ""
        cls = "pill nopill" if no_pill else "pill"
        pill = f'<div class="{cls}">{em}<span class="tt">{_esc(title)}</span></div>'
    body_html = "".join(f"<div>{_esc(t)}</div>" for t in body)
    sec_pos = (f"left:0;width:100%;text-align:center;align-items:center;"
               if center else f"left:54px;width:{W-108}px;text-align:left;align-items:flex-start;")
    style = f"""
    .sec{{position:absolute;top:148px;display:flex;flex-direction:column;{sec_pos}}}
    .pill{{display:inline-flex;align-items:center;gap:14px;
        background:rgba(18,18,20,0.72);border-radius:28px;padding:9px 34px;margin-bottom:20px;}}
    .pill.nopill{{background:transparent;padding:0 4px;}}
    .pill .em{{font-size:64px;font-family:{_EMOJI_STACK};line-height:1;}}
    .pill .tt{{font-family:'Baloo',{_EMOJI_STACK};font-weight:700;font-size:68px;color:#fff;line-height:1.08;
        text-shadow:0 2px 10px rgba(0,0,0,.55);}}
    .body div{{font-family:'BVP',{_EMOJI_STACK};font-weight:600;font-size:50px;color:#fff;
        line-height:1.3;text-align:{"center" if center else "left"};
        text-shadow:0 2px 5px rgba(0,0,0,.98),0 0 14px rgba(0,0,0,.75),0 0 3px rgba(0,0,0,.9);
        -webkit-text-stroke:0.9px rgba(0,0,0,.55);}}
    """
    return _doc(f'<div class="sec nv2">{pill}<div class="body">{body_html}</div></div>', style)


def _section_nv3(title: str, emoji: str, body: list[str]) -> str:
    lines = "".join(f'<div class="ln">{_esc(t)}</div>' for t in body)
    style = f"""
    .sec{{position:absolute;top:118px;left:0;width:100%;}}
    .qbar{{position:relative;width:{W-150}px;margin:0 auto 24px;height:4px;background:#2E9E5B;}}
    .badge{{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);
        width:82px;height:82px;border-radius:50%;background:#2E9E5B;
        display:flex;align-items:center;justify-content:center;}}
    .badge span{{color:#fff;font-family:'BVP',serif;font-weight:800;font-size:70px;line-height:1;
        margin-top:20px;}}
    .lines{{display:flex;flex-direction:column;align-items:center;gap:11px;}}
    .ln{{display:inline-block;background:rgba(0,0,0,0.66);border-radius:11px;padding:6px 24px;
        font-family:'BVP',{_EMOJI_STACK};font-weight:700;font-size:46px;color:#fff;line-height:1.28;
        text-align:center;text-shadow:0 1px 3px rgba(0,0,0,.9);}}
    """
    body_html = f'<div class="qbar"><div class="badge"><span>&#10077;</span></div></div><div class="lines">{lines}</div>'
    return _doc(f'<div class="sec nv3">{body_html}</div>', style)


# ─────────────────────────────────────────────────────────────────────────────
# Dispatch + render
# ─────────────────────────────────────────────────────────────────────────────

def build_html(job: dict) -> str:
    kind = job.get("kind")
    style = job.get("style", "nv2")
    if kind == "hook":
        lines = [l for l in (job.get("lines") or []) if l]
        return _hook_nv2(lines) if style == "nv2" else _hook_nv3(lines)
    if kind == "section":
        title = job.get("title", "")
        emoji = job.get("emoji", "")
        body = [b for b in (job.get("body") or []) if b]
        if style == "nv2":
            return _section_nv2(title, emoji, body,
                                align=job.get("align", "left"), no_pill=bool(job.get("no_pill")))
        return _section_nv3(title, emoji, body)
    raise ValueError(f"kind không hỗ trợ: {kind}")


def render_pngs(jobs: list[dict]) -> None:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--force-color-profile=srgb"])
        page = browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        for job in jobs:
            page.set_content(build_html(job), wait_until="load")
            page.wait_for_timeout(120)  # font/emoji settle
            page.screenshot(path=job["out"], omit_background=True,
                            clip={"x": 0, "y": 0, "width": W, "height": H})
        browser.close()


def _selftest(out_dir: str) -> None:
    d = Path(out_dir); d.mkdir(parents=True, exist_ok=True)
    jobs = [
        {"kind": "hook", "style": "nv2", "out": str(d / "nv2_hook.png"),
         "lines": ["NGƯỜI MỚI ĐI ĐÀ LẠT VỀ", "KHUYÊN NGƯỜI SẮP ĐI"]},
        {"kind": "section", "style": "nv2", "out": str(d / "nv2_sec.png"),
         "title": "Chỗ ở", "emoji": "🏡🌳",
         "body": ["500k/ đêm có được chiếc phòng", "đầy đủ tiện nghi, gần trung tâm", "Cozy Garden 📍 94 Lữ Gia"]},
        {"kind": "hook", "style": "nv3", "out": str(d / "nv3_hook.png"),
         "lines": ["Cập nhật tình hình", "Đà lạt tháng 5"]},
        {"kind": "section", "style": "nv3", "out": str(d / "nv3_sec.png"),
         "title": "", "emoji": "",
         "body": ["Đà Lạt đang vào mùa mưa nhẹ nhàng", "Sáng vẫn có nắng nhưng tới trưa chiều", "Dễ mưa lắm nha"]},
    ]
    render_pngs(jobs)
    print("selftest OK:", [j["out"] for j in jobs])


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "selftest":
        _selftest(sys.argv[2])
    elif len(sys.argv) >= 2:
        jobs = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        render_pngs(jobs)
        print(f"rendered {len(jobs)} overlay(s)")
    else:
        print("usage: python -m tools.html_overlay <jobs.json> | selftest <out_dir>")
