"""Reset account login aliases/passwords without putting secrets in source control."""
from __future__ import annotations

import argparse
import getpass
import json
from pathlib import Path

try:
    from .auth_store import AuthStore
except ImportError:
    from auth_store import AuthStore


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "data" / "auth.sqlite3"


def _interactive(accounts: list[str], login_name: str) -> dict[str, dict[str, str]]:
    credentials: dict[str, dict[str, str]] = {}
    for account in accounts:
        first = getpass.getpass(f"Password for {account}: ")
        second = getpass.getpass(f"Repeat password for {account}: ")
        if first != second:
            raise ValueError(f"Passwords do not match for {account}")
        credentials[account] = {"login_name": login_name, "password": first}
    return credentials


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--input", type=Path, help="Root-only JSON file; deleted manually.")
    parser.add_argument("--interactive", action="store_true")
    parser.add_argument("--login-name", default="")
    parser.add_argument("--accounts", default="")
    parser.add_argument(
        "--bootstrap-profiles",
        type=Path,
        help="Metadata JSON used only when the auth database has no users.",
    )
    parser.add_argument("--keep-sessions", action="store_true")
    args = parser.parse_args()

    if bool(args.input) == bool(args.interactive):
        parser.error("choose exactly one of --input or --interactive")
    if args.input:
        credentials = json.loads(args.input.read_text(encoding="utf-8"))
    else:
        accounts = [item.strip() for item in args.accounts.split(",") if item.strip()]
        if not args.login_name.strip() or not accounts:
            parser.error("--interactive needs --login-name and --accounts")
        credentials = _interactive(accounts, args.login_name.strip())

    store = AuthStore(args.db)
    if store.user_count() == 0:
        if not args.bootstrap_profiles:
            raise ValueError(
                "Auth database is empty; provide --bootstrap-profiles "
                "data/users.json"
            )
        profiles = json.loads(
            args.bootstrap_profiles.read_text(encoding="utf-8")
        )
        users = {}
        for account, values in credentials.items():
            if account not in profiles:
                raise ValueError(f"Profile metadata is missing for {account}")
            users[account] = {
                **dict(profiles[account] or {}),
                "login_name": values["login_name"],
                "password": values["password"],
            }
        imported = store.import_users(users)
        result = {
            "updated": imported["inserted"],
            "sessions_revoked": 0,
        }
    else:
        result = store.reset_credentials(
            credentials,
            revoke_sessions=not args.keep_sessions,
        )
    print(
        f"Credentials updated for {result['updated']} accounts; "
        f"sessions_revoked={bool(result['sessions_revoked'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
