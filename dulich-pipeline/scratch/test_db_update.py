import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.db import get_db
import pprint

def test():
    db = get_db()
    jobs = db["jobs"]
    
    # Update test_job_123456
    r = jobs.update_one(
        {"_id": "test_job_123456"},
        {"$set": {"hook_title": "abc", "hook_subtitle": "def"}}
    )
    print("Matched:", r.matched_count, "Modified:", r.modified_count)
    
    # Fetch and print
    doc = jobs.find_one({"_id": "test_job_123456"})
    pprint.pprint(doc)

if __name__ == "__main__":
    test()
