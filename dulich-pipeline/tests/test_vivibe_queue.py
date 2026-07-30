"""Concurrency and strict-provider tests for ViVibe TTS."""

from __future__ import annotations

import io
import os
import subprocess
import threading
import time
import wave
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from tools import list_review_render
from tools.voice_generator import VoiceGenerator


def test_vivibe_shared_key_serializes_threads(monkeypatch, tmp_path):
    active = 0
    max_active = 0
    guard = threading.Lock()

    def fake_once(self, text, voice_id, speed):
        nonlocal active, max_active
        with guard:
            active += 1
            max_active = max(max_active, active)
        try:
            time.sleep(0.04)
            return b"audio" * 200
        finally:
            with guard:
                active -= 1

    def fake_write(data, output_path):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(data)

    monkeypatch.setenv("API_VIVIBE_KEY", "one-shared-key")
    monkeypatch.setenv("VIVIBE_LOCK_DIR", str(tmp_path / "locks"))
    monkeypatch.setenv("VIVIBE_LOCK_TIMEOUT_SECONDS", "5")
    monkeypatch.setattr("tools.voice_generator.OUTPUT_DIR", tmp_path / "audio")
    monkeypatch.setattr(VoiceGenerator, "_vivibe_once", fake_once)
    monkeypatch.setattr(
        VoiceGenerator, "_write_vivibe_mp3", staticmethod(fake_write)
    )

    def generate(index):
        generator = VoiceGenerator(provider="vivibe")
        return generator.generate_voice(
            f"Nội dung {index}",
            "thu_review",
            f"voice-{index}",
        )

    with ThreadPoolExecutor(max_workers=6) as executor:
        paths = list(executor.map(generate, range(6)))

    assert max_active == 1
    assert len(set(paths)) == 6
    assert all(Path(path).is_file() for path in paths)


def test_vivibe_busy_export_waits_and_retries(monkeypatch):
    submit_count = 0

    class Response:
        status_code = 200
        text = ""

        def __init__(self, payload):
            self.payload = payload

        def json(self):
            return self.payload

    class AudioResponse:
        content = b"valid-audio" * 100

        @staticmethod
        def raise_for_status():
            return None

    def fake_post(url, **kwargs):
        nonlocal submit_count
        submit_count += 1
        if submit_count == 1:
            return Response(
                {
                    "error": {
                        "code": "INTERNAL_ERROR",
                        "message": (
                            "You already have an export in progress. "
                            "Please wait for it to complete."
                        ),
                    }
                }
            )
        return Response({"result": {"url": "https://cdn.example/audio"}})

    monkeypatch.setenv("API_VIVIBE_KEY", "busy-key")
    monkeypatch.setenv("VIVIBE_BUSY_RETRY_SECONDS", "3")
    monkeypatch.setenv("VIVIBE_POLL_INTERVAL_SECONDS", "0.5")
    monkeypatch.setattr("tools.voice_generator._requests.post", fake_post)
    monkeypatch.setattr(
        "tools.voice_generator._requests.get",
        lambda url, **kwargs: AudioResponse(),
    )

    generator = VoiceGenerator(provider="vivibe")
    data = generator._vivibe_once("Xin chào", "voice-id", 1.0)

    assert data == AudioResponse.content
    assert submit_count == 2


def test_vivibe_wav_is_normalized_to_real_mp3(tmp_path):
    raw = io.BytesIO()
    with wave.open(raw, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b"\x00\x00" * 3200)

    output = tmp_path / "voice.mp3"
    VoiceGenerator._write_vivibe_mp3(raw.getvalue(), output)

    assert output.read_bytes()[:3] == b"ID3"
    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=format_name",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "mp3" in probe.stdout


def _run_listreview_job(monkeypatch, payload: dict) -> dict:
    """Run _execute_durable_job for a list-review job, return the spec it rendered."""
    import server
    from tools import list_review_render as lrr

    captured: dict = {}

    def fake_render(spec):
        captured.update(spec)
        return {"success": True, "video_path": "/tmp/out.mp4"}

    monkeypatch.setattr(server, "_find_product", lambda job_id: None)
    monkeypatch.setattr(lrr, "render_list_review", fake_render)
    monkeypatch.setattr(server, "_render_product_from_result", lambda *a, **k: {})

    server._execute_durable_job(
        {"id": "job-1", "kind": "listreview_video", "owner": "nv1", "payload": payload}
    )
    return captured


def test_listreview_payload_voice_reaches_renderer(monkeypatch):
    """The UI sends voice_mode beside `spec`; it must land on spec.voice_provider."""
    spec = {
        "overlay_engine": "pil",
        "intro": {"scene_id": "intro", "vo": "Mở đầu"},
        "spots": [{"scene_id": "spot1", "vo": "Quán một"}],
        "outro": {"scene_id": "outro", "vo": "Kết thúc"},
    }
    payload = {
        "spec": spec,
        "voice_mode": "vivibe",
        "voice_id": "thu_review",
        "upload_files": [{"field": "intro__0", "path": "/tmp/intro.mp4"}],
    }

    rendered = _run_listreview_job(monkeypatch, payload)

    assert rendered["voice_provider"] == "vivibe"
    assert rendered["voice_id"] == "thu_review"


def test_listreview_voice_reaches_renderer_without_uploads(monkeypatch):
    """The `else payload['spec']` branch (no upload_files) must wire voice too."""
    payload = {
        "spec": {"intro": {"vo": "Mở đầu"}, "spots": [], "outro": {"vo": "Hết"}},
        "voice_mode": "chirp",
        "voice_id": "Aoede",
    }

    rendered = _run_listreview_job(monkeypatch, payload)

    assert rendered["voice_provider"] == "chirp"
    assert rendered["voice_id"] == "Aoede"


def test_listreview_legacy_spec_voice_is_preserved(monkeypatch):
    """Old queued jobs carry the voice inside spec and no voice_mode; keep it."""
    payload = {
        "spec": {
            "voice_provider": "vbee",
            "voice_id": "c_lamdong_female_giongmenmendalatnow_zero_shot_review_vc",
            "intro": {"vo": "Mở đầu"},
            "spots": [],
            "outro": {"vo": "Hết"},
        }
    }

    rendered = _run_listreview_job(monkeypatch, payload)

    assert rendered["voice_provider"] == "vbee"
    assert rendered["voice_id"].startswith("c_lamdong_female")


def test_vivibe_reads_at_natural_speed():
    """1.08 rushes ViVibe enough that Whisper drops words and captions fall back."""
    assert list_review_render._vo_speed("vivibe") == 1.0
    assert list_review_render._vo_speed("lucylab") == 1.0
    assert list_review_render._vo_speed("chirp") == 1.08
    assert list_review_render._vo_speed("") == 1.08


def test_whisper_hallucination_retries_without_prompt(monkeypatch, tmp_path):
    """Whisper slips into a canned YouTube outro; the no-prompt retry recovers it."""
    vo_text = "Muốn đi Đà Lạt cho đáng thì sáng chịu khó dậy sớm một chút nha"
    hallucination = [
        {"word": w, "start": i * 0.1, "end": i * 0.1 + 0.09}
        for i, w in enumerate("Hãy subscribe cho kênh Ghiền Mì Gõ".split())
    ]
    real = [
        {"word": w, "start": i * 0.6, "end": i * 0.6 + 0.55}
        for i, w in enumerate(vo_text.split())
    ]
    calls: list[str] = []

    def fake_whisper(path, prompt):
        calls.append(prompt)
        return hallucination if prompt else real

    monkeypatch.setattr(list_review_render, "_whisper_words", fake_whisper)
    mp3 = tmp_path / "seg.mp3"
    mp3.write_bytes(b"audio")

    words = list_review_render._word_timings(str(mp3), vo_text, dur=8.0)

    assert words == real
    assert len(calls) == 2 and calls[0] and calls[1] == ""
    assert mp3.with_suffix(".words.json").is_file()


def test_whisper_prompt_result_is_kept_when_valid(monkeypatch, tmp_path):
    """A good prompted read must not trigger a second, slower call."""
    vo_text = "Trưa thì đừng có ngồi lì trong quán cà phê nữa nha bạn"
    good = [
        {"word": w, "start": i * 0.6, "end": i * 0.6 + 0.55}
        for i, w in enumerate(vo_text.split())
    ]
    calls: list[str] = []

    def fake_whisper(path, prompt):
        calls.append(prompt)
        return good

    monkeypatch.setattr(list_review_render, "_whisper_words", fake_whisper)
    mp3 = tmp_path / "seg.mp3"
    mp3.write_bytes(b"audio")

    words = list_review_render._word_timings(str(mp3), vo_text, dur=7.0)

    assert words == good
    assert len(calls) == 1


def test_list_review_stops_if_any_vivibe_segment_fails(monkeypatch, tmp_path):
    monkeypatch.setattr(
        list_review_render,
        "render_html_overlays",
        lambda *args, **kwargs: {},
    )

    def fake_segment(kind, seg, idx, *args, **kwargs):
        if idx == 1:
            raise RuntimeError("ViVibe test failure")
        path = tmp_path / f"segment-{idx}.mp4"
        path.write_bytes(b"placeholder")
        return str(path)

    monkeypatch.setattr(list_review_render, "_render_segment", fake_segment)
    result = list_review_render.render_list_review(
        {
            "job_id": "strict-vivibe",
            "voice_provider": "vivibe",
            "voice_id": "thu_review",
            "intro": {"vo": "Mở đầu"},
            "spots": [{"vo": "Nội dung"}],
            "outro": {"vo": "Kết thúc"},
        }
    )

    assert result["success"] is False
    assert "tránh dùng sai giọng" in result["error"]
    assert "ViVibe test failure" in result["error"]
