"""Create consistent SQLite snapshots and optionally copy them to private Drive."""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import time
from contextlib import closing
from pathlib import Path

try:
    from .atomic_json import atomic_write_json
except ImportError:
    from atomic_json import atomic_write_json


ROOT = Path(__file__).resolve().parent.parent
try:
    from dotenv import load_dotenv

    env_file = Path(
        os.getenv("PIPELINE_ENV_PATH") or (ROOT / ".env")
    ).resolve()
    if env_file.exists():
        load_dotenv(env_file)
except Exception:
    pass

BACKUP_ROOT = ROOT / "data" / "backups"
STATUS_FILE = BACKUP_ROOT / "status.json"
DATABASES = {
    "auth": Path(
        os.getenv("AUTH_DB_PATH") or (ROOT / "data" / "auth.sqlite3")
    ).resolve(),
    "pipeline": Path(
        os.getenv("PIPELINE_DB_PATH") or (ROOT / "data" / "pipeline.sqlite3")
    ).resolve(),
}


def _snapshot(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.unlink(missing_ok=True)
    try:
        with closing(sqlite3.connect(source)) as source_db:
            with closing(sqlite3.connect(temporary)) as backup_db:
                source_db.backup(backup_db)
                result = str(
                    backup_db.execute("PRAGMA quick_check(1)").fetchone()[0]
                ).lower()
                if result != "ok":
                    raise RuntimeError(
                        f"SQLite quick_check failed for {source.name}: {result}"
                    )
        os.replace(temporary, destination)
        try:
            os.chmod(destination, 0o600)
        except OSError:
            pass
    finally:
        temporary.unlink(missing_ok=True)


def _prune(retention_days: int) -> int:
    cutoff = time.time() - max(1, retention_days) * 86400
    removed = 0
    if not BACKUP_ROOT.exists():
        return 0
    for item in BACKUP_ROOT.glob("*.sqlite3"):
        if item.stat().st_mtime < cutoff:
            item.unlink(missing_ok=True)
            removed += 1
    return removed


def backup_databases(
    *,
    retention_days: int = 14,
    upload_drive: bool = False,
) -> dict:
    now = time.time()
    stamp = time.strftime("%Y%m%d-%H%M%S")
    created: list[Path] = []
    missing: list[str] = []
    errors: list[str] = []
    for name, source in DATABASES.items():
        if not source.exists():
            missing.append(name)
            continue
        destination = BACKUP_ROOT / f"{name}-{stamp}.sqlite3"
        try:
            _snapshot(source, destination)
            created.append(destination)
        except Exception as exc:
            errors.append(f"{name}: {exc}")

    drive = {"requested": upload_drive, "ok": False, "files": 0}
    if upload_drive and created and not errors:
        try:
            try:
                from .drive_uploader import get_drive_uploader
            except ImportError:
                from drive_uploader import get_drive_uploader

            uploader = get_drive_uploader()
            folder_id = uploader.create_subfolder(
                f"database-backups/{time.strftime('%Y-%m-%d')}"
            )
            if not folder_id:
                raise RuntimeError("Drive backup folder is unavailable")
            uploaded = 0
            for item in created:
                result = uploader.upload_file(
                    str(item),
                    folder_id,
                    make_public=False,
                )
                if result.get("error"):
                    raise RuntimeError(str(result["error"]))
                uploaded += 1
            drive = {
                "requested": True,
                "ok": uploaded == len(created),
                "files": uploaded,
                "folder_id": folder_id,
            }
        except Exception as exc:
            drive = {
                "requested": True,
                "ok": False,
                "files": 0,
                "error": str(exc),
            }

    pruned = _prune(retention_days)
    status = {
        "timestamp": now,
        "ok": bool(created) and not errors,
        "created": [item.name for item in created],
        "missing": missing,
        "errors": errors,
        "drive": drive,
        "pruned": pruned,
    }
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    atomic_write_json(STATUS_FILE, status)
    try:
        os.chmod(STATUS_FILE, 0o600)
    except OSError:
        pass
    return status


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--retention-days", type=int, default=14)
    parser.add_argument("--upload-drive", action="store_true")
    args = parser.parse_args()
    result = backup_databases(
        retention_days=args.retention_days,
        upload_drive=args.upload_drive,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["ok"]:
        return 1
    if args.upload_drive and not result["drive"]["ok"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
