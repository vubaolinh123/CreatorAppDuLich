from pathlib import Path


HTML = (Path(__file__).resolve().parents[1] / "web" / "index.html").read_text(
    encoding="utf-8"
)


def test_mobile_controls_have_touch_targets_and_file_picker():
    assert "@media (max-width:600px)" in HTML or "@media (max-width: 600px)" in HTML
    assert "min-height:44px" in HTML or "min-height: 44px" in HTML
    assert 'for="file-${i}"' in HTML
    assert "Bấm để chọn clip" in HTML


def test_frontend_uses_resumable_upload_and_server_zip():
    assert 'API+"/uploads/init"' in HTML
    assert '"X-Upload-Offset"' in HTML
    assert "AbortController" in HTML
    assert "/album-zip/" in HTML
    assert 'API+"/jobs/retry"' in HTML
