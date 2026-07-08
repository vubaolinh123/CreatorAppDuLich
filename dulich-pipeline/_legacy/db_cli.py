"""
db_cli.py — CLI bridge for Tauri backend to interact with MongoDB.
Avoids native Rust driver compile overhead.
"""

from __future__ import annotations

import sys
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from tools.db import creators_col, get_db, now_utc
from tools.hook_effects import analyze_reference_video
from agents.personal_video_agent import ensure_creators_seeded

def print_result(data: dict | list | str, success: bool = True):
    print(json.dumps({
        "success": success,
        "data": data
    }, ensure_ascii=False))
    sys.exit(0)

def main():
    if len(sys.argv) < 2:
        print_result("Action argument missing.", success=False)

    action = sys.argv[1]

    # Ensure creators collection is seeded
    ensure_creators_seeded()

    col = creators_col()

    if action == "get_creators":
        try:
            creators = list(col.find({}))
            # Serialize _id to id
            res_list = []
            for c in creators:
                res_list.append({
                    "id": c.get("_id"),
                    "name": c.get("name"),
                    "voice_provider": c.get("voice_provider"),
                    "voice_id": c.get("voice_id"),
                    "hook_preference": c.get("hook_preference"),
                    "created_at": c.get("created_at"),
                    "updated_at": c.get("updated_at"),
                })
            print_result(res_list)
        except Exception as e:
            print_result(f"Error fetching creators: {e}", success=False)

    elif action == "save_creator":
        if len(sys.argv) < 3:
            print_result("Creator payload missing.", success=False)
        
        try:
            payload_str = sys.argv[2]
            payload = json.loads(payload_str)
            cid = payload.get("id")
            if not cid:
                print_result("id is required to save creator.", success=False)
            
            existing = col.find_one({"_id": cid})
            
            doc = {
                "name": payload.get("name", "Unnamed"),
                "voice_provider": payload.get("voice_provider", "vbee"),
                "voice_id": payload.get("voice_id", "default"),
                "hook_preference": payload.get("hook_preference", "zoom_in"),
                "updated_at": now_utc().isoformat(),
            }
            
            if existing:
                col.update_one({"_id": cid}, {"$set": doc})
            else:
                doc["_id"] = cid
                doc["created_at"] = now_utc().isoformat()
                col.insert_one(doc)
                
            print_result({"id": cid, "status": "saved"})
        except Exception as e:
            print_result(f"Error saving creator: {e}", success=False)

    elif action == "analyze_video":
        if len(sys.argv) < 3:
            print_result("Video path missing.", success=False)
            
        video_path = sys.argv[2]
        try:
            res = analyze_reference_video(video_path)
            print_result(res)
        except Exception as e:
            print_result(f"Error analyzing video: {e}", success=False)

    elif action == "get_seeding":
        try:
            from tools.db import seeding_col
            items = list(seeding_col().find({}))
            res_list = []
            for item in items:
                res_list.append({
                    "id": str(item.get("_id")),
                    "name": item.get("name"),
                    "category": item.get("category"),
                    "location": item.get("location"),
                    "description": item.get("description"),
                    "mention_guide": item.get("mention_guide"),
                    "status": item.get("status", "active"),
                })
            print_result(res_list)
        except Exception as e:
            print_result(f"Error fetching seeding items: {e}", success=False)

    elif action == "save_seeding":
        if len(sys.argv) < 3:
            print_result("Seeding payload missing.", success=False)
        try:
            from tools.db import seeding_col, new_doc, ObjectId, MONGO_AVAILABLE
            payload_str = sys.argv[2]
            payload = json.loads(payload_str)
            sid = payload.get("id")
            
            doc = {
                "name": payload.get("name", "Unnamed"),
                "category": payload.get("category", "restaurant"),
                "location": payload.get("location", "Vietnam"),
                "description": payload.get("description", ""),
                "mention_guide": payload.get("mention_guide", ""),
                "status": payload.get("status", "active"),
                "updated_at": now_utc().isoformat(),
            }
            
            scol = seeding_col()
            if sid and sid != "undefined":
                # Convert string ID to ObjectId if possible
                query = {"_id": ObjectId(sid) if MONGO_AVAILABLE else sid}
                scol.update_one(query, {"$set": doc})
                print_result({"id": sid, "status": "updated"})
            else:
                new_item = new_doc(**doc)
                scol.insert_one(new_item)
                print_result({"id": new_item["_id"], "status": "created"})
        except Exception as e:
            print_result(f"Error saving seeding item: {e}", success=False)

    elif action == "delete_seeding":
        if len(sys.argv) < 3:
            print_result("Seeding ID missing.", success=False)
        try:
            from tools.db import seeding_col, ObjectId, MONGO_AVAILABLE
            sid = sys.argv[2]
            scol = seeding_col()
            query = {"_id": ObjectId(sid) if MONGO_AVAILABLE else sid}
            scol.delete_one(query)
            print_result({"id": sid, "status": "deleted"})
        except Exception as e:
            print_result(f"Error deleting seeding item: {e}", success=False)
            
    elif action == "generate_scene_plan":
        # Args: job_id, creator_id, topic/script_text, scene_mode, template_ratio, scene_count, [custom_scenes_json]
        if len(sys.argv) < 6:
            print_result("Missing args: job_id, creator_id, script_text, scene_mode, template_ratio required.", success=False)
        try:
            from agents.personal_video_agent import run_research_and_script
            job_id = sys.argv[2]
            creator_id = sys.argv[3]
            script_text = sys.argv[4]
            scene_mode = sys.argv[5] if len(sys.argv) > 5 else "ai"
            template_ratio = sys.argv[6] if len(sys.argv) > 6 else "9:16"
            scene_count = int(sys.argv[7]) if len(sys.argv) > 7 and sys.argv[7].isdigit() else 0
            hook_style = sys.argv[8] if len(sys.argv) > 8 else ""
            hook_text = sys.argv[9] if len(sys.argv) > 9 else ""
            provider_override = sys.argv[10] if len(sys.argv) > 10 else ""
            custom_scenes_json = sys.argv[11] if len(sys.argv) > 11 else "[]"
            video_type = sys.argv[12] if len(sys.argv) > 12 else "personal"
            voice_id_override = sys.argv[13] if len(sys.argv) > 13 else ""
            
            custom_scenes = json.loads(custom_scenes_json) if custom_scenes_json != "[]" else None

            # Create job entry first
            from tools.db import get_db, now_utc, new_doc
            db = get_db()
            jobs = db["jobs"] if hasattr(db, "__getitem__") else None
            if jobs is not None:
                job_doc = new_doc(
                    _id=job_id,
                    status="running",
                    creator_id=creator_id,
                    script_text=script_text,
                    video_type=video_type,
                    created_at=now_utc().isoformat(),
                )
                try:
                    jobs.insert_one(job_doc)
                except Exception:
                    jobs.update_one({"_id": job_id}, {"$set": job_doc}, upsert=True)

            result = run_research_and_script(
                job_id=job_id,
                creator_id=creator_id,
                script_text=script_text,
                hook_style=hook_style,
                hook_text=hook_text,
                provider_override=provider_override,
                template_ratio=template_ratio,
                scene_mode=scene_mode,
                custom_scenes=custom_scenes,
                scene_count=scene_count,
                video_type=video_type,
                voice_id_override=voice_id_override,
            )
            print_result(result)
        except Exception as e:
            import traceback
            print(traceback.format_exc(), file=sys.stderr)
            print_result(f"Error in generate_scene_plan: {e}", success=False)

    elif action == "assemble_video":
        # Args: job_id, scene_uploads_json, transition, hook_style, hook_text, hook_title, hook_subtitle, video_type, voice_provider, voice_id
        if len(sys.argv) < 4:
            print_result("Missing args: job_id, scene_uploads_json required.", success=False)
        try:
            from agents.personal_video_agent import run_assemble_video
            job_id = sys.argv[2]
            scene_uploads_json = sys.argv[3]
            transition = sys.argv[4] if len(sys.argv) > 4 else "fade"
            hook_style = sys.argv[5] if len(sys.argv) > 5 else ""
            hook_text = sys.argv[6] if len(sys.argv) > 6 else ""
            hook_title = sys.argv[7] if len(sys.argv) > 7 else ""
            hook_subtitle = sys.argv[8] if len(sys.argv) > 8 else ""
            video_type = sys.argv[9] if len(sys.argv) > 9 else ""
            voice_provider = sys.argv[10] if len(sys.argv) > 10 else ""
            voice_id = sys.argv[11] if len(sys.argv) > 11 else ""

            scene_uploads = json.loads(scene_uploads_json)
            result = run_assemble_video(
                job_id=job_id,
                scene_uploads=scene_uploads,
                transition=transition,
                hook_style=hook_style,
                hook_text=hook_text,
                hook_title=hook_title,
                hook_subtitle=hook_subtitle,
                video_type=video_type,
                voice_provider=voice_provider,
                voice_id=voice_id,
            )
            print_result(result)
        except Exception as e:
            import traceback
            print(traceback.format_exc(), file=sys.stderr)
            print_result(f"Error in assemble_video: {e}", success=False)

    elif action == "preview_voice":
        if len(sys.argv) < 5:
            print_result("Missing args: provider, voice_id, text required.", success=False)
        try:
            from tools.voice_generator import VoiceGenerator
            provider = sys.argv[2]
            voice_id = sys.argv[3]
            text = sys.argv[4]
            output_name = sys.argv[5] if len(sys.argv) > 5 else "preview_temp"

            gen = VoiceGenerator(provider=provider)
            audio_path = gen.generate_voice(
                text=text,
                voice_id=voice_id,
                output_name=output_name,
                speed=1.0
            )
            print_result({"audio_path": audio_path})
        except Exception as e:
            print_result(f"Error in preview_voice: {e}", success=False)

    # ── Frame Management ─────────────────────────────────────────────────────
    elif action == "learn_frames":
        if len(sys.argv) < 3:
            print_result("Missing args: zip_path required.", success=False)
        try:
            from tools.frame_learner import learn_from_zip, learn_single_frame
            from tools.vision_provider import VisionProvider
            path = sys.argv[2]
            creator_id = sys.argv[3] if len(sys.argv) > 3 else "system"

            vision = VisionProvider.from_config()
            path_lower = path.lower()

            if path_lower.endswith(".zip"):
                results = learn_from_zip(path, creator_id, vision)
                print_result({
                    "total": len(results),
                    "frames": [{"frame_id": r["frame_id"], "name": r.get("name"), "width": r.get("width"), "height": r.get("height")} for r in results]
                })
            elif path_lower.endswith(".png"):
                doc = learn_single_frame(path, creator_id, vision)
                print_result({
                    "frame_id": doc["frame_id"],
                    "name": doc.get("name"),
                    "width": doc.get("width"),
                    "height": doc.get("height"),
                    "compatible_formats": doc.get("compatible_formats", []),
                })
            else:
                print_result(f"Unsupported file: {path} (only .zip and .png)", success=False)
        except Exception as e:
            import traceback; traceback.print_exc()
            print_result(f"Error in learn_frames: {e}", success=False)

    elif action == "list_frames":
        try:
            from tools.frame_learner import list_learned_frames
            creator_id = ""
            format_name = ""
            # Parse optional --creator and --format args
            if len(sys.argv) > 2:
                for i in range(2, len(sys.argv) - 1):
                    if sys.argv[i] == "--creator":
                        creator_id = sys.argv[i + 1]
                    elif sys.argv[i] == "--format":
                        format_name = sys.argv[i + 1]

            frames = list_learned_frames(
                creator_id=creator_id if creator_id else None,
                format_name=format_name if format_name else None,
            )
            # Serialize for JSON output
            out = []
            for f in frames:
                out.append({
                    "frame_id": f.get("frame_id"),
                    "name": f.get("name"),
                    "thumbnail_path": f.get("thumbnail_path"),
                    "width": f.get("width"),
                    "height": f.get("height"),
                    "aspect_ratio": f.get("aspect_ratio"),
                    "compatible_formats": f.get("compatible_formats", []),
                    "style_tags": f.get("analysis", {}).get("style_tags", []),
                    "color_palette": f.get("analysis", {}).get("color_palette", []),
                    "usage_count": f.get("usage_count", 0),
                    "uploaded_by": f.get("uploaded_by"),
                    "uploaded_at": f.get("uploaded_at"),
                })
            print_result(out)
        except Exception as e:
            import traceback; traceback.print_exc()
            print_result(f"Error in list_frames: {e}", success=False)

    elif action == "analyze_frame":
        if len(sys.argv) < 3:
            print_result("Missing args: frame_path required.", success=False)
        try:
            from tools.frame_analyzer import analyze_frame
            from tools.vision_provider import VisionProvider
            frame_path = sys.argv[2]
            vision = VisionProvider.from_config()
            result = analyze_frame(frame_path, vision=vision)
            print_result(result)
        except Exception as e:
            import traceback; traceback.print_exc()
            print_result(f"Error in analyze_frame: {e}", success=False)

    elif action == "delete_frame":
        if len(sys.argv) < 3:
            print_result("Missing args: frame_id required.", success=False)
        try:
            from tools.frame_learner import delete_frame
            frame_id = sys.argv[2]
            ok = delete_frame(frame_id)
            print_result({"deleted": ok})
        except Exception as e:
            print_result(f"Error in delete_frame: {e}", success=False)

    else:
        print_result(f"Unknown action: {action}", success=False)

if __name__ == "__main__":
    main()
