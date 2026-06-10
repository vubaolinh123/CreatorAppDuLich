"""Tests for subtitle alignment and cue grouping logic in subtitle_agent.py."""

import json
import pytest
from pathlib import Path
from agents.subtitle_agent import (
    clean_word,
    align_words_with_punctuation,
    group_words_into_cues,
    generate_srt,
)

def test_clean_word():
    assert clean_word("chưa?") == "chưa"
    assert clean_word("đây!.") == "đây"
    assert clean_word("😱") == ""
    assert clean_word("—") == ""
    assert clean_word("ngày 2") == "ngày2"
    assert clean_word("Lan Anh") == "lananh"


def test_align_words_with_punctuation_simple():
    words = [
        {"start": 0.1, "end": 0.5, "word": "Bạn"},
        {"start": 0.5, "end": 0.8, "word": "đã"},
        {"start": 0.8, "end": 1.2, "word": "biết"},
    ]
    full_speech = "Bạn đã biết?"
    aligned = align_words_with_punctuation(words, full_speech)
    
    assert len(aligned) == 3
    assert aligned[0]["word"] == "Bạn"
    assert aligned[1]["word"] == "đã"
    assert aligned[2]["word"] == "biết?"
    assert aligned[2]["start"] == 0.8
    assert aligned[2]["end"] == 1.2


def test_align_words_with_punctuation_emoji_and_symbols():
    words = [
        {"start": 0.1, "end": 0.4, "word": "chưa"},
        {"start": 0.4, "end": 0.8, "word": "Mình"},
        {"start": 0.8, "end": 1.2, "word": "đến"},
        {"start": 1.2, "end": 1.5, "word": "đây"},
    ]
    # "😱" at start, "—" in middle, "😱" after punctuation
    full_speech = "😱 chưa? — Mình đến đây! 😱"
    aligned = align_words_with_punctuation(words, full_speech)
    
    # Let's check:
    # 😱 at start gets prepended to "chưa?": "😱 chưa?"
    # — in middle gets appended to "chưa?": "😱 chưa? —"
    # 😱 after "đây!" gets appended to "đây!": "đây! 😱"
    assert len(aligned) == 4
    assert aligned[0]["word"] == "😱 chưa? —"
    assert aligned[0]["start"] == 0.1
    assert aligned[0]["end"] == 0.4
    
    assert aligned[1]["word"] == "Mình"
    assert aligned[1]["start"] == 0.4
    
    assert aligned[3]["word"] == "đây! 😱"
    assert aligned[3]["start"] == 1.2
    assert aligned[3]["end"] == 1.5


def test_align_words_with_punctuation_lookahead_skipped_in_tts():
    # script: "một hai ba"
    # TTS: "một ba" (skipped "hai")
    words = [
        {"start": 0.1, "end": 0.5, "word": "một"},
        {"start": 0.5, "end": 1.0, "word": "ba"},
    ]
    full_speech = "một hai ba"
    aligned = align_words_with_punctuation(words, full_speech)
    
    assert len(aligned) == 3
    assert aligned[0]["word"] == "một"
    assert aligned[0]["start"] == 0.1
    assert aligned[0]["end"] == 0.5
    
    assert aligned[1]["word"] == "hai"
    assert aligned[1]["start"] == 0.5  # gets timing of "ba"
    assert aligned[1]["end"] == 1.0
    
    assert aligned[2]["word"] == "ba"
    assert aligned[2]["start"] == 0.5
    assert aligned[2]["end"] == 1.0


def test_align_words_with_punctuation_lookahead_extra_in_tts():
    # script: "một ba"
    # TTS: "một hai ba" (extra "hai")
    words = [
        {"start": 0.1, "end": 0.4, "word": "một"},
        {"start": 0.4, "end": 0.8, "word": "hai"},
        {"start": 0.8, "end": 1.2, "word": "ba"},
    ]
    full_speech = "một ba"
    aligned = align_words_with_punctuation(words, full_speech)
    
    assert len(aligned) == 2
    assert aligned[0]["word"] == "một"
    assert aligned[0]["start"] == 0.1
    assert aligned[0]["end"] == 0.4
    
    assert aligned[1]["word"] == "ba"
    assert aligned[1]["start"] == 0.8
    assert aligned[1]["end"] == 1.2


def test_align_words_with_punctuation_number_grouping():
    # script: "ở 3 ngày 2 đêm"
    # TTS: "ở", "3", "ngày 2", "đêm"
    words = [
        {"start": 0.1, "end": 0.3, "word": "ở"},
        {"start": 0.3, "end": 0.6, "word": "3"},
        {"start": 0.6, "end": 1.0, "word": "ngày 2"},
        {"start": 1.0, "end": 1.4, "word": "đêm"},
    ]
    full_speech = "ở 3 ngày 2 đêm"
    aligned = align_words_with_punctuation(words, full_speech)
    
    assert len(aligned) == 5
    assert aligned[0]["word"] == "ở"
    assert aligned[1]["word"] == "3"
    assert aligned[2]["word"] == "ngày"
    assert aligned[2]["start"] == 0.6
    assert aligned[2]["end"] == 1.0
    
    assert aligned[3]["word"] == "2"
    assert aligned[3]["start"] == 0.6
    assert aligned[3]["end"] == 1.0
    
    assert aligned[4]["word"] == "đêm"
    assert aligned[4]["start"] == 1.0
    assert aligned[4]["end"] == 1.4


def test_group_words_into_cues_punctuation_split():
    # Test that cues are split on strong punctuation, even with emojis/spaces after
    words = [
        {"start": 0.1, "end": 0.4, "word": "Bạn"},
        {"start": 0.4, "end": 0.8, "word": "đã"},
        {"start": 0.8, "end": 1.2, "word": "biết?"},
        {"start": 1.2, "end": 1.6, "word": "😱"},
        {"start": 1.6, "end": 2.0, "word": "Mình"},
        {"start": 2.0, "end": 2.4, "word": "shock"},
        {"start": 2.4, "end": 2.8, "word": "thật"},
        {"start": 2.8, "end": 3.2, "word": "sự"},
        {"start": 3.2, "end": 3.6, "word": "khi"},
        {"start": 3.6, "end": 4.0, "word": "đến"},
        {"start": 4.0, "end": 4.4, "word": "đây! 😱"},
        {"start": 4.4, "end": 4.8, "word": "Hôm"},
        {"start": 4.8, "end": 5.2, "word": "nay"},
    ]
    cues = group_words_into_cues(words, min_words=3, max_words=5)
    
    # Let's inspect the grouped cues:
    # 1. "Bạn đã biết?" - has strong punctuation "?", and length is 3 (>=3).
    # Wait, the next is "😱" which has clean_tok == "".
    # Wait, if we aligned them first, the emoji "😱" is merged into "biết? 😱".
    # But even if they are separate (like in this raw list):
    # "Bạn đã biết?" splits because of has_strong_punctuation=True.
    # Cue 1 text: "Bạn đã biết?"
    # Then "😱", "Mình", "shock", "thật", "sự" (5 words). Splits because of max_words=5.
    # Cue 2 text: "😱 Mình shock thật sự"
    # Then "khi", "đến", "đây! 😱". splits because "đây! 😱" has strong punctuation (regex matches).
    # Cue 3 text: "khi đến đây! 😱"
    # Then "Hôm", "nay".
    # Cue 4 text: "Hôm nay"
    
    assert len(cues) >= 3
    assert cues[0]["text"] == "Bạn đã biết?"
    
    # Check that "đây! 😱" triggers split:
    # Find the cue containing "đây! 😱"
    cue_day = [c for c in cues if "đây! 😱" in c["text"]]
    assert len(cue_day) == 1
    assert cue_day[0]["text"] == "khi đến đây! 😱"
    
    # And check that "Hôm nay" starts a new cue and is not grouped with "đây! 😱"
    cue_hom = [c for c in cues if "Hôm" in c["text"]]
    assert len(cue_hom) == 1
    assert "đây" not in cue_hom[0]["text"]
    assert cue_hom[0]["text"] == "Hôm nay"


def test_group_words_into_cues_comma_split():
    # Test that commas split cues if we have at least min_words
    words = [
        {"start": 0.1, "end": 0.4, "word": "Thức"},
        {"start": 0.4, "end": 0.8, "word": "ăn"},
        {"start": 0.8, "end": 1.2, "word": "ngon,"},
        {"start": 1.2, "end": 1.6, "word": "người"},
        {"start": 1.6, "end": 2.0, "word": "dân"},
        {"start": 2.0, "end": 2.4, "word": "thân"},
        {"start": 2.4, "end": 2.8, "word": "thiện"},
    ]
    cues = group_words_into_cues(words, min_words=3, max_words=5)
    
    # Cue 1: "Thức ăn ngon," (split at comma because length=3 >= min_words=3)
    # Cue 2: "người dân thân thiện"
    assert len(cues) == 2
    assert cues[0]["text"] == "Thức ăn ngon,"
    assert cues[1]["text"] == "người dân thân thiện"


def test_convert_srt_to_ass(tmp_path):
    from tools.video_renderer import VideoEngine
    
    srt_file = tmp_path / "test.srt"
    ass_file = tmp_path / "test.ass"
    
    srt_content = (
        "1\n"
        "00:00:01,230 --> 00:00:05,670\n"
        "Chào bạn đến với\nĐà Lạt!\n\n"
        "2\n"
        "00:00:06,000 --> 00:00:10,050\n"
        "Phong cảnh tuyệt đẹp\n"
    )
    srt_file.write_text(srt_content, encoding="utf-8")
    
    engine = VideoEngine()
    success = engine._convert_srt_to_ass(str(srt_file), str(ass_file), is_personal=True)
    
    assert success
    assert ass_file.exists()
    
    ass_content = ass_file.read_text(encoding="utf-8")
    assert "PlayResX: 1080" in ass_content
    assert "PlayResY: 1920" in ass_content
    assert "Dialogue: 0,0:00:01.23,0:00:05.67,Default,,0,0,0,,Chào bạn đến với\\NĐà Lạt!" in ass_content
    assert "Dialogue: 0,0:00:06.00,0:00:10.05,Default,,0,0,0,,Phong cảnh tuyệt đẹp" in ass_content
