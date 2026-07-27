"""Execute exactly one leased durable job inside an isolated process group."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tools.atomic_json import atomic_write_json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--result-file", required=True)
    args = parser.parse_args()

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
