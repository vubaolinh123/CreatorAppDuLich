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
    assert "request_id:job.requestId" in HTML
    assert '"X-Upload-Offset"' in HTML
    assert "AbortController" in HTML
    assert "MAX_PARALLEL_UPLOADS=2" in HTML
    assert "/album-zip/" in HTML
    assert 'API+"/jobs/retry"' in HTML


def test_admin_filters_use_complete_canonical_roster():
    expected = [
        '{username:"nv1",name:"Lê"}',
        '{username:"nv2",name:"Uyên"}',
        '{username:"nv3",name:"Hiền"}',
        '{username:"nv4",name:"Vy"}',
        '{username:"nv5",name:"Muối"}',
        '{username:"tintuc",name:"Tin tức"}',
    ]
    for item in expected:
        assert item in HTML
    assert 'const makers=["",...accountOrder()]' in HTML
    assert 'const users=["",...accountOrder()]' in HTML


def test_frontend_exposes_four_vivibe_voices():
    expected = {
        "vivibe:thu_review",
        "vivibe:trinh_review",
        "vivibe:my_review",
        "vivibe:adam_3",
    }
    assert 'v.startsWith("vivibe:")' in HTML
    for value in expected:
        assert f'value="{value}"' in HTML


def test_gemini_image_button_is_paused():
    assert "Tạo lại bài ảnh TikTok (AI) · Tạm dừng" in HTML
    assert 'id="aiimgBtn" disabled' in HTML
    assert 'onclick="aiImageFromLink()"' not in HTML
