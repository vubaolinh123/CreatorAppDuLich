"""Dedicated durable worker process for render and external publish jobs."""
from __future__ import annotations

import argparse
import sys
import time

from server import PIPELINE_STORE, run_durable_workers


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--queue",
        choices=("all", "heavy", "network"),
        default="all",
        help="Worker queue group to run.",
    )
    args = parser.parse_args()
    threads = run_durable_workers(args.queue)
    print(
        f"[worker] started queue={args.queue}, threads={len(threads)}, "
        f"db={PIPELINE_STORE.db_path}",
        file=sys.stderr,
    )
    try:
        while all(thread.is_alive() for thread in threads):
            time.sleep(1)
    except KeyboardInterrupt:
        print("[worker] stopping; leased jobs will recover after timeout.", file=sys.stderr)
        return 0
    print("[worker] a worker thread stopped unexpectedly.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
