"""Backup legacy JSON and initialize/export the transactional pipeline database."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _backup(path: Path, backup_dir: Path) -> None:
    if path.is_file():
        backup_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup_dir / path.name)


def migrate() -> dict:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    backup_dir = ROOT / "data" / "migration-backups" / stamp
    for path in (
        ROOT / "output" / "products.json",
        ROOT / "output" / "album_products.json",
        ROOT / "data" / "script_drafts.json",
        ROOT / "data" / "venues.json",
        ROOT / "data" / "album_images.json",
    ):
        _backup(path, backup_dir)

    import server
    from tools import script_drafts

    products = server._load_products()
    albums = server._load_albums()
    drafts = script_drafts.list_drafts()
    return {
        "database": str(server.PIPELINE_STORE.db_path),
        "backup": str(backup_dir),
        "products": len(products),
        "albums": len(albums),
        "drafts": len(drafts),
    }


def export() -> dict:
    from tools.pipeline_store import get_pipeline_store

    store = get_pipeline_store()
    export_dir = ROOT / "data" / "pipeline-export"
    export_dir.mkdir(parents=True, exist_ok=True)
    mapping = {
        "video": export_dir / "products.json",
        "album": export_dir / "album_products.json",
        "draft": export_dir / "script_drafts.json",
    }
    counts = {}
    for kind, path in mapping.items():
        items = store.list_resources(kind)
        path.write_text(
            json.dumps(items, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        counts[kind] = len(items)
    return {"directory": str(export_dir), "counts": counts}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--export", action="store_true")
    args = parser.parse_args()
    result = export() if args.export else migrate()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
