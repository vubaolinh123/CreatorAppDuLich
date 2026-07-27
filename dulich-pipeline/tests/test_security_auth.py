from __future__ import annotations

import concurrent.futures
import json
import threading
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

import server
from tools.auth_store import AuthStore, hash_password, verify_password
from tools.pipeline_store import PipelineStore


def test_password_hash_is_salted_and_verifiable():
    first = hash_password("test-password")
    second = hash_password("test-password")
    assert first != second
    assert "test-password" not in first
    assert verify_password("test-password", first)
    assert not verify_password("wrong", first)


def test_shared_login_alias_maps_password_to_internal_account(tmp_path):
    store = AuthStore(tmp_path / "auth.sqlite3")
    store.import_users(
        {
            "admin": {
                "login_name": "appdalatnow",
                "password": "admin-password",
                "role": "admin",
            },
            "nv1": {
                "login_name": "appdalatnow",
                "password": "staff-password",
                "role": "staff",
            },
        }
    )

    admin, retry = store.authenticate(
        "appdalatnow", "admin-password", "127.0.0.1"
    )
    assert retry == 0
    assert admin["username"] == "admin"
    assert admin["login_name"] == "appdalatnow"

    staff, retry = store.authenticate(
        "appdalatnow", "staff-password", "127.0.0.1"
    )
    assert retry == 0
    assert staff["username"] == "nv1"


def test_reset_credentials_is_atomic_and_revokes_existing_sessions(tmp_path):
    store = AuthStore(tmp_path / "auth.sqlite3")
    store.import_users(
        {
            "admin": {
                "password": "old-admin-password",
                "role": "admin",
            },
            "nv1": {
                "password": "old-staff-password",
                "role": "staff",
            },
        }
    )
    token, _, _ = store.create_session("admin")

    result = store.reset_credentials(
        {
            "admin": {
                "login_name": "appdalatnow",
                "password": "new-admin-password",
            },
            "nv1": {
                "login_name": "appdalatnow",
                "password": "new-staff-password",
            },
        }
    )
    assert result["updated"] == 2
    assert store.get_session(token) is None
    assert store.authenticate("admin", "old-admin-password", "127.0.0.1")[0] is None
    assert (
        store.authenticate(
            "appdalatnow", "new-admin-password", "127.0.0.1"
        )[0]["username"]
        == "admin"
    )
    assert (
        store.authenticate(
            "appdalatnow", "new-staff-password", "127.0.0.1"
        )[0]["username"]
        == "nv1"
    )


def test_six_sessions_are_isolated_under_concurrency(tmp_path):
    store = AuthStore(tmp_path / "auth.sqlite3")
    users = {
        f"nv{i}": {"password": f"pw-{i}", "role": "staff", "name": f"NV {i}"}
        for i in range(1, 6)
    }
    users["admin"] = {"password": "pw-admin", "role": "admin", "name": "Admin"}
    store.import_users(users)

    sessions = []
    for username, record in users.items():
        profile, retry = store.authenticate(username, record["password"], "127.0.0.1")
        assert retry == 0 and profile["username"] == username
        sessions.append((username, *store.create_session(username)[:2]))

    def read_session(item):
        expected, token, csrf = item
        session = store.get_session(token)
        return (
            expected,
            session["username"],
            store.csrf_matches(session, csrf),
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(read_session, sessions * 10))
    assert all(expected == actual and csrf_ok for expected, actual, csrf_ok in results)


def test_path_resolver_rejects_traversal_and_absolute_paths(tmp_path):
    base = tmp_path / "allowed"
    base.mkdir()
    (base / "ok.txt").write_text("ok", encoding="utf-8")
    assert server._resolve_under(base, "ok.txt") == (base / "ok.txt").resolve()
    for attack in ("../outside.txt", "%2e%2e/outside.txt", str(tmp_path / "outside.txt")):
        with pytest.raises((OSError, ValueError)):
            server._resolve_under(base, attack)


def test_login_is_rate_limited_after_five_failures(tmp_path):
    store = AuthStore(tmp_path / "auth.sqlite3")
    store.import_users({
        "nv1": {"password": "correct", "role": "staff", "name": "NV 1"}
    })
    retry_after = 0
    for _ in range(5):
        profile, retry_after = store.authenticate("nv1", "wrong", "10.0.0.1")
        assert profile is None
    assert retry_after > 0
    profile, retry_after = store.authenticate("nv1", "correct", "10.0.0.1")
    assert profile is None and retry_after > 0


@pytest.fixture()
def secured_server(tmp_path, monkeypatch):
    auth = AuthStore(tmp_path / "auth.sqlite3")
    auth.import_users({
        "nv1": {"password": "pw1", "role": "staff", "name": "NV 1"},
        "nv2": {"password": "pw2", "role": "staff", "name": "NV 2"},
        "admin": {"password": "pwa", "role": "admin", "name": "Admin"},
    })
    output = tmp_path / "output"
    (output / "videos").mkdir(parents=True)
    (output / "videos" / "one.mp4").write_bytes(b"video-one")
    (output / "videos" / "two.mp4").write_bytes(b"video-two")
    products = output / "products.json"
    products.write_text(json.dumps([
        {
            "id": "video-one", "user": "nv1", "topic": "One",
            "video_url": "/output/videos/one.mp4", "time": 1,
        },
        {
            "id": "video-two", "user": "nv2", "topic": "Two",
            "video_url": "/output/videos/two.mp4", "time": 2,
        },
    ]), encoding="utf-8")
    albums = output / "album_products.json"
    albums.write_text("[]", encoding="utf-8")

    monkeypatch.setattr(server, "AUTH_STORE", auth)
    monkeypatch.setattr(
        server,
        "PIPELINE_STORE",
        PipelineStore(tmp_path / "pipeline.sqlite3", tmp_path / "uploads"),
    )
    monkeypatch.setattr(server, "OUTPUT_DIR", output.resolve())
    monkeypatch.setattr(server, "PRODUCTS_FILE", products)
    monkeypatch.setattr(server, "ALBUM_PRODUCTS_FILE", albums)
    monkeypatch.setattr(server, "AUDIT_FILE", tmp_path / "audit.jsonl")
    monkeypatch.setenv("MEDIA_SIGNING_SECRET", "s" * 48)
    monkeypatch.setenv("SKIP_UPLOAD_FFPROBE", "1")

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.AssembleHandler)
    port = httpd.server_address[1]
    monkeypatch.setenv("APP_ORIGIN", f"http://127.0.0.1:{port}")
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield port
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


def request(port, method, path, *, body=None, headers=None):
    connection = HTTPConnection("127.0.0.1", port, timeout=5)
    payload = None if body is None else json.dumps(body).encode()
    actual_headers = dict(headers or {})
    if body is not None:
        actual_headers.setdefault("Content-Type", "application/json")
        actual_headers.setdefault("Content-Length", str(len(payload)))
    connection.request(method, path, body=payload, headers=actual_headers)
    response = connection.getresponse()
    raw = response.read()
    result = (
        response.status,
        response.getheaders(),
        json.loads(raw.decode()) if raw and "json" in (response.getheader("Content-Type") or "") else raw,
    )
    connection.close()
    return result


def login(port, username, password):
    origin = f"http://127.0.0.1:{port}"
    status, headers, data = request(
        port, "POST", "/login",
        body={"username": username, "password": password},
        headers={"Origin": origin},
    )
    assert status == 200
    cookies = [value.split(";", 1)[0] for key, value in headers if key.lower() == "set-cookie"]
    return {
        "Cookie": "; ".join(cookies),
        "Origin": origin,
        "X-CSRF-Token": data["csrf_token"],
    }


def test_unauthenticated_api_and_direct_output_are_blocked(secured_server):
    port = secured_server
    status, headers, _ = request(port, "GET", "/settings")
    assert status == 401
    assert not any(key.lower() == "access-control-allow-origin" for key, _ in headers)
    status, _, _ = request(port, "GET", "/output/../README.md")
    assert status == 404


def test_client_role_and_user_cannot_impersonate(secured_server):
    port = secured_server
    nv1 = login(port, "nv1", "pw1")
    status, _, data = request(
        port, "GET", "/library?user=nv2&role=admin", headers=nv1
    )
    assert status == 200
    assert [item["user"] for item in data["videos"]] == ["nv1"]
    status, _, _ = request(
        port, "POST", "/product-status",
        body={"kind": "video", "id": "video-two", "status": "posted", "role": "admin"},
        headers=nv1,
    )
    assert status == 403


def test_media_is_owner_scoped_and_signed_public_url_expires_on_tamper(secured_server):
    port = secured_server
    nv1 = login(port, "nv1", "pw1")
    nv2 = login(port, "nv2", "pw2")
    status, _, body = request(port, "GET", "/media/video/video-one", headers=nv1)
    assert status == 200 and body == b"video-one"
    status, _, _ = request(port, "GET", "/media/video/video-one", headers=nv2)
    assert status == 404

    signed = server._signed_media_url("video", "video-one")
    status, _, body = request(port, "GET", signed)
    assert status == 200 and body == b"video-one"
    status, _, _ = request(port, "GET", signed.replace("video-one", "video-two"))
    assert status == 403


def test_admin_can_review_all_users_by_resource_id(secured_server):
    port = secured_server
    admin = login(port, "admin", "pwa")
    status, _, data = request(port, "GET", "/library", headers=admin)
    assert status == 200
    assert {item["id"] for item in data["videos"]} == {"video-one", "video-two"}
    status, _, data = request(
        port,
        "POST",
        "/product-status",
        body={"kind": "video", "id": "video-two", "status": "cancelled"},
        headers=admin,
    )
    assert status == 200 and data["success"] is True


def test_publish_reconcile_is_admin_only_and_requires_provider_id(secured_server):
    port = secured_server
    nv1 = login(port, "nv1", "pw1")
    status, _, _ = request(
        port,
        "POST",
        "/publish-reconcile",
        body={"kind": "video", "id": "video-one"},
        headers=nv1,
    )
    assert status == 403

    admin = login(port, "admin", "pwa")
    status, _, data = request(
        port,
        "POST",
        "/publish-reconcile",
        body={"kind": "video", "id": "video-one"},
        headers=admin,
    )
    assert status == 409
    assert data["status"] == "unknown"
    assert "post id" in data["error"].lower()


def test_streaming_upload_creates_server_owned_durable_job(secured_server):
    port = secured_server
    nv1 = login(port, "nv1", "pw1")
    status, _, data = request(
        port,
        "POST",
        "/uploads/init",
        body={
            "kind": "listreview_video",
            "files": [
                {
                    "field": "intro__0",
                    "name": "intro.mp4",
                    "type": "video/mp4",
                    "size": 10,
                }
            ],
        },
        headers=nv1,
    )
    assert status == 201 and data["success"]
    upload_id = data["upload"]["id"]
    file_id = data["upload"]["files"][0]["id"]

    connection = HTTPConnection("127.0.0.1", port, timeout=5)
    headers = {
        **nv1,
        "Content-Type": "application/octet-stream",
        "Content-Length": "10",
        "X-Upload-Offset": "0",
    }
    connection.request(
        "PUT",
        f"/uploads/{upload_id}/{file_id}",
        body=b"0123456789",
        headers=headers,
    )
    response = connection.getresponse()
    chunk_result = json.loads(response.read().decode())
    connection.close()
    assert response.status == 200 and chunk_result["complete"] is True

    status, _, data = request(
        port,
        "POST",
        f"/uploads/{upload_id}/complete",
        body={},
        headers=nv1,
    )
    assert status == 200 and data["upload"]["status"] == "ready"
    status, _, data = request(
        port,
        "POST",
        "/jobs",
        body={
            "kind": "listreview_video",
            "upload_id": upload_id,
            "payload": {
                "topic": "Test",
                "spec": {
                    "intro": {"scene_id": "intro", "vo": "hello"},
                    "spots": [],
                    "outro": {"scene_id": "outro", "vo": ""},
                },
            },
        },
        headers=nv1,
    )
    assert status == 202 and data["queued"] is True
    assert len(data["job_id"]) == 32
    assert data["job_id"] != upload_id
    status, _, listed = request(port, "GET", "/render-jobs", headers=nv1)
    assert status == 200
    assert listed["jobs"][0]["job_id"] == data["job_id"]

    nv2 = login(port, "nv2", "pw2")
    status, _, _ = request(
        port,
        "POST",
        "/jobs/cancel",
        body={"job_id": data["job_id"]},
        headers=nv2,
    )
    assert status == 404
    status, _, cancelled = request(
        port,
        "POST",
        "/jobs/cancel",
        body={"job_id": data["job_id"]},
        headers=nv1,
    )
    assert status == 200
    assert cancelled["job"]["durable_status"] == "cancelled"


def test_album_download_is_one_zip_and_owner_scoped(secured_server):
    port = secured_server
    image = server.OUTPUT_DIR / "albums" / "one.png"
    image.parent.mkdir(parents=True, exist_ok=True)
    image.write_bytes(b"not-a-real-png")
    server.PIPELINE_STORE.insert_resource(
        "album",
        {
            "id": "album-one",
            "user": "nv1",
            "label": "Album test",
            "images": [{"name": "one.png", "url": "/output/albums/one.png"}],
            "time": 1,
        },
    )

    nv2 = login(port, "nv2", "pw2")
    status, _, _ = request(port, "GET", "/album-zip/album-one", headers=nv2)
    assert status == 404

    nv1 = login(port, "nv1", "pw1")
    status, headers, body = request(
        port, "GET", "/album-zip/album-one", headers=nv1
    )
    assert status == 200
    assert body.startswith(b"PK")
    assert any(
        key.lower() == "content-type" and value == "application/zip"
        for key, value in headers
    )


def test_cross_origin_post_is_rejected(secured_server):
    port = secured_server
    status, headers, _ = request(
        port,
        "POST",
        "/login",
        body={"username": "nv1", "password": "pw1"},
        headers={"Origin": "https://evil.example"},
    )
    assert status == 403
    assert not any(key.lower() == "access-control-allow-origin" for key, _ in headers)


def test_csrf_and_logout_revoke_the_session(secured_server):
    port = secured_server
    nv1 = login(port, "nv1", "pw1")
    invalid = dict(nv1)
    invalid["X-CSRF-Token"] = "tampered"
    status, _, _ = request(
        port, "POST", "/album-delete", body={"id": "missing"}, headers=invalid
    )
    assert status == 403
    status, _, _ = request(port, "POST", "/logout", headers=nv1)
    assert status == 200
    status, _, _ = request(port, "GET", "/session", headers=nv1)
    assert status == 401
