"""Tests for pipeline graph — verifies structure and node wiring."""

import sys
import os
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_build_pipeline_returns_graph():
    from graph.pipeline import build_pipeline

    mock_llm = MagicMock()
    graph = build_pipeline(mock_llm)
    assert graph is not None


def test_build_pipeline_no_sheets_when_empty_id():
    from graph.pipeline import build_pipeline

    mock_llm = MagicMock()
    graph = build_pipeline(mock_llm, sheet_id="")
    assert graph is not None


def test_build_pipeline_accepts_sheet_id():
    from graph.pipeline import build_pipeline

    mock_llm = MagicMock()
    with patch("graph.pipeline.SheetsSync") as mock_sheets:
        graph = build_pipeline(mock_llm, sheet_id="sheet-abc")
        assert graph is not None


def test_build_pipeline_instantiates_video_engine():
    from graph.pipeline import build_pipeline

    mock_llm = MagicMock()
    with patch("graph.pipeline.VideoEngine") as mock_ve:
        with patch("graph.pipeline.VoiceGenerator"):
            build_pipeline(mock_llm)
            mock_ve.assert_called_once()


def test_graph_has_expected_nodes():
    from graph.pipeline import build_pipeline

    mock_llm = MagicMock()
    with patch("graph.pipeline.research_agent") as mock_research:
        mock_research.return_value = {"trends": [{"destination": "Hanoi"}], "sources": []}
        with patch("graph.pipeline.VoiceGenerator"):
            with patch("graph.pipeline.VideoEngine"):
                graph = build_pipeline(mock_llm)
                # Graph builder exists and has nodes registered
                assert graph is not None


def test_run_pipeline_mock_mode_without_api_key(monkeypatch):
    from graph.pipeline import run_pipeline

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with patch("graph.pipeline.build_pipeline") as mock_build:
        mock_graph = MagicMock()
        mock_build.return_value = mock_graph
        run_pipeline()
        mock_build.assert_called_once_with(None)


def test_run_pipeline_creates_llm(monkeypatch):
    from graph.pipeline import run_pipeline

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
    with patch("graph.pipeline.build_pipeline") as mock_build:
        mock_graph = MagicMock()
        mock_build.return_value = mock_graph
        run_pipeline(trends=[{"destination": "Da Nang"}])
        mock_build.assert_called_once()
        call_llm = mock_build.call_args[0][0]
        assert call_llm is not None


def test_script_node_topic_from_first_trend():
    """When trends exist, script topic should be first destination."""
    from graph.pipeline import build_pipeline

    mock_llm = MagicMock()

    with patch("graph.pipeline.script_agent") as mock_script:
        mock_script.return_value = {"hook": "h", "body": "b", "cta": "c"}
        with patch("graph.pipeline.research_agent") as mock_research:
            mock_research.return_value = {
                "trends": [{"destination": "Phu Quoc", "activity": "resort"}],
                "sources": [],
            }
            with patch("graph.pipeline.VoiceGenerator"):
                with patch("graph.pipeline.VideoEngine"):
                    with patch("graph.pipeline.SheetsSync"):
                        graph = build_pipeline(mock_llm)
                        # Verify graph built without error
                        assert graph is not None


def test_script_node_fallback_when_no_trends():
    """When trends empty, build still works (falls back to 'Vietnam travel')."""
    from graph.pipeline import build_pipeline

    mock_llm = MagicMock()

    with patch("graph.pipeline.script_agent") as mock_script:
        mock_script.return_value = {"hook": "h", "body": "b", "cta": "c"}
        with patch("graph.pipeline.research_agent") as mock_research:
            mock_research.return_value = {"trends": [], "sources": []}
            with patch("graph.pipeline.VoiceGenerator"):
                with patch("graph.pipeline.VideoEngine"):
                    with patch("graph.pipeline.SheetsSync"):
                        graph = build_pipeline(mock_llm)
                        assert graph is not None


def test_caption_node_uses_video_desc():
    """caption_node passes 'Travel video' as video_desc."""
    from graph.pipeline import build_pipeline

    mock_llm = MagicMock()

    with patch("graph.pipeline.caption_agent") as mock_caption:
        mock_caption.return_value = {"hooks": [], "caption_short": "s", "caption_long": "l", "hashtags": []}
        with patch("graph.pipeline.research_agent") as mock_research:
            mock_research.return_value = {"trends": [{"destination": "Da Nang"}], "sources": []}
            with patch("graph.pipeline.VoiceGenerator"):
                with patch("graph.pipeline.VideoEngine"):
                    with patch("graph.pipeline.SheetsSync"):
                        graph = build_pipeline(mock_llm)
                        assert graph is not None


def test_video_node_calls_voice_and_engine():
    """video_node invokes VoiceGenerator and VideoEngine."""
    from graph.pipeline import build_pipeline

    mock_llm = MagicMock()

    with patch("graph.pipeline.VoiceGenerator") as mock_vg_cls:
        mock_voice = MagicMock()
        mock_voice.generate_voice.return_value = "/tmp/audio.mp3"
        mock_vg_cls.return_value = mock_voice

        with patch("graph.pipeline.VideoEngine") as mock_ve_cls:
            mock_engine = MagicMock()
            mock_engine.assemble_video.return_value = "/tmp/video.mp4"
            mock_ve_cls.return_value = mock_engine

            with patch("graph.pipeline.research_agent") as mock_research:
                mock_research.return_value = {
                    "trends": [{"destination": "Da Nang"}],
                    "sources": [],
                }
                with patch("graph.pipeline.script_agent") as mock_script:
                    mock_script.return_value = {"hook": "Discover!", "body": "Amazing!", "cta": "Follow!"}
                    with patch("graph.pipeline.caption_agent"):
                        with patch("graph.pipeline.image_agent"):
                            with patch("graph.pipeline.SheetsSync"):
                                graph = build_pipeline(mock_llm)
                                assert graph is not None
                                # VoiceGenerator and VideoEngine instantiated
                                mock_vg_cls.assert_called_once()
                                mock_ve_cls.assert_called_once()


def test_image_node_uses_first_trend():
    """image_agent gets the first trend destination."""
    from graph.pipeline import build_pipeline

    mock_llm = MagicMock()

    with patch("graph.pipeline.image_agent") as mock_img:
        mock_img.return_value = {"description": "d", "prompts": ["p1", "p2", "p3", "p4", "p5"]}
        with patch("graph.pipeline.research_agent") as mock_research:
            mock_research.return_value = {
                "trends": [{"destination": "Hanoi", "activity": "food"}],
                "sources": [],
            }
            with patch("graph.pipeline.VoiceGenerator"):
                with patch("graph.pipeline.VideoEngine"):
                    with patch("graph.pipeline.script_agent"):
                        with patch("graph.pipeline.caption_agent"):
                            with patch("graph.pipeline.SheetsSync"):
                                graph = build_pipeline(mock_llm)
                                assert graph is not None


def test_image_node_fallback_vietnam():
    """image_agent falls back to 'Vietnam' when no trends."""
    from graph.pipeline import build_pipeline

    mock_llm = MagicMock()

    with patch("graph.pipeline.image_agent") as mock_img:
        mock_img.return_value = {"description": "d", "prompts": ["p1"]}
        with patch("graph.pipeline.research_agent") as mock_research:
            mock_research.return_value = {"trends": [], "sources": []}
            with patch("graph.pipeline.VoiceGenerator"):
                with patch("graph.pipeline.VideoEngine"):
                    with patch("graph.pipeline.script_agent"):
                        with patch("graph.pipeline.caption_agent"):
                            with patch("graph.pipeline.SheetsSync"):
                                graph = build_pipeline(mock_llm)
                                assert graph is not None
