"""
db.py — MongoDB connection & collection helpers.
Provides a lazy singleton client; falls back gracefully if MongoDB is not running.
Collections:
  - jobs       : Pipeline jobs (news + personal)
  - briefs     : Brief documents (script + source folder info)
  - content    : Generated content (video, album, caption metadata)
  - creators   : Creator profiles (voice IDs, template preferences)
  - seeding    : Restaurant / hotel seeding items
  - templates  : Video / album templates
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from typing import Optional, Any

# Fix Windows console encoding globally
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# pymongo is optional — fall back to a mock store if not installed
try:
    from pymongo import MongoClient
    from pymongo.collection import Collection
    from pymongo.database import Database
    from bson import ObjectId
    MONGO_AVAILABLE = True
except ImportError:
    MONGO_AVAILABLE = False

from config import config


# ── Singleton client ──────────────────────────────────────────────────────────

_client: Optional[Any] = None
_db: Optional[Any] = None


def get_db() -> Any:
    """Return the MongoDB database instance (lazy init)."""
    global _client, _db
    if _db is not None:
        return _db

    if not MONGO_AVAILABLE:
        print("[DB] pymongo not installed — using in-memory mock store.", file=sys.stderr)
        _db = MockDB()
        return _db

    try:
        _client = MongoClient(
            config.mongo_uri,
            serverSelectionTimeoutMS=3000,  # 3s timeout
        )
        # Ping to confirm connection
        _client.admin.command("ping")
        _db = _client[config.mongo_db_name]
        print(f"[DB] ✓ Connected to MongoDB: {config.mongo_uri}/{config.mongo_db_name}", file=sys.stderr)
        _ensure_indexes(_db)
    except Exception as e:
        print(f"[DB] ⚠ MongoDB unavailable ({e}). Using in-memory mock store.", file=sys.stderr)
        _db = MockDB()

    return _db


def _ensure_indexes(db: Any) -> None:
    """Create useful indexes on startup."""
    try:
        db["jobs"].create_index("created_at")
        db["jobs"].create_index("status")
        db["briefs"].create_index("date")
        db["content"].create_index("creator_id")
        db["content"].create_index("status")
        db["seeding"].create_index("category")
    except Exception:
        pass


# ── Convenience helpers ───────────────────────────────────────────────────────

def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def new_doc(**kwargs) -> dict:
    """Build a new document with _id, created_at, updated_at."""
    return {
        "_id": str(ObjectId()) if MONGO_AVAILABLE else _mock_id(),
        "created_at": now_utc().isoformat(),
        "updated_at": now_utc().isoformat(),
        **kwargs,
    }


def _mock_id() -> str:
    import uuid
    return str(uuid.uuid4())


# ── Collection shortcuts ──────────────────────────────────────────────────────

def jobs_col():
    return get_db()["jobs"]

def briefs_col():
    return get_db()["briefs"]

def content_col():
    return get_db()["content"]

def creators_col():
    return get_db()["creators"]

def seeding_col():
    return get_db()["seeding"]

def templates_col():
    return get_db()["templates"]


# ── Job helpers ───────────────────────────────────────────────────────────────

def create_job(channel: str, topic: str, creator_id: str = "", batch_index: int = 0) -> dict:
    """Insert a new job document and return it."""
    doc = new_doc(
        channel=channel,          # "news" | "personal"
        topic=topic,
        creator_id=creator_id,
        batch_index=batch_index,
        status="pending",         # pending → running → done | error
        progress=0,
        logs=[],
        result=None,
    )
    jobs_col().insert_one(doc)
    return doc


def update_job(job_id: str, patch: dict) -> None:
    """Patch a job document by _id."""
    patch["updated_at"] = now_utc().isoformat()
    jobs_col().update_one({"_id": job_id}, {"$set": patch})


def append_job_log(job_id: str, level: str, text: str) -> None:
    """Append a log line to the job's logs array."""
    log_entry = {
        "time": now_utc().isoformat(),
        "level": level,
        "text": text,
    }
    jobs_col().update_one(
        {"_id": job_id},
        {
            "$push": {"logs": log_entry},
            "$set": {"updated_at": now_utc().isoformat()},
        }
    )


def get_pending_jobs(channel: str = "news") -> list[dict]:
    return list(jobs_col().find({"channel": channel, "status": "pending"}))


def get_recent_jobs(limit: int = 50) -> list[dict]:
    return list(jobs_col().find().sort("created_at", -1).limit(limit))


# ── Content helpers ───────────────────────────────────────────────────────────

def save_content(job_id: str, content_type: str, data: dict) -> dict:
    """Save generated content (video/album/caption) linked to a job."""
    doc = new_doc(
        job_id=job_id,
        content_type=content_type,   # "video" | "album" | "caption"
        status="pending_review",
        data=data,
    )
    content_col().insert_one(doc)
    return doc


# ── Brief helpers ─────────────────────────────────────────────────────────────

def save_brief(brief_data: dict) -> dict:
    """Persist a brief document."""
    doc = new_doc(**brief_data)
    briefs_col().insert_one(doc)
    return doc


def get_brief(brief_id: str) -> Optional[dict]:
    return briefs_col().find_one({"_id": brief_id})


# ── Seeding helpers ───────────────────────────────────────────────────────────

def get_seeding_items(location: str = "", category: str = "", limit: int = 3) -> list[dict]:
    """Fetch seeding items; filter by location/category if given."""
    query = {}
    if location:
        query["location"] = {"$regex": location, "$options": "i"}
    if category:
        query["category"] = {"$regex": category, "$options": "i"}
    return list(seeding_col().find(query).limit(limit))


# ── MockDB (fallback when MongoDB not running) ────────────────────────────────

class MockCollection:
    """In-memory collection that mimics pymongo Collection interface."""

    def __init__(self, name: str):
        self.name = name
        self._store: list[dict] = []

    def insert_one(self, doc: dict):
        self._store.append(doc)

    def find(self, query: dict = None, *args, **kwargs):
        # Very basic filter: just return all for now
        return _MockCursor(self._store)

    def find_one(self, query: dict):
        for doc in self._store:
            if all(doc.get(k) == v for k, v in (query or {}).items()):
                return doc
        return None

    def update_one(self, query: dict, update: dict):
        for doc in self._store:
            if all(doc.get(k) == v for k, v in query.items()):
                if "$set" in update:
                    doc.update(update["$set"])
                if "$push" in update:
                    for field, val in update["$push"].items():
                        doc.setdefault(field, []).append(val)
                break

    def create_index(self, *args, **kwargs):
        pass


class _MockCursor:
    def __init__(self, data: list):
        self._data = list(data)

    def sort(self, *args, **kwargs):
        return self

    def limit(self, n: int):
        self._data = self._data[:n]
        return self

    def __iter__(self):
        return iter(self._data)


class MockDB:
    """In-memory database used when pymongo is unavailable."""

    def __init__(self):
        self._collections: dict[str, MockCollection] = {}

    def __getitem__(self, name: str) -> MockCollection:
        if name not in self._collections:
            self._collections[name] = MockCollection(name)
        return self._collections[name]
