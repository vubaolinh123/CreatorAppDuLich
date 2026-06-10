import requests
import json
import sys

def test():
    url = "http://localhost:7788/assemble"
    
    script = {
        "hook": "Chào các bạn nhé!",
        "body": "Đà Lạt rất đẹp.",
        "cta": "Follow mình."
    }
    scenes_meta = [
        {"scene_id": "scene_1", "description": "Cảnh 1", "min_duration_sec": 5, "type": "clip"}
    ]
    
    data = {
        "job_id": "test_job_123456",
        "transition": "fade",
        "voice_mode": "elevenlabs",
        "voice_id": "pNInz6obpgqjVWtg2t5c",
        "creator_id": "lan_anh",
        "template_ratio": "9:16",
        "hook_style": "bold_impact",
        "hook_text": "",
        "hook_title": "Đừng đi Đà Lạt",
        "hook_subtitle": "nếu chưa biết điều này",
        "video_type": "personal",
        "script": json.dumps(script),
        "scenes_meta": json.dumps(scenes_meta)
    }
    
    # Send as multipart
    files = {
        "dummy": ("dummy.txt", b"hello world")
    }
    
    print("Sending POST request to", url)
    r = requests.post(url, data=data, files=files)
    print("Response status:", r.status_code)
    try:
        res = r.json()
        print("Response success:", res.get("success"))
        print("Response JSON keys:", list(res.keys()))
    except Exception as e:
        print("Failed to parse JSON:", e)

if __name__ == "__main__":
    test()
