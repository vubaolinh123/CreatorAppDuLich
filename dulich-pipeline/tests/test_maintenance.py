from __future__ import annotations

import os
import time

from tools.maintenance import run_maintenance
from tools.pipeline_store import PipelineStore
from tools import storage_cleanup


def test_maintenance_cleans_expired_uploads_and_runs_output_archive(
    tmp_path, monkeypatch
):
    store = PipelineStore(tmp_path / "pipeline.sqlite3", tmp_path / "uploads")
    session = store.create_upload_session(
        owner="nv1",
        kind="personal_video",
        files=[
            {
                "field": "scene1__0",
                "name": "clip.mp4",
                "type": "video/mp4",
                "size": 4,
            }
        ],
        max_file_bytes=100,
        max_job_bytes=100,
        max_active_sessions=2,
        reserve_free_bytes=0,
    )
    old = time.time() - 3 * 3600
    with store._connect() as conn:
        conn.execute(
            "UPDATE upload_sessions SET updated_at=? WHERE id=?",
            (old, session["id"]),
        )

    result_dir = store.db_path.parent / "job-results"
    result_dir.mkdir()
    stale_result = result_dir / "stale.json"
    stale_result.write_text("{}", encoding="utf-8")
    os.utime(stale_result, (old, old))

    archived = []

    def fake_archive(*, days, store):
        archived.append(days)
        assert store.db_path == tmp_path / "pipeline.sqlite3"
        return {"archived": 2, "failed": 0}

    monkeypatch.setattr("tools.storage_cleanup.run", fake_archive)
    result = run_maintenance(
        store,
        upload_ttl_hours=1,
        output_retention_days=5,
        archive_output=True,
    )

    assert result["uploads_removed"] == 1
    assert result["job_results_removed"] == 1
    assert result["output"]["archived"] == 2
    assert archived == [5]
    assert not (store.upload_root / session["id"]).exists()
    assert not stale_result.exists()


def test_output_archive_updates_transactional_video_resource(tmp_path, monkeypatch):
    output = tmp_path / "output"
    video = output / "videos" / "old.mp4"
    video.parent.mkdir(parents=True)
    video.write_bytes(b"video")
    old = time.time() - 6 * 86400
    os.utime(video, (old, old))

    store = PipelineStore(tmp_path / "pipeline.sqlite3", tmp_path / "uploads")
    store.insert_resource(
        "video",
        {
            "id": "video-old",
            "user": "nv1",
            "status": "posted",
            "video_url": "/output/videos/old.mp4",
            "time": old,
        },
    )

    class FakeDrive:
        def create_subfolder(self, name):
            return "folder-1"

        def upload_file(self, path, folder_id):
            return {"webViewLink": "https://drive.example/old"}

    monkeypatch.setattr(storage_cleanup, "ROOT", tmp_path)
    monkeypatch.setattr(storage_cleanup, "OUTPUT", output)
    monkeypatch.setattr(
        storage_cleanup,
        "MANIFEST",
        tmp_path / "data" / "archive_manifest.json",
    )
    monkeypatch.setattr(
        "tools.drive_uploader.get_drive_uploader",
        lambda: FakeDrive(),
    )

    result = storage_cleanup.run(days=5, store=store)
    resource = store.get_resource("video", "video-old")
    assert result == {"archived": 1, "failed": 0}
    assert not video.exists()
    assert resource["archived"] is True
    assert resource["drive_link"] == "https://drive.example/old"
