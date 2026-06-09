"""
Research Agent — Scrapes tourism trends daily from multiple sources.
Uses Playwright for web scraping + Context7 MCP for structured data lookups.
"""

import asyncio
import json
from typing import Annotated, List
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages


class ResearchState:
    trends: List[dict]
    sources: List[str]
    messages: Annotated[list, add_messages]


async def research_agent(state: ResearchState, llm: ChatAnthropic) -> dict:
    system_prompt = """You are a tourism trend researcher for Vietnamese travel content.
Given a list of scraped headlines and social media posts, extract:
(1) top 3 emerging destinations,
(2) viral activity types,
(3) sentiment signals.
Format as structured JSON. Do not add destinations not present in the source data."""

    # TODO: Integrate Playwright MCP for scraping
    # For now, return structured placeholder
    result = {
        "trends": [
            {"destination": "Đà Nẵng", "activity": "beach", "sentiment": "positive"},
            {"destination": "Phú Quốc", "activity": "resort", "sentiment": "positive"},
            {"destination": "Hà Giang", "activity": "trekking", "sentiment": "positive"},
        ],
        "sources": ["google_trends", "tiktok_trending", "travel_news"],
    }

    return {"trends": result["trends"], "sources": result["sources"]}


def build_research_graph(llm: ChatAnthropic) -> StateGraph:
    builder = StateGraph(ResearchState)
    builder.add_node("research", lambda s: asyncio.run(research_agent(s, llm)))
    builder.add_edge(START, "research")
    builder.add_edge("research", END)
    return builder
