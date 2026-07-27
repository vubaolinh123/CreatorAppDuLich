"""
album_db.py — Kho "Ảnh chung" Đà Lạt (ảnh không thuộc quán nào). Kho phẳng, KHÔNG phân loại.
Storage: data/album_images.json ; file ảnh: data/album/
"""
from __future__ import annotations

import json
import threading
import functools
from pathlib import Path

from tools.atomic_json import atomic_write_json

DB_PATH = Path(__file__).parent.parent / "data" / "album_images.json"
ALBUM_DIR = Path(__file__).parent.parent / "data" / "album"

_LOCK = threading.RLock()


def _locked(fn):
    @functools.wraps(fn)
    def _w(*a, **k):
        with _LOCK:
            return fn(*a, **k)
    return _w


def _load() -> dict:
    if DB_PATH.exists():
        with open(DB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"images": [], "_next_id": 1}


def _save(data: dict) -> None:
    atomic_write_json(DB_PATH, data)


def get_all() -> list:
    # bỏ mục mà file đã mất
    data = _load()
    out = []
    for im in data["images"]:
        if (Path(__file__).parent.parent / im.get("file", "")).exists():
            out.append(im)
    return out


@_locked
def add(file_rel: str) -> dict:
    """Thêm 1 ảnh (đường dẫn tương đối, vd data/album/x.jpg)."""
    data = _load()
    if any(im.get("file") == file_rel for im in data["images"]):
        return next(im for im in data["images"] if im["file"] == file_rel)
    iid = data.get("_next_id", len(data["images"]) + 1)
    im = {"id": iid, "file": file_rel}
    data["images"].append(im)
    data["_next_id"] = iid + 1
    _save(data)
    return im


@_locked
def delete_by_id(iid: int) -> str | None:
    data = _load()
    rm = next((im for im in data["images"] if im["id"] == iid), None)
    if not rm:
        return None
    data["images"] = [im for im in data["images"] if im["id"] != iid]
    _save(data)
    return rm.get("file")
