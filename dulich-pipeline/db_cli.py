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
            
    else:
        print_result(f"Unknown action: {action}", success=False)

if __name__ == "__main__":
    main()
