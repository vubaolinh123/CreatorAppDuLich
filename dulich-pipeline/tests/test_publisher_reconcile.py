from __future__ import annotations

import server
from tools import publisher
from tools.pipeline_store import PipelineStore


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
        self.text = str(payload)

    def json(self):
        return self._payload


def test_zernio_create_uses_idempotency_header(monkeypatch):
    captured = {}

    def fake_post(url, **kwargs):
        captured.update({"url": url, **kwargs})
        return FakeResponse(
            200,
            {
                "existingPost": {
                    "_id": "post-1",
                    "status": "publishing",
                    "platforms": [{"platform": "tiktok", "status": "pending"}],
                }
            },
        )

    monkeypatch.setattr("requests.post", fake_post)
    result = publisher._zernio_post(
        [{"type": "video", "url": "https://example.test/video.mp4"}],
        "caption",
        api_key="secret",
        account_id="account-1",
        request_id="request-uuid",
    )
    assert result["id"] == "post-1"
    assert result["deduplicated"] is True
    assert captured["headers"]["x-request-id"] == "request-uuid"


def test_reconcile_published_provider_resolves_unknown_job(tmp_path, monkeypatch):
    store = PipelineStore(tmp_path / "pipeline.sqlite3", tmp_path / "uploads")
    store.mark_resource_migration_done("video")
    store.insert_resource(
        "video",
        {
            "id": "video-1",
            "user": "nv1",
            "status": "unknown",
            "video_url": "/output/videos/one.mp4",
            "zernio_post_id": "post-1",
            "zernio_ki": 0,
        },
    )
    job, _ = store.create_job(
        kind="publish_video",
        owner="nv1",
        payload={"resource_id": "video-1", "zernio_ki": 0},
    )
    running = store.claim_next("network-worker")
    store.fail_job(
        running["id"],
        "network-worker",
        "timeout",
        uncertain=True,
    )

    monkeypatch.setattr(server, "PIPELINE_STORE", store)
    monkeypatch.setattr(server, "_user_zernio", lambda user, ki=0: "key")
    monkeypatch.setattr(server, "_archive_video", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        publisher,
        "get_zernio_post",
        lambda *args, **kwargs: {
            "success": True,
            "id": "post-1",
            "provider_status": "published",
            "platform_url": "https://tiktok.example/post-1",
            "provider_post": {
                "status": "published",
                "platforms": [
                    {
                        "platform": "tiktok",
                        "status": "published",
                        "platformPostUrl": "https://tiktok.example/post-1",
                    }
                ],
            },
        },
    )

    result = server._reconcile_publish_resource("video", "video-1", job=job)
    assert result["status"] == "posted"
    assert store.get_resource("video", "video-1")["status"] == "posted"
    assert store.get_job(job["id"])["status"] == "done"


def test_reconcile_failed_provider_reopens_done_job_for_safe_retry(
    tmp_path, monkeypatch
):
    store = PipelineStore(tmp_path / "pipeline.sqlite3", tmp_path / "uploads")
    store.mark_resource_migration_done("album")
    store.insert_resource(
        "album",
        {
            "id": "album-1",
            "user": "nv1",
            "status": "publishing",
            "zernio_post_id": "post-2",
            "images": [],
        },
    )
    job, _ = store.create_job(
        kind="publish_album",
        owner="nv1",
        payload={"resource_id": "album-1"},
    )
    running = store.claim_next("network-worker")
    store.complete_job(running["id"], "network-worker", {"status": "publishing"})

    monkeypatch.setattr(server, "PIPELINE_STORE", store)
    monkeypatch.setattr(server, "_user_zernio", lambda user, ki=0: "key")
    monkeypatch.setattr(
        publisher,
        "get_zernio_post",
        lambda *args, **kwargs: {
            "success": True,
            "id": "post-2",
            "provider_status": "failed",
            "provider_post": {
                "status": "failed",
                "platforms": [
                    {"platform": "tiktok", "status": "failed", "error": "bad media"}
                ],
            },
        },
    )

    result = server._reconcile_publish_resource("album", "album-1", job=job)
    assert result["status"] == "failed"
    assert store.get_resource("album", "album-1")["status"] == "failed"
    assert store.get_job(job["id"])["status"] == "failed"
