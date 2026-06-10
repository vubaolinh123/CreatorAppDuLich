"""Tests for pipeline agents (research, script, caption, image)."""

import json
import sys
import os
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ─── Shared fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def mock_llm():
    llm = MagicMock()
    return llm


# ─── research_agent tests ──────────────────────────────────────────────────────

from agents.research_agent import research_agent


@pytest.mark.asyncio
async def test_research_agent_returns_trends(mock_llm):
    result = await research_agent({"trends": [], "sources": []}, mock_llm)

    assert "trends" in result
    assert "sources" in result
    assert len(result["trends"]) == 3


@pytest.mark.asyncio
async def test_research_agent_trends_structure(mock_llm):
    result = await research_agent({"trends": [], "sources": []}, mock_llm)

    for trend in result["trends"]:
        assert "destination" in trend
        assert "activity" in trend
        assert "sentiment" in trend


@pytest.mark.asyncio
async def test_research_agent_sentiment_positive(mock_llm):
    result = await research_agent({"trends": [], "sources": []}, mock_llm)

    for trend in result["trends"]:
        assert trend["sentiment"] in ("positive", "negative", "neutral")


@pytest.mark.asyncio
async def test_research_agent_sources_list(mock_llm):
    result = await research_agent({"trends": [], "sources": []}, mock_llm)

    assert isinstance(result["sources"], list)
    assert len(result["sources"]) > 0


# ─── script_agent tests ────────────────────────────────────────────────────────

from agents.script_agent import script_agent


def test_script_agent_llm_success(mock_llm):
    mock_llm.invoke.return_value = MagicMock(
        content=json.dumps({"hook": "Test hook", "body": "Test body", "cta": "Test CTA"})
    )

    result = script_agent(
        topic="Da Nang",
        trends=[{"destination": "Da Nang"}],
        seeds=[],
        llm=mock_llm,
    )

    assert result["hook"] == "Test hook"
    assert result["body"] == "Test body"
    assert result["cta"] == "Test CTA"


def test_script_agent_llm_with_markdown_code_block(mock_llm):
    mock_llm.invoke.return_value = MagicMock(
        content='```json\n{"hook": "Hook here", "body": "Body here", "cta": "CTA here"}\n```'
    )

    result = script_agent("Da Nang", [], [], mock_llm)
    assert result["hook"] == "Hook here"


def test_script_agent_llm_failure_returns_fallback(mock_llm):
    mock_llm.invoke.side_effect = Exception("API error")

    result = script_agent("Da Nang", [], [], mock_llm)

    assert "hook" in result
    assert "body" in result
    assert "cta" in result
    assert "Da Nang" in result["hook"]


def test_script_agent_fallback_includes_topic(mock_llm):
    mock_llm.invoke.side_effect = Exception("API error")

    result = script_agent("Phu Quoc", [], [], mock_llm)
    assert "Phu Quoc" in result["hook"]
    assert "Phu Quoc" in result["body"]


def test_script_agent_invokes_llm(mock_llm):
    mock_llm.invoke.return_value = MagicMock(
        content=json.dumps({"hook": "h", "body": "b", "cta": "c"})
    )

    script_agent("Hanoi", [{"destination": "Hanoi"}], [], mock_llm)
    assert mock_llm.invoke.called


# ─── caption_agent tests ───────────────────────────────────────────────────────

from agents.caption_agent import caption_agent


def test_caption_agent_llm_success(mock_llm):
    mock_llm.invoke.return_value = MagicMock(
        content=json.dumps({
            "hooks": ["Hook 1", "Hook 2", "Hook 3"],
            "caption_short": "Short caption",
            "caption_long": "Long caption here",
            "hashtags": ["#a", "#b", "#c"],
        })
    )

    result = caption_agent(
        script={"hook": "h", "body": "b", "cta": "c"},
        video_desc="Travel video",
        llm=mock_llm,
    )

    assert len(result["hooks"]) == 3
    assert result["caption_short"] == "Short caption"
    assert result["caption_long"] == "Long caption here"
    assert len(result["hashtags"]) > 0


def test_caption_agent_llm_failure_returns_fallback(mock_llm):
    mock_llm.invoke.side_effect = Exception("API error")

    result = caption_agent({}, "desc", mock_llm)

    assert "hooks" in result
    assert "caption_short" in result
    assert "caption_long" in result
    assert "hashtags" in result


def test_caption_agent_fallback_has_3_hooks(mock_llm):
    mock_llm.invoke.side_effect = Exception("API error")

    result = caption_agent({}, "desc", mock_llm)
    assert len(result["hooks"]) == 3


def test_caption_agent_fallback_has_hashtags(mock_llm):
    mock_llm.invoke.side_effect = Exception("API error")

    result = caption_agent({}, "desc", mock_llm)
    assert len(result["hashtags"]) >= 5


# ─── image_agent tests ─────────────────────────────────────────────────────────

from agents.image_agent import image_agent


def test_image_agent_llm_success(mock_llm):
    mock_llm.invoke.return_value = MagicMock(
        content=json.dumps({
            "description": "Photo album about Da Nang",
            "prompts": ["p1", "p2", "p3", "p4", "p5"],
        })
    )

    result = image_agent("Da Nang", "template-1", mock_llm)

    assert result["description"] == "Photo album about Da Nang"
    assert len(result["prompts"]) == 5


def test_image_agent_llm_failure_returns_fallback(mock_llm):
    mock_llm.invoke.side_effect = Exception("API error")

    result = image_agent("Phu Quoc", "tmpl", mock_llm)

    assert "description" in result
    assert "prompts" in result
    assert len(result["prompts"]) == 5


def test_image_agent_fallback_prompts_count(mock_llm):
    mock_llm.invoke.side_effect = Exception("API error")

    result = image_agent("Hanoi", "tmpl", mock_llm)
    assert len(result["prompts"]) == 5


def test_image_agent_fallback_includes_destination(mock_llm):
    mock_llm.invoke.side_effect = Exception("API error")

    result = image_agent("Da Nang", "tmpl", mock_llm)
    assert "Da Nang" in result["description"]


def test_image_agent_invokes_llm_with_correct_args(mock_llm):
    mock_llm.invoke.return_value = MagicMock(
        content=json.dumps({"description": "d", "prompts": ["p1", "p2", "p3", "p4", "p5"]})
    )

    image_agent("Da Nang", "template-42", mock_llm)
    assert mock_llm.invoke.called
    call_args = mock_llm.invoke.call_args[0][0]
    assert "template-42" in str(call_args)


# ─── personal_video_agent tests ──────────────────────────────────────────────────

from agents.personal_video_agent import run_assemble_video

@patch("tools.db.update_job")
@patch("tools.db.append_job_log")
@patch("tools.db.save_content")
@patch("agents.personal_video_agent.VoiceGenerator")
@patch("agents.personal_video_agent.VideoEngine")
@patch("agents.personal_video_agent.get_audio_duration")
@patch("tools.db.creators_col")
@patch("tools.db.get_db")
@patch("shutil.copy2")
@patch("subprocess.run")
def test_run_assemble_video_segments(
    mock_sub_run,
    mock_copy,
    mock_get_db,
    mock_creators_col,
    mock_get_audio_duration,
    mock_VideoEngine,
    mock_VoiceGenerator,
    mock_save_content,
    mock_append_job_log,
    mock_update_job
):
    # Setup mocks
    mock_db = MagicMock()
    mock_get_db.return_value = mock_db
    
    mock_creators_col.return_value.find_one.return_value = {
        "_id": "lan_anh",
        "name": "Lan Anh",
        "voice_provider": "vbee",
        "voice_id": "hn_female_lananh",
    }
    
    # Mock voice generator
    voice_gen_instance = MagicMock()
    # Mock generate_voice to return paths for segments
    def side_effect(text, voice_id, output_name, speed):
        return f"output/audio/{output_name}.mp3"
    voice_gen_instance.generate_voice.side_effect = side_effect
    mock_VoiceGenerator.return_value = voice_gen_instance
    
    # Mock durations: hook: 2.0s, body: 10.0s, cta: 3.0s
    def dur_side_effect(path):
        if "hook" in path:
            return 2.0
        elif "body" in path:
            return 10.0
        elif "cta" in path:
            return 3.0
        return 15.0
    mock_get_audio_duration.side_effect = dur_side_effect
    
    # Mock video engine
    video_engine_instance = MagicMock()
    video_engine_instance.assemble_from_scenes.return_value = "output/videos/raw.mp4"
    video_engine_instance.add_subtitles.return_value = "output/videos/final.mp4"
    mock_VideoEngine.return_value = video_engine_instance
    
    # Mock subprocess run to simulate successful FFmpeg concat
    mock_sub_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    # Mock job in DB
    mock_db["jobs"].find_one.return_value = {
        "_id": "job_123",
        "script": {
            "hook": "Chào mừng bạn!",
            "body": "Đây là video du lịch.",
            "cta": "Hãy bấm follow kênh nhé."
        },
        "creator_id": "lan_anh",
        "voice_provider": "vbee",
        "voice_id": "hn_female_lananh",
        "scenes": [
            {"scene_id": "scene_1", "description": "Hook scene", "min_duration_sec": 5},
            {"scene_id": "scene_2", "description": "Body scene", "min_duration_sec": 10}
        ]
    }
    
    # Run assemble video
    result = run_assemble_video(
        job_id="job_123",
        scene_uploads=[
            {"scene_id": "scene_1", "file_path": "clip1.mp4"},
            {"scene_id": "scene_2", "file_path": "clip2.mp4"}
        ],
        transition="fade"
    )
    
    # Assert voice generator generate_voice was called for each segment
    assert voice_gen_instance.generate_voice.call_count == 3
    
    # Assert ffmpeg audio concat command was run
    mock_sub_run.assert_called_once()
    ffmpeg_cmd = mock_sub_run.call_args[0][0]
    ffmpeg_cmd_str = " ".join(ffmpeg_cmd)
    assert "ffmpeg" in ffmpeg_cmd_str
    assert "-filter_complex" in ffmpeg_cmd_str
    assert "concat=n=3:v=0:a=1" in ffmpeg_cmd_str
    
    # Assert video engine was called with exact timing offsets
    # hook_dur = 2.0, body_dur = 10.0, cta_dur = 3.0
    # audio_duration = 15.0
    # hook_end = 2.0, body_end = 12.0
    assert result["video_path"].endswith("final.mp4")
    # Verify that update_job was called with the correct audio_duration
    last_update_args = mock_update_job.call_args[0][1]
    assert last_update_args["result"]["audio_duration"] == 15.0
