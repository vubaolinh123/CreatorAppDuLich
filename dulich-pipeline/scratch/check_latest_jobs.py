import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.db import get_db

def main():
    db = get_db()
    jobs_col = db["jobs"]
    
    # Get the latest job
    latest_job = jobs_col.find_one(sort=[("created_at", -1)])
    if not latest_job:
        print("No jobs found in MongoDB.")
        return
        
    print(f"Latest Job ID: {latest_job.get('_id')}")
    print(f"Created At: {latest_job.get('created_at')}")
    print(f"Status: {latest_job.get('status')}")
    print(f"Creator: {latest_job.get('creator_id')}")
    print(f"Voice Provider: {latest_job.get('voice_provider')}")
    print(f"Voice ID: {latest_job.get('voice_id')}")
    print("\nLogs:")
    for log in latest_job.get("logs", []):
        print(f"[{log.get('level')}] {log.get('text')}")

if __name__ == "__main__":
    main()
