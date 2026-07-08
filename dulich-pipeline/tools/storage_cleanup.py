"""
storage_cleanup.py — Giải phóng disk: output/ cũ hơn N ngày (mặc định 5)
→ upload lên Google Drive (DuLichApp/archive/...) → upload OK mới xóa local.
Upload fail → GIỮ file, log lại. Manifest lưu ở data/archive_manifest.json.

Usage:
  python -X utf8 tools/storage_cleanup.py --dry-run
  python -X utf8 tools/storage_cleanup.py --days 5
"""
from __future__ import annotations
import argparse, json, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

ROOT = Path(__file__).parent.parent
OUTPUT = ROOT / "output"
MANIFEST = ROOT / "data" / "archive_manifest.json"


def _old_dirs(days: int) -> list[Path]:
    """Các folder con cấp 1-2 trong output/ có mtime mới nhất cũ hơn N ngày."""
    cutoff = time.time() - days * 86400
    found = []
    if not OUTPUT.exists():
        return found
    for sub in OUTPUT.iterdir():
        if not sub.is_dir():
            if sub.stat().st_mtime < cutoff:
                found.append(sub)
            continue
        for d in sub.iterdir():
            if d.is_dir():
                try:
                    newest = max((f.stat().st_mtime for f in d.rglob("*") if f.is_file()),
                                 default=d.stat().st_mtime)
                except OSError:
                    newest = d.stat().st_mtime
                if newest < cutoff:
                    found.append(d)
            elif d.stat().st_mtime < cutoff:
                found.append(d)
    return found


def _load_manifest() -> dict:
    try:
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_manifest(m: dict) -> None:
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")


def run(days: int = 5, dry_run: bool = False) -> dict:
    targets = _old_dirs(days)
    if not targets:
        print(f"[cleanup] Không có gì cũ hơn {days} ngày.")
        return {"archived": 0, "failed": 0}
    if dry_run:
        for t in targets:
            print(f"[dry-run] sẽ archive: {t.relative_to(ROOT)}")
        return {"archived": 0, "failed": 0, "candidates": len(targets)}

    from tools.drive_uploader import get_drive_uploader
    up = get_drive_uploader()
    manifest = _load_manifest()
    ok = fail = 0
    for t in targets:
        rel = str(t.relative_to(ROOT)).replace("\\", "/")
        folder_id = up.create_subfolder(f"archive/{rel}")
        if not folder_id:
            print(f"[cleanup] ✗ Không tạo được folder Drive cho {rel} → giữ local")
            fail += 1
            continue
        files = [t] if t.is_file() else [f for f in t.rglob("*") if f.is_file()]
        links, all_ok = {}, True
        for f in files:
            res = up.upload_file(str(f), folder_id)
            if res.get("error"):
                all_ok = False
                print(f"[cleanup] ✗ Upload fail {f.name}: {res['error']}")
                break
            links[f.name] = res.get("webViewLink", "")
        if not all_ok:
            fail += 1
            continue
        import shutil
        if t.is_dir():
            shutil.rmtree(t, ignore_errors=True)
        else:
            t.unlink(missing_ok=True)
        manifest[rel] = {"archived_at": time.strftime("%Y-%m-%d %H:%M"),
                         "drive_folder": folder_id, "files": links}
        ok += 1
        print(f"[cleanup] ✓ Archived + xóa local: {rel} ({len(files)} file)")
    _save_manifest(manifest)
    print(f"[cleanup] Xong: {ok} archived, {fail} lỗi (giữ local).")
    return {"archived": ok, "failed": fail}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=5)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    run(a.days, a.dry_run)
