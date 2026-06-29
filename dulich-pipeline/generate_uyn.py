"""
generate_uyn.py — Generate UYN-style album: 7 slides.
Usage: python -X utf8 generate_uyn.py [--seed N] [--out path]

Slides:
  00_cover    — pure scenic photo
  01_hook     — photo + sticker text
  02_checkin  — 2x2 grid tham quan
  03_cafe     — 2x2 grid quán cà phê
  04_play     — 2x2 grid activities (tham quan)
  05_food     — 2x2 grid quán ăn
  06_snacks   — 2x2 grid quán ăn (desserts/snacks)
"""
from __future__ import annotations
import sys, random, argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from tools.venue_picker import VenuePicker
from tools.uyn_renderer import (
    render_cover, render_intro_hook, render_grid_slide,
    HOOK_TEXTS,
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
    p = THUMBS / f"{name}.jpg"
    if p.exists():
        return str(p)
    img = venue.get("image_path", "")
    if img:
        alt = THUMBS / Path(img).name
        if alt.exists():
            return str(alt)
    return ""


def _fill4(cat: str, fallback: str | None = None, seed: int | None = None) -> list:
    """Each grid slide picks independently — no shared used-set between slides."""
    picker = VenuePicker(seed=seed)
    avail = [v for v in picker._all if v.get("loai_quan") == cat]
    items = picker.pick_n(min(4, len(avail)), loai_quan=cat)
    if len(items) < 4:
        fb_cat = fallback or "quán ăn"
        items += picker.pick_n(4 - len(items), loai_quan=fb_cat)
    result = []
    for v in items[:4]:
        result.append({**v, "_resolved_path": _resolve_thumb(v)})
    return result


GRID_SLIDES = [
    ("checkin",  "Đi check-in free",       "tham quan",    "quán cà phê"),
    ("cafe",     "Đi cafe vibe DL",         "quán cà phê",  "quán ăn"),
    ("play",     "Đi chơi",                 "tham quan",    None),
    ("food",     "Đi ănggg",                "quán ăn",      "quán cà phê"),
    ("snacks",   "Đi ăn vặt",               "quán ăn",      None),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--out", default="")
    args = parser.parse_args()
    if args.seed is not None:
        random.seed(args.seed)

    out_dir = args.out or str(Path(__file__).parent / "output" / "albums" / "uyn_demo")
    p = Path(out_dir)
    paths = []

    # Cover — pure photo
    out0 = str(p / "uyn_00_cover.png")
    print(f"[1/7] Cover → {out0}")
    paths.append(render_cover(_pick_bg(), out0))

    # Hook slide
    out1 = str(p / "uyn_01_hook.png")
    hook = random.choice(HOOK_TEXTS)
    print(f"[2/7] Hook → {out1}")
    paths.append(render_intro_hook(_pick_bg(), hook, out1))

    # Grid slides — each uses its own fresh picker so venues don't conflict across slides
    for i, (slug, label, cat, fallback) in enumerate(GRID_SLIDES, start=3):
        seed_i = (args.seed or 0) + i if args.seed is not None else None
        venues = _fill4(cat, fallback, seed=seed_i)
        out_n = str(p / f"uyn_{i-1:02d}_{slug}.png")
        print(f"[{i}/7] {label} grid → {out_n}")
        paths.append(render_grid_slide(venues, label, out_n))

    print(f"\n✓ Album xong — {len(paths)} slides:")
    for s in paths:
        print(f"  file:///{Path(s).as_posix()}")


if __name__ == "__main__":
    main()
