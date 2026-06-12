"""frame_selector.py — AI-powered frame selection from learned templates.

Given a topic, title, and format, picks the best matching frame from
the MongoDB frame_templates collection using a scoring algorithm.
"""

from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Optional

from tools.db import frame_templates_col, frame_feedback_col


# Topic-to-style keyword mapping for scoring
TOPIC_STYLE_MAP: dict[str, list[str]] = {
    "biển": ["beach", "ocean", "tropical", "summer", "blue"],
    "núi": ["mountain", "nature", "adventure", "green", "earthy"],
    "ẩm thực": ["food", "warm", "bold", "vibrant", "red"],
    "thành phố": ["modern", "urban", "neon", "minimal", "gray"],
    "cổ điển": ["vintage", "retro", "warm", "gold", "elegant"],
    "sang trọng": ["luxury", "gold", "elegant", "dark", "premium"],
    "thiên nhiên": ["nature", "green", "fresh", "earthy", "calm"],
    "vui chơi": ["fun", "vibrant", "colorful", "bold", "playful"],
    "lãng mạn": ["romantic", "soft", "pink", "warm", "elegant"],
    "mạo hiểm": ["adventure", "bold", "dark", "rugged", "urban"],
}

# Default weights when no specific style match
DEFAULT_STYLE_WEIGHTS = {
    "match_topic_style": 30,
    "usage_distribution": 10,
    "format_compatibility": 25,
    "random_jitter": 5,
}


def _topic_to_keywords(topic: str) -> list[str]:
    """Extract relevant style keywords from the topic string."""
    topic_lower = topic.lower()
    keywords = []
    for key, vals in TOPIC_STYLE_MAP.items():
        if key in topic_lower:
            keywords.extend(vals)
    return keywords


def _score_style_match(topic_keywords: list[str], frame_tags: list[str]) -> int:
    """Score how well frame style tags match topic keywords."""
    if not topic_keywords or not frame_tags:
        return 15  # neutral score
    ft_lower = [t.lower() for t in frame_tags]
    matches = sum(1 for kw in topic_keywords if any(kw in ft for ft in ft_lower))
    return min(30, matches * 10)


def _score_color_harmony(topic: str, palette: list[str]) -> int:
    """Simple bonus for frames with appropriate color palettes."""
    topic_lower = topic.lower()
    # Warm tones for food, cool for beach, etc.
    warm_keywords = ["ẩm thực", "food", "cafe", "ấm cúng", "hoàng hôn"]
    cool_keywords = ["biển", "núi", "thiên nhiên", "hồ", "sông"]

    has_warm = any(k in topic_lower for k in warm_keywords)
    has_cool = any(k in topic_lower for k in cool_keywords)

    if not palette:
        return 10

    # Rough warm/cool detection from hex
    warm_count = 0
    cool_count = 0
    for c in palette:
        c = c.lstrip("#")
        if len(c) != 6:
            continue
        r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
        if r > g + 30 and r > b + 30:
            warm_count += 1
        elif b > r + 30 and b > g + 30:
            cool_count += 1

    if has_warm and warm_count > cool_count:
        return 20
    if has_cool and cool_count > warm_count:
        return 20
    return 10


def select_best_frame(
    topic: str,
    title: str = "",
    format_name: str = "story",
    creator_id: Optional[str] = None,
    prefer_frame_id: Optional[str] = None,
) -> Optional[dict]:
    """Select the best frame template for the given content parameters.

    Args:
        topic: Travel destination / content topic.
        title: Album title (may influence style).
        format_name: Target format key (story, feed_square, etc.).
        creator_id: Optional — prefer frames this creator has liked.
        prefer_frame_id: Optional — force a specific frame.

    Returns:
        Frame template dict from MongoDB, or None if no frames exist.
    """
    from config import config

    if prefer_frame_id:
        frame = frame_templates_col().find_one({"frame_id": prefer_frame_id})
        if frame:
            return frame
        print(f"[FrameSelector] Requested frame '{prefer_frame_id}' not found, falling back")

    # Get all frames compatible with this format
    candidates = list(
        frame_templates_col().find(
            {"compatible_formats": format_name}
        )
    )

    # Fallback: any frame if none match format
    if not candidates:
        candidates = list(frame_templates_col().find())

    if not candidates:
        print("[FrameSelector] No learned frames available")
        return None

    topic_kw = _topic_to_keywords(topic)

    # Score each candidate
    scored: list[tuple[float, dict]] = []
    for frame in candidates:
        analysis = frame.get("analysis", {})
        score = 0.0

        # Style match
        score += _score_style_match(topic_kw, analysis.get("style_tags", []))

        # Color harmony
        score += _score_color_harmony(topic, analysis.get("color_palette", []))

        # Format compatibility bonus
        if format_name in frame.get("compatible_formats", []):
            score += 25

        # Usage distribution — prefer less-used frames
        usage = frame.get("usage_count", 0)
        score += max(0, 10 - usage)

        # Creator preference (feedback-based)
        if creator_id:
            feedbacks = list(
                frame_feedback_col().find(
                    {"frame_id": frame["frame_id"], "creator_id": creator_id, "action": "like"}
                )
            )
            if feedbacks:
                score += 20

        # Small random jitter to avoid always picking the same frame
        score += random.uniform(0, 5)

        scored.append((score, frame))

    scored.sort(key=lambda x: -x[0])
    best = scored[0][1]

    # Increment usage count
    frame_templates_col().update_one(
        {"frame_id": best["frame_id"]},
        {
            "$inc": {"usage_count": 1},
            "$set": {"last_used_at": datetime.now(timezone.utc).isoformat()},
        },
    )

    print(f"[FrameSelector] Selected frame '{best.get('name', best['frame_id'])}' "
          f"(score: {scored[0][0]:.1f}, {len(candidates)} candidates)")
    return best


def record_feedback(
    frame_id: str, creator_id: str, action: str, context: Optional[dict] = None
) -> None:
    """Record user feedback on a frame (like/reject) for future selection."""
    doc = {
        "frame_id": frame_id,
        "creator_id": creator_id,
        "action": action,
        "context": context or {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    frame_feedback_col().insert_one(doc)
    print(f"[FrameSelector] Feedback recorded: {creator_id} {action} {frame_id}")
