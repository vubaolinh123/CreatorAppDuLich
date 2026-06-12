"""vision_provider.py — Vision AI abstraction layer for Gemini & GPT-4o.

Provides a unified interface to analyze Canva frame images and extract
structural metadata (transparent regions, borders, text areas, style).
"""

from __future__ import annotations

import base64
import json
import os
import re
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional


FRAME_ANALYSIS_PROMPT = """You are analyzing a Canva frame template (PNG with transparent areas).
This frame will be overlaid on travel photos to create social media images.

Analyze this frame and return ONLY valid JSON (no markdown, no extra text) matching this schema:
{
  "border": {"top": <int>, "bottom": <int>, "left": <int>, "right": <int>, "style": "<solid|gradient|dashed>", "dominant_colors": ["<hex>", ...]},
  "header": {"exists": <bool>, "height": <int>, "background": "<dark_solid|light_solid|gradient|none>", "text_areas": [{"x": <int>, "y": <int>, "type": "<title|subtitle>", "align": "<left|center|right>"}]},
  "footer": {"exists": <bool>, "height": <int>, "text_areas": [...]},
  "decorations": [{"type": "<logo_ellipse|accent_line|icon|shape>", "x": <int>, "y": <int>, "w": <int>, "h": <int>}],
  "style_tags": ["<tag>", ...],
  "color_palette": ["<hex>", ...]
}

Rules:
- border.style must be one of: solid, gradient, dashed
- header.background must be one of: dark_solid, light_solid, gradient, none
- style_tags should be 3-5 words like: modern, vintage, tropical, minimal, bold, elegant, travel, luxury
- color_palette should be 3-6 hex colors extracted from the frame
- If a section does not exist, set exists: false and omit sub-fields
- x,y are pixel coordinates, measured from top-left"""


class VisionProvider(ABC):
    """Abstract base for vision AI providers."""

    @abstractmethod
    def analyze_frame(self, image_path: str) -> dict:
        """Analyze a Canva frame image, return structural metadata dict."""
        ...

    @classmethod
    def from_config(cls) -> Optional["VisionProvider"]:
        """Factory: return best available provider based on configured API keys."""
        from config import config

        if config.gemini_api_key:
            return GeminiVisionProvider(config.gemini_api_key)
        if config.openai_api_key:
            return OpenAIVisionProvider(config.openai_api_key)
        return None

    @staticmethod
    def _parse_json(text: str) -> dict:
        """Safely extract JSON from LLM response (handles markdown fences)."""
        # Strip markdown code fences
        text = re.sub(r"```(?:json)?\s*", "", text).strip()
        # Find first { and last }
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            text = text[start : end + 1]
        return json.loads(text)


class GeminiVisionProvider(VisionProvider):
    """Vision analysis via Google Gemini (gemini-2.0-flash)."""

    def __init__(self, api_key: str):
        try:
            import google.generativeai as genai

            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel("gemini-2.0-flash")
        except ImportError:
            print("[Vision] google-generativeai not installed, falling back", file=sys.stderr)
            raise

    def analyze_frame(self, image_path: str) -> dict:
        import PIL.Image

        img = PIL.Image.open(image_path)
        response = self.model.generate_content([FRAME_ANALYSIS_PROMPT, img])
        return self._parse_json(response.text)


class OpenAIVisionProvider(VisionProvider):
    """Vision analysis via OpenAI GPT-4o."""

    def __init__(self, api_key: str):
        try:
            from openai import OpenAI

            self.client = OpenAI(api_key=api_key)
        except ImportError:
            print("[Vision] openai not installed, falling back", file=sys.stderr)
            raise

    def analyze_frame(self, image_path: str) -> dict:
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()

        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": FRAME_ANALYSIS_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{b64}",
                                "detail": "high",
                            },
                        },
                    ],
                }
            ],
            response_format={"type": "json_object"},
        )
        return json.loads(response.choices[0].message.content)
