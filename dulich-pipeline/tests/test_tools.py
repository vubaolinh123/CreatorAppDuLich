"""Tests for pipeline tools (sheets_sync, drive_uploader, voice_generator, video_renderer)."""

import json
import sys
import os
import pytest
from unittest.mock import MagicMock, patch, mock_open
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ─── SheetsSync tests ─────────────────────────────────────────────────────────

from tools.sheets_sync import SheetsSync


@pytest.fixture
def mock_sheets_service():
    service = MagicMock()
    return service


def test_sheets_sync_no_credentials_returns_empty(monkeypatch):
    monkeypatch.setattr("tools.sheets_sync.SheetsSync._get_service", lambda self: None)
    sync = SheetsSync("fake-sheet-id")
    assert sync.read_sheet("Videos") == []
    assert sync.append_row("Videos", ["a", "b"]) is False
    assert sync.update_cell("Videos", "A1", "test") is False


def test_sheets_sync_append_row_calls_service(mock_sheets_service):
    with patch.object(SheetsSync, "_get_service", return_value=mock_sheets_service):
        sync = SheetsSync("test-sheet-id")
        result = sync.append_row("Videos", ["vid1", "AI", "done", "http://link"])
        assert result is True
        mock_sheets_service.spreadsheets().values().append.assert_called_once()


def test_sheets_sync_append_row_sends_correct_params(mock_sheets_service):
    with patch.object(SheetsSync, "_get_service", return_value=mock_sheets_service):
        sync = SheetsSync("test-sheet-id")
        sync.append_row("Videos", ["vid1", "AI", "done", "http://link"])
        call = mock_sheets_service.spreadsheets().values().append.call_args
        assert "test-sheet-id" in str(call)


def test_sheets_sync_update_cell_calls_service(mock_sheets_service):
    with patch.object(SheetsSync, "_get_service", return_value=mock_sheets_service):
        sync = SheetsSync("test-sheet-id")
        result = sync.update_cell("Videos", "A1", "new-value")
        assert result is True


def test_sheets_sync_add_video_delegates_to_append(mock_sheets_service):
    with patch.object(SheetsSync, "_get_service", return_value=mock_sheets_service):
        sync = SheetsSync("test-sheet-id")
        with patch.object(sync, "append_row", return_value=True) as mock_append:
            result = sync.add_video(["row-data"])
            assert result is True
            mock_append.assert_called_once_with("Videos", ["row-data"])


def test_sheets_sync_add_album_delegates_to_append(mock_sheets_service):
    with patch.object(SheetsSync, "_get_service", return_value=mock_sheets_service):
        sync = SheetsSync("test-sheet-id")
        with patch.object(sync, "append_row", return_value=True) as mock_append:
            result = sync.add_album(["album-row"])
            assert result is True
            mock_append.assert_called_once_with("Albums", ["album-row"])


def test_sheets_sync_get_queue_empty_when_no_data(mock_sheets_service):
    with patch.object(SheetsSync, "_get_service", return_value=mock_sheets_service):
        mock_sheets_service.spreadsheets().values().get.return_value.execute.return_value = {}
        sync = SheetsSync("test-sheet-id")
        result = sync.get_queue()
        assert result == []


def test_sheets_sync_get_queue_parses_rows(mock_sheets_service):
    with patch.object(SheetsSync, "_get_service", return_value=mock_sheets_service):
        mock_sheets_service.spreadsheets().values().get.return_value.execute.return_value = {
            "values": [
                ["id", "status", "topic"],
                ["1", "pending", "Da Nang"],
                ["2", "done", "Phu Quoc"],
            ]
        }
        sync = SheetsSync("test-sheet-id")
        result = sync.get_queue()
        assert len(result) == 2
        assert result[0]["id"] == "1"
        assert result[0]["status"] == "pending"
        assert result[0]["topic"] == "Da Nang"
        assert result[1]["id"] == "2"


def test_sheets_sync_get_queue_single_row(mock_sheets_service):
    with patch.object(SheetsSync, "_get_service", return_value=mock_sheets_service):
        mock_sheets_service.spreadsheets().values().get.return_value.execute.return_value = {
            "values": [["col1", "col2"]]
        }
        sync = SheetsSync("test-sheet-id")
        result = sync.get_queue()
        assert result == []


# ─── DriveUploader tests ──────────────────────────────────────────────────────

from tools.drive_uploader import DriveUploader


def test_drive_uploader_no_credentials_returns_empty():
    uploader = DriveUploader()
    with patch.object(DriveUploader, "_get_service", return_value=None):
        assert uploader.upload_file("path/to/file.mp4", "folder-id") == {}
        assert uploader.create_subfolder("sub") == ""


def test_drive_uploader_upload_success():
    uploader = DriveUploader()
    mock_file = MagicMock()
    mock_file.get.side_effect = lambda k, default=None: {
        "id": "file-123", "name": "test.mp4", "webViewLink": "http://link"
    }.get(k, default)
    mock_service = MagicMock()
    mock_service.files().create.return_value.execute.return_value = mock_file

    with patch.object(DriveUploader, "_get_service", return_value=mock_service):
        with patch("tools.drive_uploader.MediaFileUpload"):
            result = uploader.upload_file("/tmp/test.mp4", "folder-abc", "test.mp4")
            assert result["id"] == "file-123"
            assert result["name"] == "test.mp4"


def test_drive_uploader_uses_filename_from_path():
    uploader = DriveUploader()
    mock_service = MagicMock()
    mock_file = MagicMock()
    mock_file.get.return_value = {"id": "f1", "name": "auto.mp4", "webViewLink": "url"}
    mock_service.files().create.return_value.execute.return_value = mock_file

    with patch.object(DriveUploader, "_get_service", return_value=mock_service):
        with patch("tools.drive_uploader.MediaFileUpload"):
            uploader.upload_file("/tmp/my-video.mp4", "folder-abc")
            call = mock_service.files().create.call_args
            assert call[1]["body"]["name"] == "my-video.mp4"


# ─── VoiceGenerator tests ─────────────────────────────────────────────────────

from tools.voice_generator import VoiceGenerator


def test_voice_generator_default_provider():
    gen = VoiceGenerator()
    assert gen.provider == "vbee"


def test_voice_generator_no_key_no_client(monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    gen = VoiceGenerator()
    assert gen._el_client is None


def test_voice_generator_falls_back_to_mock(monkeypatch):
    monkeypatch.delenv("VBEE_API_KEY", raising=False)
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    # Mock _edge_generate to return None to force fallback to mock WAV
    monkeypatch.setattr(VoiceGenerator, "_edge_generate", lambda self, *args, **kwargs: None)
    
    gen = VoiceGenerator()
    # Should fall back to generating a mock silent wav file
    audio_path = gen.generate_voice("Đây là bản thử nghiệm", "default", "test_fallback_audio")
    assert audio_path.endswith(".wav")
    assert os.path.exists(audio_path)
    # Clean up
    if os.path.exists(audio_path):
        os.remove(audio_path)


def test_voice_generator_clone_no_client(monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    gen = VoiceGenerator()
    voice_id = gen.clone_voice(["sample.wav"], "new-voice")
    assert voice_id.startswith("mock_clone_")


def test_voice_generator_edge_tts(monkeypatch):
    # Mock edge_tts.Communicate
    class MockCommunicateStream:
        def __init__(self, text, voice, rate, boundary):
            self.text = text
            self.voice = voice

        async def stream(self):
            # Yield dummy audio and word boundary events
            yield {"type": "audio", "data": b"dummy_audio_bytes"}
            yield {
                "type": "WordBoundary",
                "offset": 1000000,    # 0.1s
                "duration": 5000000,  # 0.5s
                "text": "test"
            }
            yield {
                "type": "WordBoundary",
                "offset": 7000000,    # 0.7s
                "duration": 4000000,  # 0.4s
                "text": "word"
            }

    import edge_tts
    monkeypatch.setattr(edge_tts, "Communicate", MockCommunicateStream)

    gen = VoiceGenerator(provider="edge")
    audio_path = gen.generate_voice("test word", "vi-VN-HoaiMyNeural", "test_edge_mock")
    
    assert audio_path.endswith(".mp3")
    assert os.path.exists(audio_path)
    
    words_path = audio_path.replace(".mp3", ".words.json")
    assert os.path.exists(words_path)
    
    # Verify word timing file contents
    import json
    with open(words_path, "r", encoding="utf-8") as f:
        words = json.load(f)
    
    assert len(words) == 2
    assert words[0]["word"] == "test"
    assert words[0]["start"] == 0.1
    assert words[0]["end"] == 0.6
    assert words[1]["word"] == "word"
    assert words[1]["start"] == 0.7
    assert words[1]["end"] == 1.1
    
    # Clean up
    if os.path.exists(audio_path):
        os.remove(audio_path)
    if os.path.exists(words_path):
        os.remove(words_path)


# ─── HookEffects and VideoEngine Hook tests ───────────────────────────────────

from tools.hook_effects import apply_hook_effect, get_hashtag, HOOK_PRESETS
from tools.video_renderer import VideoEngine


def test_get_hashtag():
    assert get_hashtag("Chào mừng bạn đến với Đà Lạt đẹp mộng mơ!") == "#toiladandalat"
    assert get_hashtag("Hành trình khám phá Phú Quốc 3 ngày 2 đêm") == "#khamphaphuquoc"
    assert get_hashtag("Chào các bạn!") == "#trending"


def test_apply_hook_effect_presets():
    # Test standard preset
    filter_expr = apply_hook_effect("0:v", "vout", "zoom_in", duration_sec=3.0)
    assert "[0:v]scale=" in filter_expr
    assert "zoompan" in filter_expr
    assert "[vout]" in filter_expr

    # Test new tiktok styles
    filter_tag = apply_hook_effect("0:v", "vout", "tiktok_tag_banner", duration_sec=3.0, hook_text="Đà Lạt có gì ngon?")
    assert "drawbox" in filter_tag
    assert "#toiladandalat" in filter_tag
    assert "drawtext" in filter_tag
    assert "textfile" in filter_tag

    filter_tag_pink = apply_hook_effect("0:v", "vout", "tiktok_tag_banner_pink", duration_sec=3.0, hook_text="Đà Lạt có gì ngon?")
    assert "color=0xD81B60@0.85" in filter_tag_pink

    filter_tag_green = apply_hook_effect("0:v", "vout", "tiktok_tag_banner_green", duration_sec=3.0, hook_text="Đà Lạt có gì ngon?")
    assert "color=0x005A36@0.85" in filter_tag_green

    filter_quote = apply_hook_effect("0:v", "vout", "tiktok_quote_card", duration_sec=3.0, hook_text="Đà Lạt có gì ngon?")
    assert "“" in filter_quote
    assert "”" in filter_quote
    assert "drawbox" in filter_quote
    assert "textfile" in filter_quote

    filter_floating = apply_hook_effect("0:v", "vout", "tiktok_floating_box", duration_sec=3.0, hook_text="Đà Lạt có gì ngon?")
    assert "box=1" in filter_floating
    assert "boxcolor=black@0.7" in filter_floating
    assert "textfile" in filter_floating



def test_video_engine_assemble_with_hook(tmp_path, monkeypatch):
    # Mock subprocess.run to verify FFmpeg is called with the hook filter complex
    called_cmds = []

    def mock_run(cmd, *args, **kwargs):
        called_cmds.append(cmd)
        
        # Return mock process success
        from unittest.mock import MagicMock
        r = MagicMock()
        r.returncode = 0
        r.stdout = "3.0"  # mock duration probe
        r.stderr = ""
        
        # If the command is writing a normalized output, we should write a dummy file
        # to satisfy the "file exists and size > 1000" check in _normalize_clip/_normalize_image
        output_file = cmd[-1]
        if isinstance(output_file, str) and (output_file.endswith(".mp4") or output_file.endswith(".wav")):
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            with open(output_file, "wb") as f:
                f.write(b"DUMMY_MP4_CONTENT_DUMMY_MP4_CONTENT" * 100) # > 1000 bytes
        return r

    import subprocess
    monkeypatch.setattr(subprocess, "run", mock_run)

    # Instantiate video engine
    engine = VideoEngine(output_dir=str(tmp_path))

    clips = [
        {"path": "", "duration": 3.0, "media_type": "clip", "scene_id": "scene_1", "description": "Hook Scene"},
        {"path": "", "duration": 4.0, "media_type": "clip", "scene_id": "scene_2", "description": "Body Scene"},
    ]

    out_path = engine.assemble_from_scenes(
        clips=clips,
        voiceover_path=None,
        output_name="test_hook_assemble",
        hook_style="tiktok_tag_banner",
        hook_text="Chào Đà Lạt!",
    )

    # Check that a path was returned
    assert os.path.exists(out_path)

    # Verify that apply_hook_effect was called and ffmpeg was spawned for it
    # We expect an ffmpeg command containing -filter_complex and the tag banner drawbox filter
    hook_apply_call = False
    for cmd in called_cmds:
        cmd_str = " ".join(cmd)
        if "-filter_complex" in cmd_str and "drawbox" in cmd_str and "#toiladandalat" in cmd_str:
            hook_apply_call = True
            break
            
    assert hook_apply_call, "FFmpeg was not called with the hook filter complex"

