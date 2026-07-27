from __future__ import annotations

import subprocess
import sys
import time
import json
import os
from pathlib import Path

import pytest

import server
from job_runner import reload_job_environment
from tools.pipeline_store import PipelineStore
from tools.process_control import popen_group_kwargs, terminate_process_tree


def test_isolated_job_reloads_latest_dotenv(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text(
        "OPENROUTER_KEY=new-key-from-admin\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("OPENROUTER_KEY", "stale-worker-key")
    assert reload_job_environment(tmp_path / ".env") == str(tmp_path / ".env")
    assert os.environ["OPENROUTER_KEY"] == "new-key-from-admin"


def test_process_group_can_be_terminated_quickly():
    process = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        **popen_group_kwargs(),
    )
    started = time.monotonic()
    assert terminate_process_tree(process, grace_seconds=1)
    assert process.poll() is not None
    assert time.monotonic() - started < 5


def test_isolated_job_honors_cancel_before_work(tmp_path, monkeypatch):
    store = PipelineStore(tmp_path / "pipeline.sqlite3", tmp_path / "uploads")
    job, _ = store.create_job(kind="personal_video", owner="nv1", payload={})
    running = store.claim_next("worker-test")
    assert running["id"] == job["id"]
    store.cancel_job(job["id"], "nv1")

    class FakeProcess:
        pid = 12345
        returncode = None

        def poll(self):
            return self.returncode

        def wait(self, timeout=None):
            return self.returncode

    fake = FakeProcess()
    killed = []

    def fake_terminate(process):
        killed.append(process.pid)
        process.returncode = -9
        return True

    monkeypatch.setattr(server, "PIPELINE_STORE", store)
    monkeypatch.setattr(server.subprocess, "Popen", lambda *args, **kwargs: fake)
    monkeypatch.setattr(server, "terminate_process_tree", fake_terminate)

    with pytest.raises(server.JobExecutionError, match="hủy"):
        server._run_durable_job_isolated(running)
    assert killed == [12345]


def test_job_runner_uses_shared_database_and_writes_structured_result(tmp_path):
    store = PipelineStore(tmp_path / "pipeline.sqlite3", tmp_path / "uploads")
    job, _ = store.create_job(kind="unsupported-test-kind", owner="nv1", payload={})
    store.claim_next("worker-test")
    result_file = tmp_path / "result.json"
    root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PIPELINE_DB_PATH"] = str(store.db_path)
    env["UPLOAD_TEMP_DIR"] = str(store.upload_root)
    env["AUTH_DB_PATH"] = str(tmp_path / "auth.sqlite3")
    env["DISABLE_BACKGROUND_JOBS"] = "1"
    env["DISABLE_JOB_WORKER"] = "1"

    completed = subprocess.run(
        [
            sys.executable,
            "-X",
            "utf8",
            str(root / "job_runner.py"),
            "--job-id",
            job["id"],
            "--result-file",
            str(result_file),
        ],
        cwd=str(root),
        env=env,
        timeout=15,
        check=False,
    )
    envelope = json.loads(result_file.read_text(encoding="utf-8"))
    assert completed.returncode == 3
    assert envelope["ok"] is False
    assert "không được hỗ trợ" in envelope["error"]
