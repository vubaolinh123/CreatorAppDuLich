"""Validate the configured Google Drive destination without printing secrets."""
from __future__ import annotations

import json

try:
    from .drive_uploader import DriveUploader
except ImportError:
    from drive_uploader import DriveUploader


def main() -> int:
    result = DriveUploader().destination_info()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
