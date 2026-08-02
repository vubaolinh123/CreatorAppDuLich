"""Zernio key slots: keep by index, delete by sending an empty slot."""

from __future__ import annotations

import json

import pytest

import server


@pytest.fixture()
def keys_file(tmp_path, monkeypatch):
    path = tmp_path / "user_keys.json"
    monkeypatch.setattr(server, "USER_KEYS_FILE", path)
    return path


def _save(uid: str, slots: list[str]) -> list[str]:
    """Mirror handle_user_keys_save's merge without standing up HTTP."""
    keys = server._load_user_keys()
    rec = keys.get(uid) or {}
    old = rec.get("zernio_keys")
    if not isinstance(old, list):
        old = [rec["zernio_key"]] if (rec.get("zernio_key") or "").strip() else []
        rec.pop("zernio_key", None)
    newk = []
    for i, v in enumerate(slots):
        v = (v or "").strip()
        if set(v) <= {"•", "*"} and v:
            if i < len(old) and old[i].strip():
                newk.append(old[i].strip())
        elif v:
            newk.append(v)
    rec["zernio_keys"] = newk
    keys[uid] = rec
    server._save_user_keys(keys)
    return newk


def test_blank_slot_drops_that_key_only(keys_file):
    keys_file.write_text(
        json.dumps({"nv2": {"zernio_keys": ["k1", "k2", "k3"]}}), encoding="utf-8"
    )

    # UI marks slot 2 deleted and keeps the row, so indexes stay aligned.
    assert _save("nv2", ["••", "", "••"]) == ["k1", "k3"]


def test_deleting_the_first_key_does_not_shift_the_others(keys_file):
    """Dropping the row instead of blanking it would have kept k1 and k2."""
    keys_file.write_text(
        json.dumps({"nv2": {"zernio_keys": ["k1", "k2", "k3"]}}), encoding="utf-8"
    )

    assert _save("nv2", ["", "••", "••"]) == ["k2", "k3"]


def test_delete_all_leaves_no_stored_keys(keys_file, monkeypatch):
    monkeypatch.delenv("ZERNIO_KEY", raising=False)
    keys_file.write_text(
        json.dumps({"nv2": {"zernio_keys": ["k1", "k2"]}}), encoding="utf-8"
    )

    assert _save("nv2", ["", ""]) == []
    assert server._user_zernio_keys("nv2") == []


def test_clearing_every_key_still_falls_back_to_the_shared_one(keys_file, monkeypatch):
    """Deleting a staff member's keys does not stop them publishing.

    _user_zernio_keys falls back to the shared ZERNIO_KEY, so removing the
    per-user keys only removes their own channels, not the ability to post.
    """
    monkeypatch.setenv("ZERNIO_KEY", "shared-key")
    keys_file.write_text(
        json.dumps({"nv2": {"zernio_keys": ["k1"]}}), encoding="utf-8"
    )

    assert _save("nv2", [""]) == []
    assert server._user_zernio_keys("nv2") == ["shared-key"]


def test_new_key_can_be_added_while_deleting_an_old_one(keys_file):
    keys_file.write_text(
        json.dumps({"nv2": {"zernio_keys": ["k1", "k2"]}}), encoding="utf-8"
    )

    assert _save("nv2", ["", "••", "k3"]) == ["k2", "k3"]
