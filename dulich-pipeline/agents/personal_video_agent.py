"""
Personal Video Agent — Controls the pipeline for individual creators.
Applies specific voice clones, hook templates, and custom script text.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from tools.db import jobs_col, creators_col, content_col, update_job, append_job_log, save_content, new_doc
from tools.voice_generator import VoiceGenerator
from agents.subtitle_agent import generate_srt
from tools.video_renderer import VideoEngine

# Default creators data to seed database
DEFAULT_CREATORS = [
    {
        "_id": "lan_anh",
        "name": "Lan Anh",
        "voice_provider": "vbee",
        "voice_id": "hn_female_lananh",
        "hook_preference": "zoom_in",
        "created_at": "2026-06-09T00:00:00Z",
        "updated_at": "2026-06-09T00:00:00Z",
    },
    {
        "_id": "minh_tuan",
        "name": "Minh Tuấn",
        "voice_provider": "vbee",
        "voice_id": "hn_male_minhtuan",
        "hook_preference": "glitch",
        "created_at": "2026-06-09T00:00:00Z",
        "updated_at": "2026-06-09T00:00:00Z",
    },
    {
        "_id": "thu_ha",
        "name": "Thu Hà",
        "voice_provider": "vbee",
        "voice_id": "hn_female_thutrang",
        "hook_preference": "cinematic_vignette",
        "created_at": "2026-06-09T00:00:00Z",
        "updated_at": "2026-06-09T00:00:00Z",
    },
    {
        "_id": "duc_anh",
        "name": "Đức Anh",
        "voice_provider": "vbee",
        "voice_id": "hcm_male_ducanh",
        "hook_preference": "zoom_out",
        "created_at": "2026-06-09T00:00:00Z",
        "updated_at": "2026-06-09T00:00:00Z",
    },
    {
        "_id": "ngoc_mai",
        "name": "Ngọc Mai",
        "voice_provider": "vbee",
        "voice_id": "hn_female_ngocmai",
        "hook_preference": "zoom_in",
        "created_at": "2026-06-09T00:00:00Z",
        "updated_at": "2026-06-09T00:00:00Z",
    }
]


def ensure_creators_seeded() -> None:
    """Ensure that the 5 default creators are present in MongoDB."""
    import sys
    try:
        col = creators_col()
        # Count documents, if empty or less than 5, insert them
        existing_count = col.count_documents({}) if hasattr(col, "count_documents") else len(list(col.find({})))
        if existing_count < 5:
            print(f"[PersonalPipeline] Seeding {5 - existing_count} default creators into database.", file=sys.stderr)
            for c in DEFAULT_CREATORS:
                # Check if exists by _id
                if not col.find_one({"_id": c["_id"]}):
                    col.insert_one(c)
    except Exception as e:
        print(f"[PersonalPipeline] Warning during seeding creators: {e}", file=sys.stderr)


def run_personal_pipeline(
    job_id: str,
    creator_id: str,
    script_text: str,  # Raw text or JSON string
    media_paths: list[str],
    hook_style: str = "",
    hook_text: str = "",
    provider_override: str = "",
) -> dict:
    """
    Run the Personal Creator Pipeline.
    
    1. Parse script (supports raw paragraph or JSON {hook, body, cta})
    2. Retrieve creator profile (for voice config)
    3. Generate voiceover (voice clone)
    4. Generate SRT subtitles
    5. Assemble video with hook effect presets and burn subs
    6. Save final video artifact
    """
    ensure_creators_seeded()
    
    append_job_log(job_id, "INFO", f"Khởi động Personal Pipeline cho Creator: {creator_id}")
    
    # 1. Parse or Generate Script
    import json
    script = {"hook": "", "body": "", "cta": ""}
    
    is_just_topic = len(script_text.strip()) < 60 and "\n" not in script_text
    
    if is_just_topic:
        append_job_log(job_id, "INFO", f"Nhận diện đầu vào là chủ đề. Đang tự động viết kịch bản cho chủ đề: '{script_text}'...")
        
        # Query seeding from MongoDB
        from tools.db import get_seeding_items
        location_keyword = ""
        # Basic check for vietnamese destinations
        for word in ["Đà Nẵng", "Hội An", "Phú Quốc", "Nha Trang", "Đà Lạt", "Sapa", "Hà Nội", "Hồ Chí Minh", "Huế", "Ninh Bình"]:
            if word.lower() in script_text.lower():
                location_keyword = word
                break
                
        seeds = get_seeding_items(location=location_keyword, limit=2)
        if seeds:
            seed_names = ", ".join([s.get("name", "") for s in seeds])
            append_job_log(job_id, "INFO", f"Tìm thấy địa điểm seeding phù hợp trong DB: {seed_names}")
        else:
            append_job_log(job_id, "INFO", "Không tìm thấy địa điểm seeding nào phù hợp trong DB.")
            
        # Call script agent or mock
        from config import config
        if config.anthropic_api_key and config.anthropic_api_key != "your-anthropic-key":
            from agents.script_agent import script_agent
            from langchain_anthropic import ChatAnthropic
            llm = ChatAnthropic(model="claude-3-5-sonnet-20240620", api_key=config.anthropic_api_key)
            try:
                script = script_agent(topic=script_text, trends=[], seeds=seeds, llm=llm)
            except Exception as e:
                append_job_log(job_id, "WARNING", f"Lỗi gọi LLM: {e}. Fallback sang mock script.")
                script = _generate_mock_script_with_seeds(script_text, seeds)
        else:
            script = _generate_mock_script_with_seeds(script_text, seeds)
    else:
        # Full script provided
        if script_text.strip().startswith("{") and script_text.strip().endswith("}"):
            try:
                script = json.loads(script_text)
            except Exception:
                script["body"] = script_text
        else:
            lines = [line.strip() for line in script_text.split("\n") if line.strip()]
            if len(lines) >= 3:
                script["hook"] = lines[0]
                script["body"] = " ".join(lines[1:-1])
                script["cta"] = lines[-1]
            elif len(lines) == 2:
                script["hook"] = lines[0]
                script["body"] = lines[1]
                script["cta"] = "Hãy theo dõi mình để biết thêm nhé!"
            elif len(lines) == 1:
                script["hook"] = "Khám phá cùng mình nhé!"
                script["body"] = lines[0]
                script["cta"] = "Follow kênh mình nha!"
            else:
                script["hook"] = "Cùng đi du lịch nào!"
                script["body"] = "Trải nghiệm chuyến đi tuyệt vời ngày hôm nay."
                script["cta"] = "Nhấn follow để xem thêm video nhé!"

    append_job_log(job_id, "INFO", f"Script hoàn thiện: Hook: '{script['hook']}', Body: '{script['body'][:40]}...', CTA: '{script['cta']}'")

    # 2. Retrieve Creator Profile
    col = creators_col()
    creator = col.find_one({"_id": creator_id})
    if not creator:
        # Fallback to default config
        append_job_log(job_id, "WARNING", f"Không tìm thấy creator '{creator_id}' trong DB, dùng mặc định Lan Anh.")
        creator = DEFAULT_CREATORS[0]

    voice_provider = provider_override or creator.get("voice_provider", "vbee")
    voice_id = creator.get("voice_id", "hn_female_lananh")
    chosen_hook_style = hook_style or creator.get("hook_preference", "zoom_in")

    append_job_log(job_id, "INFO", f"Sử dụng giọng nói: {voice_id} ({voice_provider}) | Hiệu ứng Hook: {chosen_hook_style}")

    # Combine text for TTS
    full_speech_text = f"{script['hook']}. {script['body']}. {script['cta']}"

    # 3. Generate voiceover
    update_job(job_id, {"progress": 20})
    append_job_log(job_id, "INFO", "Đang tạo giọng nói AI...")
    
    voice_gen = VoiceGenerator(provider=voice_provider)
    audio_output_name = f"personal_{creator_id}_{job_id[:8]}"
    
    try:
        audio_path = voice_gen.generate_voice(
            text=full_speech_text,
            voice_id=voice_id,
            output_name=audio_output_name,
        )
        append_job_log(job_id, "INFO", f"Đã sinh file âm thanh: {audio_path}")
    except Exception as e:
        append_job_log(job_id, "ERROR", f"Lỗi sinh giọng nói: {e}")
        raise e

    # Estimate duration of audio
    import wave
    audio_duration = 10.0
    if audio_path.endswith(".wav"):
        try:
            with wave.open(audio_path, "r") as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                audio_duration = frames / float(rate)
        except Exception:
            pass
    else:
        # Estimate from text length if MP3 (approx 12 characters per second)
        audio_duration = max(5.0, len(full_speech_text) / 12.0)

    append_job_log(job_id, "INFO", f"Thời lượng âm thanh dự tính: {audio_duration:.1f} giây")

    # 4. Generate SRT subtitles
    update_job(job_id, {"progress": 40})
    append_job_log(job_id, "INFO", "Đang tạo phụ đề...")
    
    # Calculate timings based on text ratio
    hook_len = len(script["hook"])
    body_len = len(script["body"])
    cta_len = len(script["cta"])
    total_len = hook_len + body_len + cta_len
    
    hook_end = (hook_len / total_len) * audio_duration if total_len > 0 else 3.0
    body_end = ((hook_len + body_len) / total_len) * audio_duration if total_len > 0 else 8.0
    
    try:
        srt_path = generate_srt(
            script=script,
            output_name=f"sub_{audio_output_name}",
            voice_duration_sec=audio_duration,
            hook_end=hook_end,
            body_end=body_end,
            cta_end=audio_duration
        )
        append_job_log(job_id, "INFO", f"Đã sinh file phụ đề: {srt_path}")
    except Exception as e:
        append_job_log(job_id, "ERROR", f"Lỗi sinh phụ đề: {e}")
        raise e

    # 5. Assemble video
    update_job(job_id, {"progress": 60})
    append_job_log(job_id, "INFO", "Đang dựng và ghép video...")

    video_engine = VideoEngine()
    
    # Build clips structures
    clips = []
    if media_paths:
        # Divide duration equally among raw clips
        avg_dur = audio_duration / len(media_paths)
        for path in media_paths:
            clips.append({
                "path": path,
                "duration": avg_dur
            })
    else:
        # Fallback to single placeholder clip
        clips.append({
            "path": "",
            "duration": audio_duration
        })

    video_output_name = f"video_personal_{creator_id}_{job_id[:8]}"
    
    try:
        # Call video assembler with hook_style
        raw_video = video_engine.assemble_video(
            clips=clips,
            voiceover_path=audio_path,
            subtitle_path=None,  # Subtitles will be burned in next
            output_name=f"{video_output_name}_raw",
            hook_style=chosen_hook_style,
            hook_text=hook_text or script["hook"]
        )
        append_job_log(job_id, "INFO", f"Đã ghép video thô: {raw_video}")
        
        # Burn in subtitles
        update_job(job_id, {"progress": 80})
        append_job_log(job_id, "INFO", "Đang chèn phụ đề vào video...")
        
        final_video = video_engine.add_subtitles(raw_video, srt_path)
        append_job_log(job_id, "INFO", f"Hoàn tất video: {final_video}")
        
    except Exception as e:
        append_job_log(job_id, "ERROR", f"Lỗi dựng video: {e}")
        raise e

    # 6. Save final video artifact
    update_job(job_id, {"progress": 100})
    
    # Save content details to content collection
    content_data = {
        "creator_id": creator_id,
        "creator_name": creator.get("name", creator_id),
        "video_path": final_video,
        "audio_path": audio_path,
        "srt_path": srt_path,
        "script": script,
        "hook_style": chosen_hook_style,
        "hook_text": hook_text or script["hook"],
        "voice_provider": voice_provider,
        "voice_id": voice_id,
    }
    
    save_content(
        job_id=job_id,
        content_type="personal_video",
        data=content_data
    )
    
    # Update job status
    update_job(job_id, {
        "status": "done",
        "result": {
            "video_path": final_video,
            "creator_id": creator_id,
            "hook_style": chosen_hook_style,
            "audio_duration": audio_duration
        }
    })
    
    append_job_log(job_id, "INFO", "✓ Job hoàn thành thành công!")
    return content_data


def _generate_mock_script_with_seeds(topic: str, seeds: list[dict]) -> dict:
    seed_str = ""
    if seeds:
        seed_details = []
        for s in seeds:
            name = s.get("name", "")
            cat = "quán" if s.get("category", "") == "restaurant" else "khách sạn"
            desc = s.get("description", "")
            seed_details.append(f"ghé {cat} {name} ({desc})")
        seed_str = " Và đừng quên " + ", ".join(seed_details)
        
    return {
        "hook": f"Đừng đi du lịch {topic} nếu bạn chưa biết điều này! 😱",
        "body": f"Hôm nay mình sẽ bật mí cho các bạn hành trình review {topic} siêu chất.{seed_str}. Nơi đây phong cảnh siêu đẹp và người dân cực kỳ mến khách luôn.",
        "cta": "Nhấn follow kênh mình để nhận thêm nhiều bí kíp du lịch nhé!"
    }
