from __future__ import annotations

import json
import sqlite3
import time

import server
from tools import backup_sqlite
from tools.auth_store import AuthStore
from tools.pipeline_store import PipelineStore


def _database(path, value):
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE sample(value TEXT)")
        db.execute("INSERT INTO sample(value) VALUES(?)", (value,))


def test_consistent_sqlite_backup_and_private_drive_copy(tmp_path, monkeypatch):
    auth_db = tmp_path / "auth.sqlite3"
    pipeline_db = tmp_path / "pipeline.sqlite3"
    _database(auth_db, "auth")
    _database(pipeline_db, "pipeline")
    backup_root = tmp_path / "backups"

    monkeypatch.setattr(
        backup_sqlite,
        "DATABASES",
        {"auth": auth_db, "pipeline": pipeline_db},
    )
    monkeypatch.setattr(backup_sqlite, "BACKUP_ROOT", backup_root)
    monkeypatch.setattr(
        backup_sqlite,
        "STATUS_FILE",
        backup_root / "status.json",
    )

    uploads = []

    class FakeDrive:
        def create_subfolder(self, name):
            assert name.startswith("database-backups/")
            return "backup-folder"

        def upload_file(self, path, folder_id, *, make_public):
            uploads.append((path, folder_id, make_public))
            return {"id": f"file-{len(uploads)}"}

    monkeypatch.setattr(
        "tools.drive_uploader.get_drive_uploader",
        lambda: FakeDrive(),
    )
    result = backup_sqlite.backup_databases(upload_drive=True)

    assert not result["errors"], result["errors"]
    assert result["ok"] is True, result
    assert result["drive"]["ok"] is True
    assert len(uploads) == 2
    assert all(item[2] is False for item in uploads)
    for item in backup_root.glob("*.sqlite3"):
        with sqlite3.connect(item) as db:
            assert db.execute("PRAGMA quick_check(1)").fetchone()[0] == "ok"


def test_health_requires_worker_auth_database_and_disk(tmp_path, monkeypatch):
    pipeline = PipelineStore(
        tmp_path / "pipeline.sqlite3",
        tmp_path / "uploads",
    )
    pipeline.set_meta(
        "worker_heartbeat",
        json.dumps(
            {
                "timestamp": time.time(),
                "queue": "all",
                "workers": 3,
            }
        ),
    )
    pipeline.set_meta("maintenance_last_success", str(time.time()))

    auth = AuthStore(tmp_path / "auth.sqlite3")
    auth.import_users(
        {
            "admin": {"password": "p-admin", "role": "admin"},
            **{
                f"nv{i}": {"password": f"p-{i}", "role": "staff"}
                for i in range(1, 6)
            },
        }
    )
    backup_status = tmp_path / "backup-status.json"
    backup_status.write_text(
        json.dumps(
            {
                "timestamp": time.time(),
                "ok": True,
                "drive": {"ok": True},
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(server, "PIPELINE_STORE", pipeline)
    monkeypatch.setattr(server, "AUTH_STORE", auth)
    monkeypatch.setattr(server, "BACKUP_STATUS_FILE", backup_status)
    monkeypatch.setattr(server, "UPLOAD_DISK_RESERVE_BYTES", 0)
    healthy, status = server._health_snapshot()
    assert status == 200
    assert healthy["status"] == "ok"
    assert healthy["checks"]["worker"]["workers"] == 3

    pipeline.set_meta(
        "worker_heartbeat",
        json.dumps({"timestamp": time.time() - 120, "workers": 3}),
    )
    unhealthy, status = server._health_snapshot()
    assert status == 503
    assert "worker" in unhealthy["errors"]
