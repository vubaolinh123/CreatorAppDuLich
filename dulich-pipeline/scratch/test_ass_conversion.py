import sys
import re
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.video_renderer import VideoEngine

def main():
    engine = VideoEngine()
    srt_path = "output/subtitles/sub_personal_lan_anh_job_1781087123873.srt"
    ass_path = "output/subtitles/sub_personal_lan_anh_job_1781087123873_test.ass"
    
    # Run conversion
    success = engine._convert_srt_to_ass(srt_path, ass_path, is_personal=True)
    print("Conversion success:", success)
    
    if success and Path(ass_path).exists():
        with open(ass_path, "r", encoding="utf-8") as f:
            print("\nGenerated ASS content:")
            sys.stdout.buffer.write(f.read().encode("utf-8"))
            print()
    else:
        print("Failed to convert or file not created.")

if __name__ == "__main__":
    main()
