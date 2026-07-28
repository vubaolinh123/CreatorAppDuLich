from __future__ import annotations

import io
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from tools.pipeline_store import (
    PipelineStore,
    QueueLimitError,
    UploadValidationError,
)


@pytest.fixture()
def store(tmp_path):
    return PipelineStore(tmp_path / "pipeline.sqlite3", tmp_path / "uploads")


def test_job_idempotency_is_safe_under_concurrency(store):
    def create(_):
        job, created = store.create_job(
            kind="publish_video",
            owner="admin",
            payload={"resource_id": "video-1"},
            idempotency_key="publish:video:video-1:account-1",
        )
        return job["id"], created

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(create, range(20)))

    assert len({job_id for job_id, _ in results}) == 1
    assert sum(1 for _, created in results if created) == 1


def test_owner_active_job_limit_and_fair_claim(store):
    first, _ = store.create_job(
        kind="video", owner="nv1", payload={"n": 1}, active_limit=2
    )
    store.create_job(kind="video", owner="nv1", payload={"n": 2}, active_limit=2)
    with pytest.raises(QueueLimitError):
        store.create_job(kind="video", owner="nv1", payload={"n": 3}, active_limit=2)

    other, _ = store.create_job(
        kind="video", owner="nv2", payload={"n": 1}, active_limit=2
    )
    worker = "worker-test"
    claimed1 = store.claim_next(worker)
    assert claimed1["id"] == first["id"]
    store.complete_job(claimed1["id"], worker, {"ok": True})

    # nv2 has never run, so fair scheduling picks nv2 before nv1's second job.
    claimed2 = store.claim_next(worker)
    assert claimed2["id"] == other["id"]


def test_stale_running_job_is_recovered(store):
    job, _ = store.create_job(kind="video", owner="nv1", payload={})
    claimed = store.claim_next("dead-worker")
    assert claimed["id"] == job["id"]
    with store._connect() as conn:
        conn.execute(
            "UPDATE jobs SET heartbeat_at=1, updated_at=1 WHERE id=?", (job["id"],)
        )
    result = store.recover_stale_jobs(30)
    assert result["recovered"] == 1
    assert store.get_job(job["id"])["status"] == "queued"


def test_stale_publish_is_unknown_and_never_auto_replayed(store):
    job, _ = store.create_job(
        kind="publish_video",
        owner="nv1",
        payload={"resource_id": "v1"},
        max_attempts=2,
    )
    store.claim_next("dead-network-worker")
    with store._connect() as conn:
        conn.execute(
            "UPDATE jobs SET heartbeat_at=1, updated_at=1 WHERE id=?", (job["id"],)
        )
    result = store.recover_stale_jobs(30)
    recovered = store.get_job(job["id"])
    assert result["recovered"] == 0
    assert recovered["status"] == "unknown"
    assert "kiểm tra" in recovered["error"]


def test_recent_stale_publish_with_request_id_gets_one_safe_retry(store):
    job, _ = store.create_job(
        kind="publish_video",
        owner="nv1",
        payload={"resource_id": "v1", "provider_request_id": "stable-request"},
        max_attempts=2,
    )
    store.claim_next("dead-network-worker")
    with store._connect() as conn:
        conn.execute(
            "UPDATE jobs SET heartbeat_at=1 WHERE id=?",
            (job["id"],),
        )
    result = store.recover_stale_jobs(30)
    recovered = store.get_job(job["id"])
    assert result["recovered"] == 1
    assert recovered["status"] == "queued"


def test_manual_retry_respects_owner_limit(store):
    failed, _ = store.create_job(kind="video", owner="nv1", payload={})
    claimed = store.claim_next("worker")
    store.fail_job(claimed["id"], "worker", "bad input")
    store.create_job(kind="video", owner="nv1", payload={"n": 1})
    store.create_job(kind="video", owner="nv1", payload={"n": 2})
    with pytest.raises(QueueLimitError):
        store.retry_job(failed["id"], "nv1", active_limit=2)


def test_chunk_upload_writes_exact_offsets_without_buffering_whole_job(store):
    session = store.create_upload_session(
        owner="nv1",
        kind="listreview_video",
        files=[
            {
                "field": "intro__0",
                "name": "clip.mp4",
                "type": "video/mp4",
                "size": 10,
            }
        ],
        max_file_bytes=100,
        max_job_bytes=100,
        max_active_sessions=2,
        reserve_free_bytes=0,
    )
    file_id = session["files"][0]["id"]
    one = store.append_upload_chunk(
        session_id=session["id"],
        file_id=file_id,
        owner="nv1",
        offset=0,
        length=4,
        source=io.BytesIO(b"1234"),
        max_chunk_bytes=8,
    )
    assert one["received"] == 4
    with pytest.raises(UploadValidationError, match="Offset"):
        store.append_upload_chunk(
            session_id=session["id"],
            file_id=file_id,
            owner="nv1",
            offset=0,
            length=2,
            source=io.BytesIO(b"xx"),
            max_chunk_bytes=8,
        )
    two = store.append_upload_chunk(
        session_id=session["id"],
        file_id=file_id,
        owner="nv1",
        offset=4,
        length=6,
        source=io.BytesIO(b"567890"),
        max_chunk_bytes=8,
    )
    assert two["complete"] is True
    complete = store.complete_upload(session["id"], "nv1")
    assert complete["status"] == "ready"
    consumed = store.consume_upload(session["id"], "nv1", "job-1")
    assert consumed["files"][0]["path"]
    with pytest.raises(UploadValidationError, match="trạng thái"):
        store.complete_upload(session["id"], "nv1")


def test_four_upload_jobs_are_reserved_idempotently_and_queue_after_complete(store):
    sessions = []
    for index in range(4):
        session = store.create_upload_session(
            owner="nv1",
            kind="listreview_video",
            files=[
                {
                    "field": f"intro__{index}",
                    "name": f"clip-{index}.mp4",
                    "type": "video/mp4",
                    "size": 4,
                }
            ],
            max_file_bytes=100,
            max_job_bytes=100,
            max_active_sessions=4,
            reserve_free_bytes=0,
            payload={"topic": f"Video {index}", "hook_style": "hook_red"},
            idempotency_key=f"render-upload:nv1:req-{index:04d}",
            active_job_limit=4,
            global_active_job_limit=20,
        )
        assert session["job_status"] == "uploading"
        sessions.append(session)

    duplicate = store.create_upload_session(
        owner="nv1",
        kind="listreview_video",
        files=[
            {
                "field": "intro__0",
                "name": "clip-0.mp4",
                "type": "video/mp4",
                "size": 4,
            }
        ],
        max_file_bytes=100,
        max_job_bytes=100,
        max_active_sessions=4,
        reserve_free_bytes=0,
        payload={"topic": "Không được ghi đè"},
        idempotency_key="render-upload:nv1:req-0000",
        active_job_limit=4,
        global_active_job_limit=20,
    )
    assert duplicate["created"] is False
    assert duplicate["id"] == sessions[0]["id"]
    assert duplicate["job_id"] == sessions[0]["job_id"]

    with pytest.raises(QueueLimitError):
        store.create_upload_session(
            owner="nv1",
            kind="listreview_video",
            files=[
                {
                    "field": "intro__5",
                    "name": "clip-5.mp4",
                    "type": "video/mp4",
                    "size": 4,
                }
            ],
            max_file_bytes=100,
            max_job_bytes=100,
            max_active_sessions=4,
            reserve_free_bytes=0,
            payload={"topic": "Video 5"},
            idempotency_key="render-upload:nv1:req-0005",
            active_job_limit=4,
            global_active_job_limit=20,
        )

    first = sessions[0]
    store.append_upload_chunk(
        session_id=first["id"],
        file_id=first["files"][0]["id"],
        owner="nv1",
        offset=0,
        length=4,
        source=io.BytesIO(b"1234"),
        max_chunk_bytes=8,
    )
    assert store.complete_upload(first["id"], "nv1")["status"] == "ready"
    queued = store.queue_reserved_upload(first["id"], "nv1")
    assert queued["id"] == first["job_id"]
    assert queued["status"] == "queued"
    assert queued["payload"]["upload_files"][0]["field"] == "intro__0"


def test_resource_writes_are_transactional_under_threads(store):
    def insert(index):
        return store.insert_resource(
            "video",
            {
                "id": f"v{index}",
                "user": f"nv{index % 5 + 1}",
                "status": "pending",
                "time": index,
            },
        )

    with ThreadPoolExecutor(max_workers=10) as pool:
        list(pool.map(insert, range(100)))
    assert len(store.list_resources("video")) == 100


def test_resource_insert_once_is_idempotent(store):
    original, created = store.insert_resource_once(
        "video", {"id": "job-1", "topic": "Bản đầu", "user": "nv1"}
    )
    duplicate, created_again = store.insert_resource_once(
        "video", {"id": "job-1", "topic": "Bản trùng", "user": "nv1"}
    )
    assert created is True
    assert created_again is False
    assert duplicate == original
    assert duplicate["topic"] == "Bản đầu"


def test_six_accounts_can_enqueue_without_cross_owner_leak(store):
    owners = ["admin", "nv1", "nv2", "nv3", "nv4", "nv5"]

    def enqueue(owner):
        return store.create_job(
            kind="video",
            owner=owner,
            payload={"owner": owner},
            active_limit=2,
        )[0]

    with ThreadPoolExecutor(max_workers=12) as pool:
        jobs = list(pool.map(enqueue, owners * 2))

    assert len({job["id"] for job in jobs}) == 12
    for owner in owners:
        own_jobs = store.list_jobs(owner=owner)
        assert len(own_jobs) == 2
        assert all(job["owner"] == owner for job in own_jobs)


def test_upload_stream_is_read_in_bounded_blocks(store):
    class GuardedStream(io.BytesIO):
        def read(self, size=-1):
            assert 0 < size <= 1024 * 1024
            return super().read(size)

    size = 3 * 1024 * 1024
    session = store.create_upload_session(
        owner="nv1",
        kind="personal_video",
        files=[
            {
                "field": "scene-1__0",
                "name": "large.mp4",
                "type": "video/mp4",
                "size": size,
            }
        ],
        max_file_bytes=size,
        max_job_bytes=size,
        max_active_sessions=2,
        reserve_free_bytes=0,
    )
    store.append_upload_chunk(
        session_id=session["id"],
        file_id=session["files"][0]["id"],
        owner="nv1",
        offset=0,
        length=size,
        source=GuardedStream(b"x" * size),
        max_chunk_bytes=size,
    )
    assert store.complete_upload(session["id"], "nv1")["status"] == "ready"


def test_slow_upload_does_not_hold_sqlite_write_lock_for_other_file(store):
    started = threading.Event()
    release = threading.Event()

    class SlowStream(io.BytesIO):
        def read(self, size=-1):
            started.set()
            if not release.wait(3):
                raise RuntimeError("test timed out")
            return super().read(size)

    session = store.create_upload_session(
        owner="nv1",
        kind="personal_video",
        files=[
            {"field": "scene1__0", "name": "a.mp4", "type": "video/mp4", "size": 4},
            {"field": "scene2__0", "name": "b.mp4", "type": "video/mp4", "size": 4},
        ],
        max_file_bytes=100,
        max_job_bytes=100,
        max_active_sessions=2,
        reserve_free_bytes=0,
    )

    def append(file_id, source):
        return store.append_upload_chunk(
            session_id=session["id"],
            file_id=file_id,
            owner="nv1",
            offset=0,
            length=4,
            source=source,
            max_chunk_bytes=8,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        slow = pool.submit(append, session["files"][0]["id"], SlowStream(b"aaaa"))
        assert started.wait(1)
        fast = pool.submit(append, session["files"][1]["id"], io.BytesIO(b"bbbb"))
        try:
            assert fast.result(timeout=2)["complete"] is True
        finally:
            release.set()
        assert slow.result(timeout=2)["complete"] is True
