"""Tests for pipeline config module."""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import PipelineConfig


# ─── Defaults ─────────────────────────────────────────────────────────────────

def test_default_keys_are_empty():
    cfg = PipelineConfig()
    assert cfg.anthropic_api_key == ""
    assert cfg.elevenlabs_api_key == ""
    assert cfg.google_sheet_id == ""


def test_default_creator_voices_are_empty():
    cfg = PipelineConfig()
    for i in range(1, 6):
        assert cfg.creator_voices[f"creator{i}"] == ""


def test_default_output_dir():
    cfg = PipelineConfig()
    assert cfg.output_dir == "./output"


def test_default_voice_provider():
    cfg = PipelineConfig()
    assert cfg.voice_provider == "vbee"


# ─── Output path properties ───────────────────────────────────────────────────

def test_output_video_dir():
    cfg = PipelineConfig(output_dir="./output")
    assert cfg.output_video_dir == "./output/videos"


def test_output_audio_dir():
    cfg = PipelineConfig(output_dir="./output")
    assert cfg.output_audio_dir == "./output/audio"


def test_output_image_dir():
    cfg = PipelineConfig(output_dir="./output")
    assert cfg.output_image_dir == "./output/images"


def test_output_dirs_custom():
    cfg = PipelineConfig(output_dir="/tmp/dulich")
    assert cfg.output_video_dir == "/tmp/dulich/videos"
    assert cfg.output_audio_dir == "/tmp/dulich/audio"
    assert cfg.output_image_dir == "/tmp/dulich/images"


# ─── Explicit values ──────────────────────────────────────────────────────────

def test_explicit_api_key():
    cfg = PipelineConfig(anthropic_api_key="sk-ant-test123")
    assert cfg.anthropic_api_key == "sk-ant-test123"


def test_explicit_elevenlabs_key():
    cfg = PipelineConfig(elevenlabs_api_key="el-test456")
    assert cfg.elevenlabs_api_key == "el-test456"


def test_explicit_sheet_id():
    cfg = PipelineConfig(google_sheet_id="sheet-abc-123")
    assert cfg.google_sheet_id == "sheet-abc-123"


# ─── Creator voices ───────────────────────────────────────────────────────────

def test_custom_creator_voices():
    custom = {
        "creator1": "v1", "creator2": "v2", "creator3": "v3",
        "creator4": "v4", "creator5": "v5",
    }
    cfg = PipelineConfig(creator_voices=custom)
    assert cfg.creator_voices == custom


def test_creator_voices_keys_populated_from_env(monkeypatch):
    monkeypatch.setenv("CREATOR1_VOICE_ID", "voice-1")
    monkeypatch.setenv("CREATOR3_VOICE_ID", "voice-3")
    cfg = PipelineConfig()
    assert cfg.creator_voices["creator1"] == "voice-1"
    assert cfg.creator_voices["creator3"] == "voice-3"
    assert cfg.creator_voices["creator2"] == ""


# ─── google_credentials_path ──────────────────────────────────────────────────

def test_default_credentials_path():
    cfg = PipelineConfig()
    assert cfg.google_credentials_path == "credentials.json"


def test_custom_credentials_path():
    cfg = PipelineConfig(google_credentials_path="/path/to/creds.json")
    assert cfg.google_credentials_path == "/path/to/creds.json"
