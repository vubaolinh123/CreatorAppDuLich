"""Backfill thumbnail + bản preview 480p cho video cũ trong output/products.json.

Chạy từ thư mục dulich-pipeline:  python -X utf8 scratch/backfill_media.py
Chạy lại nhiều lần được (bỏ qua file đã có). Không xoá gì.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
PRODUCTS = ROOT / "output" / "products.json"


def url_of(p: Path) -> str:
    return "/" + p.relative_to(ROOT).as_posix()


def make_thumb(src: Path) -> Path | None:
    dst = src.with_suffix(".jpg")
    if dst.exists():
        return dst
    r = subprocess.run(["ffmpeg", "-y", "-ss", "1", "-i", str(src), "-frames:v", "1",
                        "-vf", "scale=360:-2", "-q:v", "5", str(dst)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  thumb lỗi: {r.stderr[-300:]}")
        return None
    return dst if dst.exists() else None


def main():
    items = json.loads(PRODUCTS.read_text(encoding="utf-8"))
    from tools.list_review_render import make_preview

    changed = 0
    for i, rec in enumerate(items, 1):
        vurl = (rec.get("video_url") or "").lstrip("/")
        if not vurl:
            continue
        src = ROOT / vurl
        if not src.exists() or src.suffix.lower() != ".mp4":
            continue
        name = src.name
        if src.stem.endswith("_preview"):
            continue

        t = ROOT / (rec.get("thumb_url") or "").lstrip("/") if rec.get("thumb_url") else None
        if t is None or not t.exists():
            print(f"[{i}/{len(items)}] thumb {name}")
            got = make_thumb(src)
            if got:
                rec["thumb_url"] = url_of(got)
                changed += 1

        p = ROOT / (rec.get("preview_url") or "").lstrip("/") if rec.get("preview_url") else None
        if p is None or not p.exists():
            cand = src.with_name(src.stem + "_preview.mp4")
            if cand.exists():
                rec["preview_url"] = url_of(cand)
                changed += 1
            else:
                print(f"[{i}/{len(items)}] preview {name} ({src.stat().st_size/1e6:.1f}MB)")
                got = make_preview(src)
                if got:
                    rec["preview_url"] = url_of(got)
                    changed += 1
                    print(f"    -> {got.stat().st_size/1e6:.1f}MB")

    if changed:
        PRODUCTS.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Xong. Cập nhật {changed} trường.")


if __name__ == "__main__":
    main()
