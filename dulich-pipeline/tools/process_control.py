"""Cross-platform process-group helpers for cancellable durable jobs."""
from __future__ import annotations

import os
import signal
import subprocess
import time


def popen_group_kwargs() -> dict:
    """Start a child in a group that can be terminated with all descendants."""
    if os.name == "nt":
        return {
            "creationflags": getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        }
    return {"start_new_session": True}


def terminate_process_tree(
    process: subprocess.Popen,
    *,
    grace_seconds: float = 3.0,
) -> bool:
    """Terminate a process and every FFmpeg/Whisper descendant it spawned."""
    if process.poll() is not None:
        return True

    if os.name == "nt":
        # /T includes descendants; /F is required because FFmpeg does not
        # reliably handle CTRL_BREAK when launched without an interactive console.
        try:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=max(2.0, grace_seconds),
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            try:
                process.kill()
            except OSError:
                pass
    else:
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        except (ProcessLookupError, OSError):
            try:
                process.terminate()
            except OSError:
                pass
        deadline = time.monotonic() + max(0.1, grace_seconds)
        while process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.05)
        if process.poll() is None:
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            except (ProcessLookupError, OSError):
                try:
                    process.kill()
                except OSError:
                    pass

    try:
        process.wait(timeout=max(1.0, grace_seconds))
    except subprocess.TimeoutExpired:
        try:
            process.kill()
            process.wait(timeout=2)
        except (OSError, subprocess.TimeoutExpired):
            return False
    return process.poll() is not None
