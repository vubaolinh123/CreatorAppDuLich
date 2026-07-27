"""Execute exactly one leased durable job inside an isolated process group."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from tools.atomic_json import atomic_write_json


def reload_job_environment(path: str | Path | None = None) -> str:
    """Reload the current .env so a long-lived worker never passes stale keys."""
    try:
        from dotenv import load_dotenv

        dotenv_path = Path(
            path
            or os.getenv("PIPELINE_ENV_PATH")
            or (Path(__file__).parent / ".env")
        ).resolve()
        if dotenv_path.exists():
            load_dotenv(dotenv_path, override=True)
            return str(dotenv_path)
    except Exception:
        pass
    return ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--result-file", required=True)
    args = parser.parse_args()

    # The web process can update .env while this long-lived worker is running.
    # Each isolated job must reload the current file and override inherited,
    # stale API-key values before importing the pipeline.
    reload_job_environment()

    # Import after arguments/env are ready. Importing server does not start its
    # HTTP server, scheduler, or embedded worker.
    import server

    result_file = Path(args.result_file).resolve()
    job = server.PIPELINE_STORE.get_job(args.job_id)
    if not job or job.get("status") != "running":
        atomic_write_json(
            result_file,
            {
                "ok": False,
                "error": "Job không còn ở trạng thái running.",
                "retryable": False,
                "uncertain": False,
            },
        )
        return 2

    try:
        result = server._execute_durable_job(job)
        atomic_write_json(result_file, {"ok": True, "result": result or {}})
        return 0
    except server.JobExecutionError as exc:
        atomic_write_json(
            result_file,
            {
                "ok": False,
                "error": str(exc),
                "retryable": bool(exc.retryable),
                "uncertain": bool(exc.uncertain),
            },
        )
        return 3
    except BaseException as exc:
        import traceback

        traceback.print_exc()
        atomic_write_json(
            result_file,
            {
                "ok": False,
                "error": str(exc) or type(exc).__name__,
                "retryable": server._is_transient_render_err(exc),
                "uncertain": False,
            },
        )
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
