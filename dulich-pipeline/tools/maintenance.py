"""Independent disk maintenance for uploads, job IPC files, and old output."""
from __future__ import annotations

import time
from pathlib import Path

from tools.pipeline_store import PipelineStore


def _cleanup_job_results(store: PipelineStore, max_age_seconds: int) -> int:
    root = (store.db_path.parent / "job-results").resolve()
    if not root.is_dir():
        return 0
    cutoff = time.time() - max(3600, int(max_age_seconds))
    removed = 0
    for item in root.iterdir():
        try:
            resolved = item.resolve()
            if (
                resolved.parent == root
                and resolved.is_file()
                and resolved.stat().st_mtime < cutoff
            ):
                resolved.unlink(missing_ok=True)
                removed += 1
        except OSError:
            continue
    return removed


def run_maintenance(
    store: PipelineStore,
    *,
    upload_ttl_hours: int = 24,
    output_retention_days: int = 5,
    archive_output: bool = False,
) -> dict:
    """Run bounded cleanup; Drive failures preserve every local output file."""
    upload_seconds = max(1, int(upload_ttl_hours)) * 3600
    result = {
        "uploads_removed": store.cleanup_uploads(upload_seconds),
        "job_results_removed": _cleanup_job_results(store, upload_seconds),
        "output": None,
    }
    if archive_output:
        from tools.storage_cleanup import run as archive_old_output

        result["output"] = archive_old_output(
            days=max(1, int(output_retention_days)),
            store=store,
        )
    return result
