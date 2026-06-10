import subprocess
import os

def main():
    video_path = "output/videos/video_personal_lan_anh_job_1781087123873_raw.mp4"
    srt_path = "output/subtitles/sub_personal_lan_anh_job_1781087123873.srt"
    ass_path = "output/subtitles/sub_personal_lan_anh_job_1781087123873_test.ass"
    output_path = "output/videos/video_personal_lan_anh_job_1781087123873_debug_subtitled.mp4"
    
    # Clean output if exists
    if os.path.exists(output_path):
        os.remove(output_path)
        
    safe_render = ass_path.replace("\\", "/").replace(":", "\\:")
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", f"subtitles='{safe_render}'",
        "-c:a", "copy",
        output_path
    ]
    
    print("Running command:", " ".join(cmd))
    r = subprocess.run(cmd, capture_output=True, text=True)
    print("\nReturn code:", r.returncode)
    print("\nStderr output:")
    print(r.stderr)

if __name__ == "__main__":
    main()
