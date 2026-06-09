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
