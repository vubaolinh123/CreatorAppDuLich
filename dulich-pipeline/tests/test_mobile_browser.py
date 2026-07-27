from __future__ import annotations

import json
import threading
from http.server import ThreadingHTTPServer

import pytest

import server
from tools.auth_store import AuthStore
from tools.pipeline_store import PipelineStore


playwright = pytest.importorskip("playwright.sync_api")


@pytest.fixture()
def browser_app(tmp_path, monkeypatch):
    auth = AuthStore(tmp_path / "auth.sqlite3")
    auth.import_users(
        {
            "nv1": {
                "login_name": "appdalatnow",
                "password": "mobile-test-password",
                "role": "staff",
                "name": "Mobile tester",
                "hook_style": "hook_red",
            }
        }
    )
    pipeline = PipelineStore(
        tmp_path / "pipeline.sqlite3",
        tmp_path / "uploads",
    )
    output = tmp_path / "output"
    output.mkdir()
    products = output / "products.json"
    products.write_text("[]", encoding="utf-8")
    albums = output / "album_products.json"
    albums.write_text("[]", encoding="utf-8")

    monkeypatch.setattr(server, "AUTH_STORE", auth)
    monkeypatch.setattr(server, "PIPELINE_STORE", pipeline)
    monkeypatch.setattr(server, "OUTPUT_DIR", output.resolve())
    monkeypatch.setattr(server, "PRODUCTS_FILE", products)
    monkeypatch.setattr(server, "ALBUM_PRODUCTS_FILE", albums)
    monkeypatch.setattr(server, "AUDIT_FILE", tmp_path / "audit.jsonl")
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "0")
    monkeypatch.setenv("MEDIA_SIGNING_SECRET", "m" * 48)

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.AssembleHandler)
    port = httpd.server_address[1]
    origin = f"http://127.0.0.1:{port}"
    monkeypatch.setenv("APP_ORIGIN", origin)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield origin
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


def _launch_browser(playwright_instance):
    try:
        return playwright_instance.chromium.launch(headless=True)
    except Exception as chromium_error:
        try:
            return playwright_instance.chromium.launch(
                channel="msedge",
                headless=True,
            )
        except Exception as edge_error:
            pytest.skip(
                "Playwright Chromium/Edge is unavailable: "
                f"{chromium_error}; {edge_error}"
            )


def _login(page, origin):
    page.goto(origin, wait_until="domcontentloaded")
    page.locator("#lg-user").fill("appdalatnow")
    page.locator("#lg-pass").fill("mobile-test-password")
    page.get_by_role("button", name="Đăng nhập").click()
    page.locator("#app:not(.hidden)").wait_for()


def _open_test_editor(page):
    page.evaluate(
        """
        currentScenes = [
          {scene_id:"scene_1",label:"HOOK",title:"Test",caption:"Một",
           min_duration_sec:1,type:"clip",files:[]},
          {scene_id:"scene_2",label:"NỘI DUNG",caption:"Hai",
           min_duration_sec:1,type:"clip",files:[]},
          {scene_id:"scene_3",label:"CTA",caption:"Ba",
           min_duration_sec:1,type:"clip",files:[]}
        ];
        scenePage = 0;
        openEditor();
        """
    )
    page.locator("#drop-0").wait_for()


@pytest.mark.e2e
def test_mobile_touch_navigation_and_file_picker(browser_app):
    with playwright.sync_playwright() as instance:
        browser = _launch_browser(instance)
        context = browser.new_context(
            viewport={"width": 390, "height": 844},
            is_mobile=True,
            has_touch=True,
        )
        page = context.new_page()
        _login(page, browser_app)

        video_button = page.get_by_role("button", name="📹 Video")
        box = video_button.bounding_box()
        assert box and box["height"] >= 44
        video_button.click()
        page.get_by_role("heading", name="📹 Video").wait_for()

        page.evaluate("renderHome()")
        _open_test_editor(page)
        picker = page.locator("#drop-0")
        picker_box = picker.bounding_box()
        assert picker_box and picker_box["height"] >= 44
        assert "Bấm để chọn clip" in picker.inner_text()

        with page.expect_file_chooser() as chooser:
            picker.click()
        chooser.value.set_files(
            {
                "name": "mobile.mp4",
                "mimeType": "video/mp4",
                "buffer": b"not-a-real-video",
            }
        )
        page.get_by_text("mobile.mp4").wait_for(timeout=6000)
        assert page.evaluate(
            "document.documentElement.scrollWidth <= window.innerWidth + 1"
        )
        context.close()
        browser.close()


@pytest.mark.e2e
def test_desktop_drag_and_drop_adds_file(browser_app):
    with playwright.sync_playwright() as instance:
        browser = _launch_browser(instance)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        _login(page, browser_app)
        _open_test_editor(page)
        page.evaluate(
            """
            const transfer = new DataTransfer();
            transfer.items.add(new File(
              [new Uint8Array([0,1,2,3])],
              "desktop-drop.mp4",
              {type:"video/mp4"}
            ));
            const target = document.querySelector("#drop-0");
            target.dispatchEvent(new DragEvent(
              "dragover",
              {bubbles:true,cancelable:true,dataTransfer:transfer}
            ));
            target.dispatchEvent(new DragEvent(
              "drop",
              {bubbles:true,cancelable:true,dataTransfer:transfer}
            ));
            """
        )
        page.get_by_text("desktop-drop.mp4").wait_for(timeout=6000)
        browser.close()
