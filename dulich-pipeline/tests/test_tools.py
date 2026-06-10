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
