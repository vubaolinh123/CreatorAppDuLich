"""Caption Agent — Generates hooks, captions, and hashtags for social media.
High-volume, low-complexity — uses cheaper LLM (Haiku).
"""

import json
from typing import List
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_anthropic import ChatAnthropic


CAPTION_PROMPT = """Given a script and video description, generate:
(1) 3 hook variants (first 3 words that stop scroll),
(2) 2 caption options (1 short under 125 chars, 1 long under 2200 chars),
(3) 15 hashtags (5 broad, 5 niche, 5 location-specific).
Output JSON only with keys: hooks, caption_short, caption_long, hashtags"""


def caption_agent(script: dict, video_desc: str, llm: ChatAnthropic) -> dict:
    try:
        response = llm.invoke([
            SystemMessage(content=CAPTION_PROMPT),
            HumanMessage(content=f"Script: {json.dumps(script)}\nVideo: {video_desc}"),
        ])
        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        return json.loads(content)
    except Exception:
        return {
            "hooks": ["Xem ngay!", "Bạn không tin nổi", "Check this out"],
            "caption_short": "Khám phá điểm đến hot nhất hôm nay! #dulich",
            "caption_long": "Hôm nay mình mang đến cho các bạn những địa điểm cực hot!\n\nXem hết video để không bỏ lỡ nhé!\n\n#dulich #vietnam #travel",
            "hashtags": ["#dulich", "#vietnam", "#travel", "#xanh", "#review", "#phuquoc", "#danang", "#hanoi"],
        }
