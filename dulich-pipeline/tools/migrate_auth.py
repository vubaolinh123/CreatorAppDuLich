"""One-time migration from legacy plaintext users to SQLite authentication."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

try:
    from .auth_store import AuthStore
except ImportError:  # direct: python tools/migrate_auth.py
    from auth_store import AuthStore


ROOT = Path(__file__).resolve().parent.parent
USERS_FILE = Path(
    os.getenv("AUTH_USERS_FILE") or (ROOT / "data" / "users.json")
).resolve()
AUTH_DB = Path(
    os.getenv("AUTH_DB_PATH") or (ROOT / "data" / "auth.sqlite3")
).resolve()


def _local_users() -> dict:
    data = json.loads(USERS_FILE.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("data/users.json must contain an object")
    return data


def _supabase_users() -> dict:
    if not (os.getenv("SUPABASE_URL") or "").strip():
        return {}
    from supabase_client import get_supabase

    rows = get_supabase().get_users()
    return {
        str(row.get("username") or "").strip(): row
        for row in rows
        if str(row.get("username") or "").strip()
    }


def load_source(source: str) -> tuple[str, dict]:
    if source in {"auto", "supabase"}:
        users = _supabase_users()
        if users:
            return "supabase", users
        if source == "supabase":
            raise RuntimeError("Supabase is not configured or returned no users")
    return "json", _local_users()


def scrub_local_passwords() -> None:
    users = _local_users()
    sanitized = {}
    for username, record in users.items():
        clean = dict(record or {})
        clean.pop("password", None)
        clean.pop("password_hash", None)
        sanitized[username] = clean
    USERS_FILE.write_text(
        json.dumps(sanitized, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=("auto", "json", "supabase"), default="auto")
    parser.add_argument("--db", type=Path, default=AUTH_DB)
    parser.add_argument("--replace", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--scrub-json", action="store_true")
    args = parser.parse_args()

    source_name, users = load_source(args.source)
    roles: dict[str, int] = {}
    missing_passwords = []
    for username, record in users.items():
        if not str((record or {}).get("password") or ""):
            missing_passwords.append(username)
        role = str((record or {}).get("role") or "staff")
        roles[role] = roles.get(role, 0) + 1

    print(f"Source: {source_name}; accounts: {len(users)}; roles: {roles}")
    if missing_passwords:
        store = AuthStore(args.db)
        if store.user_count() >= len(users):
            print(
                "Legacy source is already scrubbed and SQLite contains all account "
                "profiles; no migration is needed."
            )
            return 0
        raise ValueError(
            "Legacy source no longer contains passwords and SQLite is incomplete. "
            "Restore the pre-migration source or securely copy auth.sqlite3 from "
            "the migrated machine."
        )
    if args.dry_run:
        print("Dry run complete; no files changed.")
        return 0

    store = AuthStore(args.db)
    result = store.import_users(users, replace=args.replace)
    if result["total"] < len(users):
        raise RuntimeError("Migration verification failed: SQLite has fewer accounts than source")
    for username, record in users.items():
        profile, retry_after = store.authenticate(
            username,
            str((record or {}).get("password") or ""),
            "migration-local",
        )
        if retry_after or not profile or profile.get("username") != username:
            raise RuntimeError(f"Migration verification failed for account {username!r}")
    print(
        f"SQLite migration complete: inserted={result['inserted']}, "
        f"updated={result['updated']}, total={result['total']}"
    )
    if args.scrub_json:
        scrub_local_passwords()
        print("Removed plaintext password fields from data/users.json.")
    if source_name == "supabase":
        print(
            "IMPORTANT: remove the legacy Supabase users.password column/data and "
            "revoke anon access after login smoke testing."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
