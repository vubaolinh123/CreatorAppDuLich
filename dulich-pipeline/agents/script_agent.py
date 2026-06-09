"""Script Agent — Writes video scripts with optional seeding integration.
Generates Vietnamese travel video scripts in 60-second format.
"""

import json
from typing import List
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_anthropic import ChatAnthropic


SCRIPT_SYSTEM_PROMPT = """You are a Vietnamese travel video scriptwriter.
Write a 60-second script for the topic: {topic}.
Structure: Hook (0-5s) -> Destination showcase (5-40s) -> Call to action (40-60s).
Seed mentions: {seeds} -- integrate naturally, not as ads.
Tone: Energetic, authentic, cinematic.
Language: Vietnamese with travel-specific vocabulary.
Output JSON only: {{"hook": "...", "body": "...", "cta": "..."}}"""


def script_agent(
    topic: str,
    trends: List[dict],
    seeds: List[dict],
    llm: ChatAnthropic,
) -> dict:
    prompt = SCRIPT_SYSTEM_PROMPT.format(
        topic=topic,
        seeds=json.dumps(seeds),
    )

    try:
        response = llm.invoke([
            SystemMessage(content=prompt),
            HumanMessage(content=f"Trends context: {json.dumps(trends)}"),
        ])
        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        return json.loads(content)
    except Exception:
        return {
            "hook": f"Bạn đã nghe về {topic} chưa?",
            "body": f"Hôm nay mình sẽ review {topic} cho các bạn biết nhé!",
            "cta": "Follow để xem thêm nội dung du lịch mỗi ngày!",
        }
