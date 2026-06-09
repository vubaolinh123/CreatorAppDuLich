"""LangGraph Pipeline — Main content production graph.
Orchestrates: Research -> Script + Caption(parallel) -> Video -> Image
"""

import os
from typing import Annotated, List, TypedDict
import operator
from langgraph.graph import StateGraph, START, END
from langchain_anthropic import ChatAnthropic

from agents.research_agent import research_agent
from agents.script_agent import script_agent
from agents.caption_agent import caption_agent
from agents.image_agent import image_agent
from tools.video_renderer import VideoEngine
from tools.voice_generator import VoiceGenerator
from tools.sheets_sync import SheetsSync


class PipelineState(TypedDict):
    trends: Annotated[list, operator.add]
    script: dict
    captions: dict
    video_path: str
    image_assets: list
    drive_links: dict
    status: str


def _script_ready(state: PipelineState) -> str:
    return "video" if state.get("script") else END


def _video_done(state: PipelineState) -> str:
    return "image" if state.get("video_path") else END


def build_pipeline(
    llm: ChatAnthropic,
    sheet_id: str = "",
    voice_provider: str = "elevenlabs",
) -> StateGraph:
    video_engine = VideoEngine()
    voice_gen = VoiceGenerator(provider=voice_provider)
    sheets = SheetsSync(sheet_id) if sheet_id else None

    def research_node(state: PipelineState) -> dict:
        import asyncio
        result = asyncio.run(research_agent(state, llm))
        return {"trends": result.get("trends", [])}

    def script_node(state: PipelineState) -> dict:
        script = script_agent(
            topic=state["trends"][0]["destination"] if state["trends"] else "Vietnam travel",
            trends=state["trends"],
            seeds=[],
            llm=llm,
        )
        return {"script": script}

    def caption_node(state: PipelineState) -> dict:
        captions = caption_agent(
            script=state.get("script", {}),
            video_desc="Travel video",
            llm=llm,
        )
        return {"captions": captions}

    def video_node(state: PipelineState) -> dict:
        script = state.get("script", {})
        full_text = f"{script.get('hook', '')} {script.get('body', '')} {script.get('cta', '')}"

        voice_path = voice_gen.generate_voice(
            text=full_text,
            voice_id="default",
            output_name=f"video_{hash(full_text) % 10000}",
        )

        video_path = video_engine.assemble_video(
            clips=[{"path": "", "duration": 5}],
            voiceover_path=voice_path,
            subtitle_path=None,
            output_name=f"output_{hash(full_text) % 10000}",
        )

        if sheets:
            sheets.add_video([
                f"video_{hash(full_text) % 10000}",
                "AI Generated",
                state.get("status", "pending"),
                video_path,
            ])

        return {"video_path": video_path}

    def image_node(state: PipelineState) -> dict:
        top_trend = state["trends"][0] if state["trends"] else {"destination": "Vietnam"}
        images = image_agent(
            destination=top_trend["destination"],
            template_id="default",
            llm=llm,
        )
        return {"image_assets": images.get("prompts", [])}

    builder = StateGraph(PipelineState)

    builder.add_node("research", research_node)
    builder.add_node("script", script_node)
    builder.add_node("caption", caption_node)
    builder.add_node("video", video_node)
    builder.add_node("image", image_node)

    builder.add_edge(START, "research")

    # Fan out: research -> script + caption in parallel
    builder.add_edge("research", "script")
    builder.add_edge("research", "caption")

    # Continue from script
    builder.add_conditional_edges("script", _script_ready)
    builder.add_conditional_edges("video", _video_done)

    builder.add_edge("caption", END)
    builder.add_edge("image", END)

    return builder


def run_pipeline(
    trends: list = None,
    api_key: str = None,
) -> dict:
    api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
    llm = None
    if not api_key or api_key == "your-anthropic-key":
        print("[WARNING] ANTHROPIC_API_KEY is not set or using placeholder. Running in Mock/Free mode.")
    else:
        llm = ChatAnthropic(
            model="claude-sonnet-4-5-20250929",
            api_key=api_key,
        )

    graph = build_pipeline(llm)
    app = graph.compile()

    initial_state: PipelineState = {
        "trends": trends or [],
        "script": {},
        "captions": {},
        "video_path": "",
        "image_assets": [],
        "drive_links": {},
        "status": "running",
    }

    result = app.invoke(initial_state)
    return result
