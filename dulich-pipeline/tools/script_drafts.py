"""script_drafts.py — Kịch bản (khung scene) đã tạo, lưu lại KHÔNG xóa khi bấm 'Tạo nội dung'.
Hiện ở tab Video để người dùng/tự động mở lên dùng, và dùng làm lịch sử chống lặp nội dung.
"""
from __future__ import annotations

import json
import threading
import uuid
from pathlib import Path

from tools.pipeline_store import get_pipeline_store

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DRAFTS_FILE = DATA_DIR / "script_drafts.json"
_LOCK = threading.RLock()
_STORE = get_pipeline_store()


def _ensure_migrated() -> None:
    if _STORE.resource_migration_done("draft"):
        return
    with _LOCK:
        if _STORE.resource_migration_done("draft"):
            return
        try:
            items = json.loads(DRAFTS_FILE.read_text(encoding="utf-8"))
            if not isinstance(items, list):
                items = []
        except Exception:
            items = []
        _STORE.import_resources("draft", items)
        _STORE.mark_resource_migration_done("draft")


def _load() -> list:
    _ensure_migrated()
    return _STORE.list_resources("draft")


def _save(items: list) -> None:
    """Compatibility helper for old callers; replace the current draft set transactionally."""
    _ensure_migrated()
    existing = {item.get("id") for item in _STORE.list_resources("draft")}
    incoming = {item.get("id") for item in items if item.get("id")}
    for resource_id in existing - incoming:
        _STORE.delete_resource("draft", resource_id)
    for item in items:
        if not item.get("id"):
            continue
        if not _STORE.replace_resource("draft", item):
            _STORE.insert_resource("draft", item)


def _topic_of(scenes: list) -> str:
    for s in scenes:
        if s.get("kind") == "intro":
            return (s.get("title") or s.get("caption") or "").strip()[:60]
    return (scenes[0].get("caption") or "").strip()[:60] if scenes else ""


def add_draft(employee: str, scenes: list, hook_style: str, badge_mode: str,
              transition: str, overlay_engine: str, style: str, generated_by: str) -> dict:
    import time
    entry = {
        "id": uuid.uuid4().hex[:12], "user": employee, "time": time.time(),
        "topic": _topic_of(scenes), "scenes": scenes, "hook_style": hook_style,
        "badge_mode": badge_mode, "transition": transition, "overlay_engine": overlay_engine,
        "style": style, "generated_by": generated_by, "used": False,
    }
    with _LOCK:
        _ensure_migrated()
        return _STORE.insert_resource("draft", entry)


def list_drafts(employee: str | None = None, only_unused: bool = False) -> list:
    items = _load()
    if employee:
        items = [d for d in items if d.get("user") == employee]
    if only_unused:
        items = [d for d in items if not d.get("used")]
    return sorted(items, key=lambda d: d.get("time", 0), reverse=True)


def mark_used(draft_id: str) -> dict | None:
    with _LOCK:
        _ensure_migrated()
        return _STORE.update_resource("draft", draft_id, used=True)


def delete_draft(draft_id: str) -> bool:
    with _LOCK:
        _ensure_migrated()
        return _STORE.delete_resource("draft", draft_id)


def get_draft(draft_id: str) -> dict | None:
    _ensure_migrated()
    return _STORE.get_resource("draft", draft_id)


def recent_texts(employee: str, n: int = 10) -> list[str]:
    """Nội dung (captions ghép) của n kịch bản gần nhất cho 1 tài khoản — dùng chống lặp."""
    out = []
    for d in list_drafts(employee)[:n]:
        parts = [s.get("caption") or s.get("vo") or "" for s in (d.get("scenes") or [])]
        text = " ".join(p for p in parts if p).strip()
        if text:
            out.append(text[:400])
    return out
