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
from tools.atomic_json import atomic_write_json

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
    atomic_write_json(MANIFEST, m)


def _mark_video_resources_archived(
    store,
    target: Path,
    links: dict,
    folder_id: str,
    *,
    target_was_dir: bool,
) -> None:
    if store is None:
        return
    target = target.resolve()
    for record in store.list_resources("video"):
        local_url = str(record.get("video_url") or "")
        if not local_url:
            continue
        local = (ROOT / local_url.lstrip("/")).resolve()
        matches = local == target or (target_was_dir and target in local.parents)
        if not matches:
            continue
        store.update_resource(
            "video",
            record["id"],
            archived=True,
            archived_at=time.time(),
            drive_link=links.get(local.name, record.get("drive_link", "")),
            drive_folder_id=folder_id,
        )


def run(days: int = 5, dry_run: bool = False, store=None) -> dict:
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
        target_was_dir = t.is_dir()
        if target_was_dir:
            shutil.rmtree(t, ignore_errors=True)
        else:
            t.unlink(missing_ok=True)
        manifest[rel] = {"archived_at": time.strftime("%Y-%m-%d %H:%M"),
                         "drive_folder": folder_id, "files": links}
        _mark_video_resources_archived(
            store,
            t,
            links,
            folder_id,
            target_was_dir=target_was_dir,
        )
        ok += 1
        print(f"[cleanup] ✓ Archived + xóa local: {rel} ({len(files)} file)")
    _save_manifest(manifest)
    print(f"[cleanup] Xong: {ok} archived, {fail} lỗi (giữ local).")
    return {"archived": ok, "failed": fail}


def archive_posted_now(dry_run: bool = False) -> dict:
    """Video status=posted chưa archived → upload Drive (posted/YYYY-MM) + xóa local NGAY."""
    import time
    prod_file = ROOT / "output" / "products.json"
    try:
        items = json.loads(prod_file.read_text(encoding="utf-8"))
    except Exception:
        print("[cleanup] không đọc được products.json")
        return {"archived": 0}
    targets = [p for p in items
               if p.get("status") == "posted" and not p.get("archived")
               and (ROOT / (p.get("video_url") or "x").lstrip("/")).exists()]
    if not targets:
        print("[cleanup] không có video posted nào cần archive.")
        return {"archived": 0}
    if dry_run:
        for p in targets:
            print(f"[dry-run] sẽ đẩy Drive + xóa: {p['video_url']}")
        return {"archived": 0, "candidates": len(targets)}
    from tools.drive_uploader import get_drive_uploader
    up = get_drive_uploader()
    folder = up.create_subfolder(f"posted/{time.strftime('%Y-%m')}")
    ok = 0
    for p in targets:
        local = ROOT / p["video_url"].lstrip("/")
        res = up.upload_file(str(local), folder)
        if res.get("error"):
            print(f"[cleanup] ✗ {p['video_url']}: {str(res['error'])[:100]} → giữ")
            continue
        p["drive_link"] = res.get("webViewLink", "")
        p["archived"] = True
        local.unlink(missing_ok=True)
        # bản preview 480p đi kèm — cùng vòng đời với bản gốc
        local.with_name(local.stem + "_preview.mp4").unlink(missing_ok=True)
        ok += 1
        print(f"[cleanup] ✓ Drive + xóa: {p['video_url']}")
    prod_file.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[cleanup] posted-now xong: {ok}/{len(targets)}")
    return {"archived": ok}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=5)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--posted-now", action="store_true",
                    help="đẩy Drive + xóa NGAY các video đã đăng (không chờ 5 ngày)")
    a = ap.parse_args()
    if a.posted_now:
        archive_posted_now(a.dry_run)
    else:
        run(a.days, a.dry_run)
