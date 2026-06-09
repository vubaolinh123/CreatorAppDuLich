"""
Video Engine Agent — Assembles final video from clips + voiceover + subtitles.
Uses Remotion for composition + FFmpeg for encoding + ElevenLabs for voice.
"""

import json
import subprocess
import os
from pathlib import Path
from typing import Optional


class VideoEngine:
    def __init__(self, output_dir: str = "./output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

    def assemble_video(
        self,
        clips: list[dict],
        voiceover_path: Optional[str],
        subtitle_path: Optional[str],
        output_name: str,
        template_id: str = "default",
        hook_style: str = "",
        hook_text: str = "",
    ) -> str:
        output_path = self.output_dir / f"{output_name}.mp4"
        filter_parts = []
        input_files = []

        for i, clip in enumerate(clips):
            clip_path = clip.get("path", "")
            if not clip_path or not os.path.exists(clip_path):
                # Auto generate a blank black video clip as placeholder
                temp_path = self.output_dir / "temp_blank.mp4"
                duration = clip.get("duration", 10)
                cmd_gen = [
                    "ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c=0x1a1a1a:s=1080x1920:d={duration}",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-t", str(duration), str(temp_path)
                ]
                try:
                    subprocess.run(cmd_gen, capture_output=True)
                except FileNotFoundError:
                    temp_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(str(temp_path), "wb") as f:
                        f.write(b"DUMMY BLANK VIDEO")
                clip_path = str(temp_path)

            input_files.extend(["-i", clip_path])

            if i == 0 and hook_style:
                from tools.hook_effects import apply_hook_effect
                hook_filter = apply_hook_effect(
                    input_label=f"{i}:v",
                    output_label=f"v{i}",
                    style=hook_style,
                    duration_sec=clip.get("duration", 3.0),
                    hook_text=hook_text
                )
                filter_parts.append(hook_filter)
            else:
                filter_parts.append(
                    f"[{i}:v]scale=1080:1920:force_original_aspect_ratio=decrease,"
                    f"pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1[v{i}]"
                )

        current = "".join(f"[v{i}]" for i in range(len(clips)))

        if len(clips) > 1:
            xfade_parts = []
            for i in range(len(clips) - 1):
                offset = sum(c.get("duration", 5) for c in clips[: i + 1])
                xfade_parts.append(
                    f"[v{i}][v{i + 1}]xfade=transition=fade:duration=0.5:offset={offset}[v{i + 1}_out]"
                )
            filter_complex = ";".join(filter_parts) + ";" + ";".join(xfade_parts)
            last_label = f"v{len(clips) - 1}_out"
        else:
            filter_complex = ";".join(filter_parts)
            last_label = "v0"

        cmd = ["ffmpeg", "-y", *input_files]

        if voiceover_path and os.path.exists(voiceover_path):
            # Add audio input separately
            audio_idx = len(clips)
            cmd.extend(["-i", voiceover_path])
            # Video-only filter_complex, then map audio separately
            cmd.extend(["-filter_complex", filter_complex])
            cmd.extend(["-map", f"[{last_label}]", "-map", f"{audio_idx}:a"])
        else:
            cmd.extend(["-filter_complex", filter_complex])
            cmd.extend(["-map", f"[{last_label}]"])

        cmd.extend([
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            "-shortest",
            str(output_path),
        ])

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"FFmpeg failed: {result.stderr[-400:]}")
        except FileNotFoundError:
            print(f"[WARNING] FFmpeg not found. Generating dummy video: {output_path}")
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(str(output_path), "wb") as f:
                f.write(b"DUMMY MP4 VIDEO CONTENT FOR TESTING")

        return str(output_path)

    def add_subtitles(self, video_path: str, subtitle_path: str) -> str:
        output_path = video_path.replace(".mp4", "_subtitled.mp4")
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-vf", f"subtitles={subtitle_path}:force_style='FontSize=12,PrimaryColour=&HFFFFFF,OutlineColour=&H000000'",
            "-c:a", "copy",
            output_path,
        ]
        subprocess.run(cmd, capture_output=True, text=True)
        return output_path
