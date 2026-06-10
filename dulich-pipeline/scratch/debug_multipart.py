import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from server import parse_multipart
import io

class MockHeaders:
    def __init__(self, headers):
        self.headers = headers
    def get(self, name, default=None):
        return self.headers.get(name, default)

class MockHandler:
    def __init__(self, content_type, body_bytes):
        self.headers = MockHeaders({
            "Content-Type": content_type,
            "Content-Length": str(len(body_bytes))
        })
        self.rfile = io.BytesIO(body_bytes)

def test_parse():
    # Set console output encoding to utf-8
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

    from urllib3.filepost import encode_multipart_formdata

    fields_dict = {
        "job_id": "test_job_123456",
        "transition": "fade",
        "voice_mode": "mock",
        "creator_id": "lan_anh",
        "template_ratio": "9:16",
        "hook_style": "bold_impact",
        "hook_text": "",
        "hook_title": "Đừng đi Đà Lạt",
        "hook_subtitle": "nếu chưa biết điều này",
        "video_type": "personal",
        "script": "{}",
        "scenes_meta": "[]"
    }
    
    body, content_type = encode_multipart_formdata({
        **fields_dict,
        "dummy": ("dummy.txt", b"hello world")
    })
    
    handler = MockHandler(content_type, body)
    fields, files = parse_multipart(handler)
    print("Parsed fields:")
    for k, v in fields.items():
        print(f"  {k}: {v}")
        
if __name__ == "__main__":
    test_parse()
