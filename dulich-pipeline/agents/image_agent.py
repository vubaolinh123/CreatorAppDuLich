"""
Image Agent — Orchestrates the batch composition of seeding album images.
Generates 10 image formats for a given topic and saves metadata.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from tools.pexels_client import search_photos
from tools.image_composer import compose_image, FORMATS
from tools.db import save_content, create_job, update_job, append_job_log

def run_album_pipeline(
    job_id: str,
    topic: str,
    title: str,
    subtitle: str,
    creator_id: str = "lan_anh",
    canva_template_path: Optional[str] = None,
) -> dict:
    """
    Run Album Image Generation Pipeline.
    
    1. Search for stock background matching the topic.
    2. Generate 10 images (1 for each size format).
    3. Save results to MongoDB content collection.
    """
    append_job_log(job_id, "INFO", f"Khởi động Image Pipeline cho chủ đề: '{topic}'")
    append_job_log(job_id, "INFO", f"Tiêu đề: '{title}' | Phụ đề: '{subtitle}'")
    
    # 1. Search photo stock
    update_job(job_id, {"progress": 15})
    append_job_log(job_id, "INFO", "Đang tìm kiếm ảnh stock chất lượng cao...")
    
    bg_paths = []
    try:
        bg_paths = search_photos(query=topic, count=1)
        bg_image_path = bg_paths[0] if bg_paths else ""
        append_job_log(job_id, "INFO", f"Đã tìm thấy ảnh nền: {bg_image_path}")
    except Exception as e:
        append_job_log(job_id, "WARNING", f"Lỗi lấy ảnh stock: {e}. Sử dụng mock background.")
        bg_image_path = ""
        
    # 2. Compose 10 formats
    update_job(job_id, {"progress": 40})
    append_job_log(job_id, "INFO", f"Đang sản xuất hàng loạt 10 định dạng ảnh seeding...")
    
    generated_images = {}
    output_base_name = f"album_{job_id}"
    
    formats_list = list(FORMATS.keys())
    total_formats = len(formats_list)
    
    for idx, fmt_name in enumerate(formats_list):
        try:
            # Calculate format progress from 40 to 90
            prog = int(40 + (idx / total_formats) * 50)
            update_job(job_id, {"progress": prog})
            
            composed_path = compose_image(
                bg_image_path=bg_image_path,
                output_name=output_base_name,
                format_name=fmt_name,
                title=title,
                subtitle=subtitle,
                canva_template_path=canva_template_path
            )
            generated_images[fmt_name] = composed_path
            append_job_log(job_id, "INFO", f"✓ Đã tạo format '{fmt_name}': {composed_path}")
        except Exception as e:
            append_job_log(job_id, "ERROR", f"Lỗi tạo format '{fmt_name}': {e}")
            
    # 3. Save to MongoDB
    update_job(job_id, {"progress": 95})
    append_job_log(job_id, "INFO", "Đang lưu metadata album vào cơ sở dữ liệu...")
    
    album_data = {
        "creator_id": creator_id,
        "topic": topic,
        "title": title,
        "subtitle": subtitle,
        "background_used": bg_image_path,
        "canva_frame_used": canva_template_path or "mock_default",
        "images": generated_images,
    }
    
    save_content(
        job_id=job_id,
        content_type="album",
        data=album_data
    )
    
    update_job(job_id, {
        "status": "done",
        "progress": 100,
        "result": {
            "album_id": job_id,
            "total_images": len(generated_images),
            "images": generated_images
        }
    })
    
    append_job_log(job_id, "INFO", "✓ Job tạo Album seeding hoàn tất thành công!")
    return album_data


def image_agent(destination: str, template_id: str, llm: any) -> dict:
    """Legacy image agent to generate descriptions and image prompts via LLM."""
    try:
        import json
        prompt = (
            f"Generate a photo album description and 5 image prompts for the destination: '{destination}' "
            f"using template style: '{template_id}'. Return a JSON object with 'description' and 'prompts' (list of strings) keys."
        )
        resp = llm.invoke(prompt)
        content = resp.content.strip()
        # strip markdown code blocks if any
        if content.startswith("```"):
            if "json" in content:
                content = content.split("json\n", 1)[1]
            else:
                content = content.split("\n", 1)[1]
            content = content.rsplit("```", 1)[0].strip()
        
        data = json.loads(content)
        if "description" in data and "prompts" in data:
            return data
    except Exception:
        pass
        
    # Fallback
    return {
        "description": f"Photo album about {destination}",
        "prompts": [
            f"Scenic view of {destination} landmarks",
            f"Local food experience in {destination}",
            f"Adventure activity in {destination}",
            f"Relaxing sunset in {destination}",
            f"Traditional culture and people of {destination}"
        ]
    }
