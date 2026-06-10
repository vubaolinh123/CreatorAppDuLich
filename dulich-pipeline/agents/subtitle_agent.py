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


def remove_emojis_and_icons(text: str) -> str:
    """Remove emojis, icons, and non-text visual symbols from subtitles."""
    # Pattern to match standard emojis, miscellaneous symbols, dingbats, variation selectors, zero-width joiners
    pattern = re.compile(
        r'[\U00010000-\U0010FFFF\u2600-\u27BF\u2300-\u23FF\u2B50\u3030\uE000-\uF8FF\uFE00-\uFE0F\u200D]',
        flags=re.UNICODE
    )
    cleaned = pattern.sub('', text)
    # Also clean up any double spaces that resulted from emoji removal
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned



def _estimate_duration(text: str) -> float:
    """Estimate speech duration from character count."""
    cleaned = re.sub(r"\s+", " ", text.strip())
    return max(1.0, len(cleaned) / CHARS_PER_SECOND)


def _split_into_cues(text: str, start_sec: float, max_chars: int = 35, max_lines: int = 3) -> list[dict]:
    """
    Split a long text block into subtitle cue blocks, grouped by natural semantic clauses.
    Each cue has at most max_lines * max_chars chars, and respects punctuation marks.
    Returns list of { start, end, text }.
    """
    # 1. Split into natural clauses by punctuation
    parts = re.split(r'([.,!?;|—\n]+)', text.strip())
    clauses = []
    current_clause = ""
    for part in parts:
        if not part:
            continue
        if re.match(r'^[.,!?;|—\n\s]+$', part):
            current_clause += part
        else:
            if current_clause.strip():
                clauses.append(current_clause.strip())
            current_clause = part
    if current_clause.strip():
        clauses.append(current_clause.strip())

    if not clauses:
        clauses = [text.strip()]

    # 2. For each clause, wrap to max_chars and group into cues of max_lines
    cue_texts = []
    for clause in clauses:
        # Wrap this clause
        lines = textwrap.wrap(clause, width=max_chars)
        # Group into cues of max_lines (typically 2 or 3)
        for i in range(0, len(lines), max_lines):
            cue_texts.append("\n".join(lines[i : i + max_lines]))

    if not cue_texts:
        cue_texts = [text.strip()]

    # 3. Create cues with estimated timings
    cues = []
    cursor = start_sec
    for cue_text in cue_texts:
        duration = _estimate_duration(cue_text)
        end = cursor + duration
        cues.append({"start": cursor, "end": end, "text": cue_text})
        cursor = end

    # Merge tiny cues (length < 6 characters after removing emojis/symbols)
    merged_cues = []
    i = 0
    while i < len(cues):
        cue = cues[i]
        clean_text = remove_emojis_and_icons(cue["text"]).strip()
        
        # If too short and there is a previous cue, merge into it
        if len(clean_text) < 6 and merged_cues:
            prev_cue = merged_cues[-1]
            prev_cue["text"] += " " + cue["text"]
            prev_cue["end"] = max(prev_cue["end"], cue["end"])
            i += 1
            continue
            
        # If too short and no previous but has a next cue, merge into it
        if len(clean_text) < 6 and i < len(cues) - 1:
            next_cue = cues[i + 1]
            next_cue["text"] = cue["text"] + " " + next_cue["text"]
            next_cue["start"] = min(cue["start"], next_cue["start"])
            i += 1
            continue
            
        merged_cues.append(cue)
        i += 1

    return merged_cues


def clean_word(w: str) -> str:
    """Loại bỏ tất cả các ký tự không phải chữ hoặc số (bao gồm cả Unicode tiếng Việt)."""
    return "".join(re.findall(r"[\w\d]+", w.lower(), re.UNICODE))


def align_words_with_punctuation(words: list[dict], full_speech_text: str) -> list[dict]:
    """
    Căn chỉnh danh sách từ của TTS (không có dấu câu) với text gốc của kịch bản (có đầy đủ dấu câu/emoji).
    Đồng thời gom các emoji/ký hiệu không nói vào từ trước hoặc từ sau một cách thông minh.
    """
    tokens = full_speech_text.split()
    aligned_words = []
    
    i = 0  # index in tokens
    j = 0  # index in words (TTS)
    
    last_valid_timing = {"start": 0.0, "end": 0.0}
    pending_prefix = []
    
    while i < len(tokens):
        tok = tokens[i]
        clean_tok = clean_word(tok)
        
        # 1. Nếu token gốc rỗng sau khi clean (ví dụ: emoji 😱, kí hiệu —, hoặc dấu câu rời rạc)
        if clean_tok == "" and (j >= len(words) or tok != words[j]["word"]):
            if aligned_words:
                # Ghép vào từ phía trước
                aligned_words[-1]["word"] += " " + tok
            else:
                # Nếu chưa có từ nào trước đó, lưu vào pending_prefix để ghép vào từ đầu tiên
                pending_prefix.append(tok)
            i += 1
            continue
            
        # 2. Nếu đã hết danh sách từ của TTS, gán toàn bộ token còn lại vào timing cuối cùng
        if j >= len(words):
            aligned_words.append({
                "start": last_valid_timing["start"],
                "end": last_valid_timing["end"],
                "word": tok
            })
            i += 1
            continue
            
        tw = words[j]["word"]
        clean_tw = clean_word(tw)
        
        is_match = False
        matched_i = i
        matched_j = j
        
        # 3. So sánh trực tiếp
        if (clean_tok == clean_tw and clean_tok != "") or (tok == tw):
            is_match = True
        else:
            # 4. Tìm kiếm lookahead (tối đa 15 từ) để tự đồng bộ lại khi lệch index
            found = False
            best_sum = 999
            
            for offset_i in range(15):
                for offset_j in range(15):
                    if offset_i == 0 and offset_j == 0:
                        continue
                    ti = i + offset_i
                    wj = j + offset_j
                    if ti < len(tokens) and wj < len(words):
                        t_tok = tokens[ti]
                        w_word = words[wj]["word"]
                        c_t_tok = clean_word(t_tok)
                        c_w_word = clean_word(w_word)
                        if (c_t_tok == c_w_word and c_t_tok != "") or (t_tok == w_word):
                            if offset_i + offset_j < best_sum:
                                best_sum = offset_i + offset_j
                                matched_i = ti
                                matched_j = wj
                                found = True
                                
            if found:
                is_match = True
                # Gán timing của word hiện tại (words[j]) cho toàn bộ token bị bỏ qua trong kịch bản
                for skip_i in range(i, matched_i):
                    aligned_words.append({
                        "start": words[j]["start"],
                        "end": words[j]["end"],
                        "word": tokens[skip_i]
                    })
                i = matched_i
                j = matched_j
                tw = words[j]["word"]
                clean_tw = clean_word(tw)
                tok = tokens[i]
                clean_tok = clean_word(tok)
                
        if is_match:
            timing = {
                "start": words[j]["start"],
                "end": words[j]["end"],
            }
            # Ghép các prefix pending từ trước đó vào
            word_str = tok
            if pending_prefix:
                word_str = " ".join(pending_prefix + [tok])
                pending_prefix = []
                
            aligned_words.append({
                "start": timing["start"],
                "end": timing["end"],
                "word": word_str
            })
            last_valid_timing = timing
            i += 1
            j += 1
        else:
            # Fallback nếu hoàn toàn không khớp được: ghép cặp cưỡng bức
            timing = {
                "start": words[j]["start"],
                "end": words[j]["end"],
            }
            word_str = tok
            if pending_prefix:
                word_str = " ".join(pending_prefix + [tok])
                pending_prefix = []
                
            aligned_words.append({
                "start": timing["start"],
                "end": timing["end"],
                "word": word_str
            })
            last_valid_timing = timing
            i += 1
            j += 1
            
    return aligned_words


def group_words_into_cues(words: list[dict], min_words: int = 4, max_words: int = 12) -> list[dict]:
    """
    Gom nhóm danh sách từ (words với timing) thành các cue phụ đề.
    Hợp nhất các câu/cụm từ theo dấu câu, nhịp nghỉ (pause) tự nhiên của giọng nói,
    và giới hạn ký tự tối thiểu để tránh hiển thị cue quá ngắn (< 6 ký tự).
    """
    cues = []
    if not words:
        return cues
        
    current_words = []
    
    for i, word_info in enumerate(words):
        current_words.append(word_info)
        text = word_info["word"].strip()
        
        # Nhận diện dấu câu
        has_strong_punctuation = bool(re.search(r"[.!?:;][^\w]*$", text))
        has_comma = bool(re.search(r",[^\w]*$", text))
        
        # Nhận diện nhịp nghỉ (pause) giữa từ hiện tại và từ tiếp theo
        has_pause = False
        if i < len(words) - 1:
            next_word = words[i + 1]
            pause_dur = next_word["start"] - word_info["end"]
            if pause_dur > 0.35: # khoảng lặng hơn 350ms
                has_pause = True

        should_split = False
        if len(current_words) >= max_words:
            # Vượt quá giới hạn từ của 1 cue
            should_split = True
        elif has_strong_punctuation:
            # Gặp dấu ngắt câu mạnh
            should_split = True
        elif has_pause and len(current_words) >= min_words:
            # Gặp khoảng lặng và đã đủ số từ tối thiểu
            should_split = True
        elif has_comma and len(current_words) >= min_words:
            # Gặp dấu phẩy và đã đủ số từ tối thiểu
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

    # Pass 2: Merge bất kỳ cue nào có độ dài chữ (sau khi lọc emoji) < 6 ký tự
    merged_cues = []
    i = 0
    while i < len(cues):
        cue = cues[i]
        clean_text = remove_emojis_and_icons(cue["text"]).strip()
        
        # Nếu cue quá ngắn và đã có cue trước đó, gộp vào cue trước
        if len(clean_text) < 6 and merged_cues:
            prev_cue = merged_cues[-1]
            prev_cue["text"] += " " + cue["text"]
            prev_cue["end"] = max(prev_cue["end"], cue["end"])
            i += 1
            continue
            
        # Nếu cue quá ngắn và chưa có cue trước đó nhưng có cue tiếp theo
        # Gộp tạm vào cue tiếp theo bằng cách sửa đổi cue tiếp theo
        if len(clean_text) < 6 and i < len(cues) - 1:
            next_cue = cues[i + 1]
            next_cue["text"] = cue["text"] + " " + next_cue["text"]
            next_cue["start"] = min(cue["start"], next_cue["start"])
            i += 1
            continue
            
        # Nếu không gộp được (ví dụ chỉ có 1 cue duy nhất), giữ nguyên
        merged_cues.append(cue)
        i += 1

    return merged_cues


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

    # Dynamic subtitle segment wrapping based on video duration
    # We allow up to 3 lines to support grouping words into cohesive sentences/phrases
    # when requested, and adjust the wrapping width based on duration.
    max_chars = 36
    max_lines = 3
    if voice_duration_sec and voice_duration_sec > 0:
        if voice_duration_sec <= 20.0:
            max_chars = 32   # Comfortable width for short videos
        elif voice_duration_sec <= 40.0:
            max_chars = 34
        print(f"[Subtitle] Dynamic wrapping selected based on duration ({voice_duration_sec:.1f}s): max_chars={max_chars}, max_lines={max_lines}")

    if words_json_path:
        import json
        try:
            with open(words_json_path, "r", encoding="utf-8") as f:
                words = json.load(f)
            print(f"[Subtitle] Tìm thấy timing chi tiết từ file: {words_json_path}. Căn chỉnh với kịch bản gốc...")
            
            # Căn chỉnh từ nói với kịch bản gốc để khôi phục đầy đủ dấu câu, hoa thường và emoji
            hook_text = script.get("hook", "").strip()
            body_text = script.get("body", "").strip()
            cta_text = script.get("cta", "").strip()
            parts = [p for p in [hook_text, body_text, cta_text] if p]
            full_speech_text = ". ".join(parts)
            
            aligned_words = align_words_with_punctuation(words, full_speech_text)
            all_cues = group_words_into_cues(aligned_words, min_words=4, max_words=12)
            
            # Calculate the actual hook end time from word timings
            hook_words_count = len(hook_text.split())
            if aligned_words and hook_words_count > 0:
                hook_word_index = min(hook_words_count - 1, len(aligned_words) - 1)
                actual_hook_end = aligned_words[hook_word_index]["end"]
                print(f"[Subtitle] Tìm thấy timing thực tế của hook trong audio: 0s -> {actual_hook_end:.2f}s")
                hook_end = actual_hook_end
        except Exception as e:
            print(f"[Subtitle] Lỗi parse/căn chỉnh file timing: {e}. Fallback sang thuật toán ước lượng.")
            words_json_path = None

    # Fallback to character-based estimation if timing file is not available
    if not words_json_path:
        hook_text = script.get("hook", "").strip()
        body_text = script.get("body", "").strip()
        cta_text = script.get("cta", "").strip()

        # --- Hook (0 → hook_end) ---
        if hook_text:
            hook_cues = _split_into_cues(hook_text, start_sec=0.0, max_chars=max_chars, max_lines=max_lines)
            natural_duration = sum(c["end"] - c["start"] for c in hook_cues)
            if natural_duration > 0 and hook_end > 0:
                scale = hook_end / natural_duration
                for cue in hook_cues:
                    length = cue["end"] - cue["start"]
                    cue["start"] = cue["start"] * scale
                    cue["end"] = cue["start"] + length * scale
            all_cues.extend(hook_cues)

        # --- Body (hook_end → body_end) ---
        if body_text:
            body_cues = _split_into_cues(body_text, start_sec=hook_end, max_chars=max_chars, max_lines=max_lines)
            # Scale cues to fit within body_end
            body_duration = body_end - hook_end
            natural_duration = sum(c["end"] - c["start"] for c in body_cues)
            if natural_duration > 0 and body_duration > 0:
                scale = body_duration / natural_duration
                for cue in body_cues:
                    length = cue["end"] - cue["start"]
                    cue["start"] = hook_end + (cue["start"] - hook_end) * scale
                    cue["end"] = cue["start"] + length * scale
            all_cues.extend(body_cues)

        # --- CTA (body_end → cta_end) ---
        if cta_text:
            cta_cues = _split_into_cues(cta_text, start_sec=body_end, max_chars=max_chars, max_lines=max_lines)
            cta_duration = cta_end - body_end
            natural_duration = sum(c["end"] - c["start"] for c in cta_cues)
            if natural_duration > 0 and cta_duration > 0:
                scale = cta_duration / natural_duration
                for cue in cta_cues:
                    length = cue["end"] - cue["start"]
                    cue["start"] = body_end + (cue["start"] - body_end) * scale
                    cue["end"] = cue["start"] + length * scale
            all_cues.extend(cta_cues)

        # Scale all timestamps if actual voice duration is provided
        if voice_duration_sec and voice_duration_sec > 0:
            script_end = cta_end
            scale = voice_duration_sec / script_end
            for cue in all_cues:
                cue["start"] *= scale
                cue["end"] *= scale

    # Filter out cues that are part of the hook phase (starts before hook_end)
    # We use a tolerance of 0.05 seconds to handle floating point precision
    initial_cue_count = len(all_cues)
    all_cues = [cue for cue in all_cues if cue["start"] >= hook_end - 0.05]
    print(f"[Subtitle] Lọc bỏ phụ đề trong khoảng thời gian hook (0 -> {hook_end:.2f}s). Đã xóa {initial_cue_count - len(all_cues)} cues hook.")

    # --- Write .srt ---
    srt_lines = []
    for i, cue in enumerate(all_cues, start=1):
        srt_lines.append(str(i))
        srt_lines.append(
            f"{_srt_timestamp(cue['start'])} --> {_srt_timestamp(cue['end'])}"
        )
        srt_lines.append(remove_emojis_and_icons(cue["text"]))
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
