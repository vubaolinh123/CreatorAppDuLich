"""SQLite-backed authentication for the DuLich pipeline web app.

Only opaque random session tokens are sent to browsers.  Passwords and session
tokens are never stored in plaintext.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
from pathlib import Path
from typing import Any


SCRYPT_N = 1 << 15
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_MAXMEM = 64 * 1024 * 1024
LOGIN_WINDOW_SECONDS = 15 * 60
LOGIN_MAX_FAILURES = 5


def _now() -> int:
    return int(time.time())


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_password(password: str, salt: bytes | None = None) -> str:
    if not isinstance(password, str) or not password:
        raise ValueError("Password must not be empty")
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        maxmem=SCRYPT_MAXMEM,
        dklen=32,
    )
    return (
        f"scrypt$n={SCRYPT_N},r={SCRYPT_R},p={SCRYPT_P}"
        f"${salt.hex()}${digest.hex()}"
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, params, salt_hex, digest_hex = encoded.split("$", 3)
        if algorithm != "scrypt":
            return False
        parsed = dict(item.split("=", 1) for item in params.split(","))
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=int(parsed["n"]),
            r=int(parsed["r"]),
            p=int(parsed["p"]),
            maxmem=SCRYPT_MAXMEM,
            dklen=len(expected),
        )
        return hmac.compare_digest(actual, expected)
    except (KeyError, TypeError, ValueError):
        return False


class AuthStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.idle_ttl = max(300, int(os.getenv("SESSION_IDLE_SECONDS", str(12 * 3600))))
        self.absolute_ttl = max(
            self.idle_ttl,
            int(os.getenv("SESSION_ABSOLUTE_SECONDS", str(7 * 24 * 3600))),
        )
        self._initialize()
        try:
            os.chmod(self.db_path, 0o600)
        except OSError:
            pass

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=10000")
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def _initialize(self) -> None:
        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY COLLATE NOCASE,
                    login_name TEXT NOT NULL COLLATE NOCASE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('admin', 'staff', 'news')),
                    profile_json TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY,
                    username TEXT NOT NULL REFERENCES users(username) ON DELETE CASCADE,
                    csrf_hash TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    last_seen INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL,
                    revoked_at INTEGER
                );
                CREATE INDEX IF NOT EXISTS sessions_username_idx
                    ON sessions(username);
                CREATE TABLE IF NOT EXISTS login_failures (
                    bucket TEXT PRIMARY KEY,
                    failures INTEGER NOT NULL,
                    window_started INTEGER NOT NULL,
                    locked_until INTEGER NOT NULL DEFAULT 0
                );
                """
            )
            columns = {
                row["name"]
                for row in db.execute("PRAGMA table_info(users)").fetchall()
            }
            if "login_name" not in columns:
                db.execute("ALTER TABLE users ADD COLUMN login_name TEXT")
                db.execute(
                    "UPDATE users SET login_name=username "
                    "WHERE login_name IS NULL OR login_name=''"
                )
            db.execute(
                "CREATE INDEX IF NOT EXISTS users_login_name_idx "
                "ON users(login_name)"
            )

    @staticmethod
    def public_profile(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
        raw = row["profile_json"]
        try:
            profile = json.loads(raw)
        except Exception:
            profile = {}
        profile.pop("password", None)
        profile.pop("password_hash", None)
        profile["username"] = row["username"]
        profile["login_name"] = row["login_name"]
        profile["role"] = row["role"]
        return profile

    def user_count(self) -> int:
        with self._connect() as db:
            return int(db.execute("SELECT COUNT(*) FROM users").fetchone()[0])

    def users_dict(self) -> dict[str, dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT username, login_name, role, profile_json "
                "FROM users WHERE active=1 ORDER BY username"
            ).fetchall()
        return {row["username"]: self.public_profile(row) for row in rows}

    def get_user(self, username: str) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT username, login_name, role, profile_json FROM users "
                "WHERE username=? AND active=1",
                (username,),
            ).fetchone()
        return self.public_profile(row) if row else None

    def import_users(
        self,
        users: dict[str, dict[str, Any]],
        *,
        replace: bool = False,
    ) -> dict[str, int]:
        prepared: list[tuple[str, str, str, str, str]] = []
        for key, source in users.items():
            record = dict(source or {})
            username = str(record.get("account_id") or key).strip()
            login_name = str(
                record.get("login_name") or record.get("username") or username
            ).strip()
            password = str(record.pop("password", "") or "")
            role = str(record.get("role") or "staff").strip()
            if not username or not login_name or not password:
                raise ValueError(f"Account {username or key!r} has no password")
            if role not in {"admin", "staff", "news"}:
                raise ValueError(f"Account {username!r} has invalid role {role!r}")
            record["username"] = username
            record["login_name"] = login_name
            record["role"] = role
            prepared.append(
                (
                    username,
                    login_name,
                    hash_password(password),
                    role,
                    json.dumps(record, ensure_ascii=False),
                )
            )

        now = _now()
        inserted = updated = 0
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                for username, login_name, password_hash, role, profile_json in prepared:
                    exists = db.execute(
                        "SELECT 1 FROM users WHERE username=?", (username,)
                    ).fetchone()
                    if exists and not replace:
                        continue
                    if exists:
                        db.execute(
                            "UPDATE users SET login_name=?, password_hash=?, "
                            "role=?, profile_json=?, "
                            "active=1, updated_at=? WHERE username=?",
                            (
                                login_name,
                                password_hash,
                                role,
                                profile_json,
                                now,
                                username,
                            ),
                        )
                        updated += 1
                    else:
                        db.execute(
                            "INSERT INTO users "
                            "(username,login_name,password_hash,role,profile_json,"
                            "active,created_at,updated_at) "
                            "VALUES (?,?,?,?,?,1,?,?)",
                            (
                                username,
                                login_name,
                                password_hash,
                                role,
                                profile_json,
                                now,
                                now,
                            ),
                        )
                        inserted += 1
                db.commit()
            except Exception:
                db.rollback()
                raise
        return {"inserted": inserted, "updated": updated, "total": self.user_count()}

    def reset_credentials(
        self,
        credentials: dict[str, dict[str, str]],
        *,
        revoke_sessions: bool = True,
    ) -> dict[str, int]:
        """Atomically replace login aliases/passwords without storing plaintext."""
        prepared: list[tuple[str, str, str]] = []
        seen_login_passwords: set[tuple[str, str]] = set()
        for username, values in credentials.items():
            internal = str(username or "").strip()
            login_name = str((values or {}).get("login_name") or "").strip()
            password = str((values or {}).get("password") or "")
            if not internal or not login_name or len(password) < 10:
                raise ValueError(
                    f"Credential {internal or '<empty>'!r} needs login_name "
                    "and a password of at least 10 characters"
                )
            identity = (login_name.lower(), password)
            if identity in seen_login_passwords:
                raise ValueError(
                    "Accounts sharing a login_name must have distinct passwords"
                )
            seen_login_passwords.add(identity)
            prepared.append((internal, login_name, hash_password(password)))
        if not prepared:
            raise ValueError("No credentials supplied")

        now = _now()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                known = {
                    row["username"].lower()
                    for row in db.execute(
                        "SELECT username FROM users WHERE active=1"
                    ).fetchall()
                }
                missing = [
                    username
                    for username, _, _ in prepared
                    if username.lower() not in known
                ]
                if missing:
                    raise ValueError(
                        "Unknown/inactive accounts: " + ", ".join(sorted(missing))
                    )
                for username, login_name, password_hash in prepared:
                    row = db.execute(
                        "SELECT profile_json FROM users WHERE username=?",
                        (username,),
                    ).fetchone()
                    profile = json.loads(row["profile_json"] or "{}")
                    profile["username"] = username
                    profile["login_name"] = login_name
                    db.execute(
                        "UPDATE users SET login_name=?, password_hash=?, "
                        "profile_json=?, updated_at=? WHERE username=?",
                        (
                            login_name,
                            password_hash,
                            json.dumps(profile, ensure_ascii=False),
                            now,
                            username,
                        ),
                    )
                if revoke_sessions:
                    placeholders = ",".join("?" for _ in prepared)
                    db.execute(
                        f"UPDATE sessions SET revoked_at=? "
                        f"WHERE username IN ({placeholders}) AND revoked_at IS NULL",
                        [now, *[item[0] for item in prepared]],
                    )
                db.commit()
            except Exception:
                db.rollback()
                raise
        return {
            "updated": len(prepared),
            "sessions_revoked": int(bool(revoke_sessions)),
        }

    @staticmethod
    def _failure_bucket(username: str, remote_ip: str) -> str:
        return f"{username.strip().lower()}|{remote_ip.strip() or '-'}"

    def login_retry_after(self, username: str, remote_ip: str) -> int:
        now = _now()
        bucket = self._failure_bucket(username, remote_ip)
        with self._connect() as db:
            row = db.execute(
                "SELECT locked_until FROM login_failures WHERE bucket=?", (bucket,)
            ).fetchone()
        return max(0, int(row["locked_until"]) - now) if row else 0

    def _record_login_failure(self, username: str, remote_ip: str) -> int:
        now = _now()
        bucket = self._failure_bucket(username, remote_ip)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            alias_count = int(
                db.execute(
                    "SELECT COUNT(*) FROM users "
                    "WHERE login_name=? AND active=1",
                    (username,),
                ).fetchone()[0]
            )
            failure_limit = LOGIN_MAX_FAILURES + max(0, min(alias_count, 8) - 1)
            row = db.execute(
                "SELECT failures,window_started,locked_until FROM login_failures "
                "WHERE bucket=?",
                (bucket,),
            ).fetchone()
            if not row or now - int(row["window_started"]) >= LOGIN_WINDOW_SECONDS:
                failures, window_started = 1, now
            else:
                failures, window_started = int(row["failures"]) + 1, int(row["window_started"])
            locked_until = (
                now + LOGIN_WINDOW_SECONDS if failures >= failure_limit else 0
            )
            db.execute(
                "INSERT INTO login_failures(bucket,failures,window_started,locked_until) "
                "VALUES (?,?,?,?) ON CONFLICT(bucket) DO UPDATE SET "
                "failures=excluded.failures,window_started=excluded.window_started,"
                "locked_until=excluded.locked_until",
                (bucket, failures, window_started, locked_until),
            )
            db.commit()
        return max(0, locked_until - now)

    def authenticate(
        self, login_name: str, password: str, remote_ip: str
    ) -> tuple[dict[str, Any] | None, int]:
        retry_after = self.login_retry_after(login_name, remote_ip)
        if retry_after:
            return None, retry_after
        with self._connect() as db:
            rows = db.execute(
                "SELECT username,login_name,password_hash,role,profile_json "
                "FROM users WHERE login_name=? AND active=1 ORDER BY username",
                (login_name,),
            ).fetchall()
        matches = [
            row for row in rows if verify_password(password, row["password_hash"])
        ]
        if len(matches) != 1:
            return None, self._record_login_failure(login_name, remote_ip)
        row = matches[0]
        with self._connect() as db:
            db.execute(
                "DELETE FROM login_failures WHERE bucket=?",
                (self._failure_bucket(login_name, remote_ip),),
            )
        return self.public_profile(row), 0

    def create_session(self, username: str) -> tuple[str, str, dict[str, Any]]:
        profile = self.get_user(username)
        if not profile:
            raise ValueError("Unknown or inactive account")
        token = secrets.token_urlsafe(32)
        csrf = secrets.token_urlsafe(32)
        now = _now()
        with self._connect() as db:
            db.execute(
                "INSERT INTO sessions "
                "(token_hash,username,csrf_hash,created_at,last_seen,expires_at,revoked_at) "
                "VALUES (?,?,?,?,?,?,NULL)",
                (
                    _hash_token(token),
                    username,
                    _hash_token(csrf),
                    now,
                    now,
                    now + self.absolute_ttl,
                ),
            )
        return token, csrf, profile

    def get_session(self, token: str) -> dict[str, Any] | None:
        if not token:
            return None
        token_hash = _hash_token(token)
        now = _now()
        with self._connect() as db:
            row = db.execute(
                "SELECT s.*,u.login_name,u.role,u.profile_json,u.active "
                "FROM sessions s JOIN users u ON u.username=s.username "
                "WHERE s.token_hash=?",
                (token_hash,),
            ).fetchone()
            if (
                not row
                or row["revoked_at"] is not None
                or not int(row["active"])
                or now >= int(row["expires_at"])
                or now - int(row["last_seen"]) >= self.idle_ttl
            ):
                if row:
                    db.execute(
                        "UPDATE sessions SET revoked_at=COALESCE(revoked_at,?) "
                        "WHERE token_hash=?",
                        (now, token_hash),
                    )
                return None
            if now - int(row["last_seen"]) >= 300:
                db.execute(
                    "UPDATE sessions SET last_seen=? WHERE token_hash=?",
                    (now, token_hash),
                )
        return {
            "username": row["username"],
            "role": row["role"],
            "profile": self.public_profile(row),
            "csrf_hash": row["csrf_hash"],
            "expires_at": int(row["expires_at"]),
        }

    @staticmethod
    def csrf_matches(session: dict[str, Any], csrf_token: str) -> bool:
        if not csrf_token:
            return False
        return hmac.compare_digest(
            str(session.get("csrf_hash") or ""),
            _hash_token(csrf_token),
        )

    def revoke_session(self, token: str) -> None:
        if not token:
            return
        with self._connect() as db:
            db.execute(
                "UPDATE sessions SET revoked_at=? WHERE token_hash=?",
                (_now(), _hash_token(token)),
            )

    def cleanup(self) -> None:
        now = _now()
        with self._connect() as db:
            db.execute(
                "DELETE FROM sessions WHERE revoked_at IS NOT NULL OR expires_at<=? "
                "OR last_seen<=?",
                (now, now - self.idle_ttl),
            )
            db.execute(
                "DELETE FROM login_failures WHERE window_started<=? AND locked_until<=?",
                (now - LOGIN_WINDOW_SECONDS, now),
            )
