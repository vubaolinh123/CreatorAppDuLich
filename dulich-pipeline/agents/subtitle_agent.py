"""
Subtitle Agent — Generates .srt subtitle file from a script dict.

Input:
    script: { "hook": str, "body": str, "cta": str }
    voice_duration_sec: total audio duration in seconds (optional, estimated if not given)

Output:
    srt_path: path to generated .srt file

SRT format:
    1
    00:00:00,000 --> 00:00:05,000
    Hook text here

    2
    00:00:05,000 --> 00:00:40,000
    Body text here...

    3
    00:00:40,000 --> 00:01:00,000
    CTA text here
"""

from __future__ import annotations

import re
import textwrap
from pathlib import Path
from typing import Optional


OUTPUT_DIR = Path("./output/subtitles")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Vietnamese reading speed: ~120-140 words/min → ~2 words/sec
CHARS_PER_SECOND = 12          # rough estimate for Vietnamese
MAX_CHARS_PER_LINE = 42        # max chars per subtitle line
MAX_LINES_PER_CUE = 2          # max lines per cue block


def _srt_timestamp(seconds: float) -> str:
    """Convert float seconds to SRT timestamp format HH:MM:SS,mmm."""
    ms = int((seconds % 1) * 1000)
    total_int = int(seconds)
    s = total_int % 60
    m = (total_int // 60) % 60
    h = total_int // 3600
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _estimate_duration(text: str) -> float:
    """Estimate speech duration from character count."""
    cleaned = re.sub(r"\s+", " ", text.strip())
    return max(1.0, len(cleaned) / CHARS_PER_SECOND)


def _split_into_cues(text: str, start_sec: float) -> list[dict]:
    """
    Split a long text block into subtitle cue blocks.
    Each cue has at most MAX_LINES_PER_CUE * MAX_CHARS_PER_LINE chars.
    Returns list of { start, end, text }.
    """
    # Wrap text to MAX_CHARS_PER_LINE per line
    lines = textwrap.wrap(text.strip(), width=MAX_CHARS_PER_LINE)

    # Group lines into cues of MAX_LINES_PER_CUE
    cue_texts = []
    for i in range(0, len(lines), MAX_LINES_PER_CUE):
        cue_texts.append("\n".join(lines[i : i + MAX_LINES_PER_CUE]))

    if not cue_texts:
        cue_texts = [text.strip()]

    cues = []
    cursor = start_sec
    for cue_text in cue_texts:
        duration = _estimate_duration(cue_text)
        end = cursor + duration
        cues.append({"start": cursor, "end": end, "text": cue_text})
        cursor = end

    return cues


def group_words_into_cues(words: list[dict], min_words: int = 3, max_words: int = 5) -> list[dict]:
    """
    Gom nhóm danh sách từ (words với timing) thành các cue phụ đề.
    Mỗi cue chứa từ 3-5 từ, ngắt nghỉ hợp lý dựa trên dấu câu tiếng Việt.
    """
    cues = []
    current_words = []
    
    for word_info in words:
        current_words.append(word_info)
        text = word_info["word"].strip()
        
        # Ngắt theo dấu câu mạnh (. ? !) hoặc dấu phẩy (nếu đã gom đủ min_words)
        has_strong_punctuation = any(text.endswith(p) for p in ('.', '!', '?', ':', ';'))
        has_comma = text.endswith(',')
        
        should_split = False
        if len(current_words) >= max_words:
            should_split = True
        elif has_strong_punctuation:
            should_split = True
        elif has_comma and len(current_words) >= min_words:
            should_split = True
            
        if should_split and current_words:
            cue_text = " ".join([w["word"] for w in current_words])
            start_time = current_words[0]["start"]
            end_time = current_words[-1]["end"]
            cues.append({
                "start": start_time,
                "end": end_time,
                "text": cue_text
            })
            current_words = []
            
    if current_words:
        cue_text = " ".join([w["word"] for w in current_words])
        start_time = current_words[0]["start"]
        end_time = current_words[-1]["end"]
        cues.append({
            "start": start_time,
            "end": end_time,
            "text": cue_text
        })
        
    return cues


def generate_srt(
    script: dict,
    output_name: str = "subtitles",
    voice_duration_sec: Optional[float] = None,
    hook_end: float = 5.0,
    body_end: float = 40.0,
    cta_end: float = 60.0,
    audio_path: Optional[str] = None,
) -> str:
    """
    Build a .srt file from a script dict.

    Args:
        script: { "hook": str, "body": str, "cta": str }
        output_name: base filename (no extension)
        voice_duration_sec: total audio duration; used to scale timestamps if given
        hook_end: expected end time (sec) for hook segment
        body_end: expected end time (sec) for body segment
        cta_end: expected end time (sec) for cta segment
        audio_path: path to the voice audio file (checks for .words.json timings)

    Returns:
        Absolute path to the .srt file.
    """
    words_json_path = None
    if audio_path:
        p = Path(audio_path).with_suffix(".words.json")
        if p.exists():
            words_json_path = p

    all_cues: list[dict] = []

    if words_json_path:
        import json
        try:
            with open(words_json_path, "r", encoding="utf-8") as f:
                words = json.load(f)
            print(f"[Subtitle] Tìm thấy timing chi tiết từ file: {words_json_path}. Tạo phụ đề chính xác...")
            all_cues = group_words_into_cues(words, min_words=3, max_words=5)
        except Exception as e:
            print(f"[Subtitle] Lỗi parse file timing: {e}. Fallback sang thuật toán ước lượng.")
            words_json_path = None

    # Fallback to character-based estimation if timing file is not available
    if not words_json_path:
        hook_text = script.get("hook", "").strip()
        body_text = script.get("body", "").strip()
        cta_text = script.get("cta", "").strip()

        # --- Hook (0 → hook_end) ---
        if hook_text:
            all_cues.extend(_split_into_cues(hook_text, start_sec=0.0))
            # Clamp last hook cue end to hook_end
            if all_cues:
                all_cues[-1]["end"] = hook_end

        # --- Body (hook_end → body_end) ---
        if body_text:
            body_cues = _split_into_cues(body_text, start_sec=hook_end)
            # Scale cues to fit within body_end
            body_duration = body_end - hook_end
            natural_duration = sum(c["end"] - c["start"] for c in body_cues)
            if natural_duration > 0:
                scale = body_duration / natural_duration
                for cue in body_cues:
                    length = cue["end"] - cue["start"]
                    cue["start"] = hook_end + (cue["start"] - hook_end) * scale
                    cue["end"] = cue["start"] + length * scale
            all_cues.extend(body_cues)

        # --- CTA (body_end → cta_end) ---
        if cta_text:
            cta_cues = _split_into_cues(cta_text, start_sec=body_end)
            all_cues.extend(cta_cues)
            if all_cues:
                all_cues[-1]["end"] = cta_end

        # Scale all timestamps if actual voice duration is provided
        if voice_duration_sec and voice_duration_sec > 0:
            script_end = cta_end
            scale = voice_duration_sec / script_end
            for cue in all_cues:
                cue["start"] *= scale
                cue["end"] *= scale

    # --- Write .srt ---
    srt_lines = []
    for i, cue in enumerate(all_cues, start=1):
        srt_lines.append(str(i))
        srt_lines.append(
            f"{_srt_timestamp(cue['start'])} --> {_srt_timestamp(cue['end'])}"
        )
        srt_lines.append(cue["text"])
        srt_lines.append("")  # blank line between cues

    srt_content = "\n".join(srt_lines)
    output_path = OUTPUT_DIR / f"{output_name}.srt"
    output_path.write_text(srt_content, encoding="utf-8")
    print(f"[Subtitle] ✓ SRT saved ({len(all_cues)} cues): {output_path}")
    return str(output_path)


def subtitle_agent(
    script: dict,
    output_name: str = "subtitles",
    voice_duration_sec: Optional[float] = None,
) -> dict:
    """
    LangGraph-compatible node function.
    Returns { "subtitle_path": str }.
    """
    srt_path = generate_srt(
        script=script,
        output_name=output_name,
        voice_duration_sec=voice_duration_sec,
    )
    return {"subtitle_path": srt_path}
