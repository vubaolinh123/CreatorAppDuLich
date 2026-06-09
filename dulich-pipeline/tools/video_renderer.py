"""
Video Engine Agent — Assembles final video from clips + voiceover + subtitles.
Uses FFmpeg for encoding. Supports scene-based assembly with xfade transitions.
"""

import json
import subprocess
import os
from pathlib import Path
from typing import Optional


# Mapping of aspect ratios to FFmpeg dimensions
RATIO_DIMENSIONS = {
    "9:16": (1080, 1920),
    "1:1": (1080, 1080),
    "16:9": (1920, 1080),
}

# Available xfade transitions
XFADE_TRANSITIONS = {
    "fade": "fade",
    "dissolve": "dissolve",
    "wipeleft": "wipeleft",
    "wiperight": "wiperight",
    "slideright": "slideright",
    "slideleft": "slideleft",
    "circleopen": "circleopen",
    "circlecrop": "circlecrop",
}


class VideoEngine:
    def __init__(self, output_dir: str = "./output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

    # ─────────────────────────────────────────────────────────────────────────
    # Scene-based Assembly (NEW — Phase 5)
    # ─────────────────────────────────────────────────────────────────────────

    def assemble_from_scenes(
        self,
        clips: list[dict],
        voiceover_path: Optional[str],
        output_name: str,
        hook_style: str = "",
        hook_text: str = "",
        transition: str = "fade",
        transition_duration: float = 0.5,
        template_ratio: str = "9:16",
    ) -> str:
        """
        Assemble video from scene clips with xfade transitions.

        Each clip dict contains:
            path: str           — file path (empty = generate placeholder)
            duration: float     — target duration in seconds
            media_type: str     — "clip" | "image"
            scene_id: str       — identifier
            description: str    — scene description (for logging)

        Args:
            clips: List of scene clip dicts
            voiceover_path: Path to audio file (.wav/.mp3)
            output_name: Output filename without extension
            hook_style: Hook effect to apply on first scene
            hook_text: Text overlay for hook
            transition: xfade transition name
            transition_duration: Duration of each transition in seconds
            template_ratio: "9:16" | "1:1" | "16:9"

        Returns:
            Path to assembled video file
        """
        output_path = self.output_dir / "videos" / f"{output_name}.mp4"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        w, h = RATIO_DIMENSIONS.get(template_ratio, (1080, 1920))
        xfade_name = XFADE_TRANSITIONS.get(transition, "fade")

        if not clips:
            # Fallback: empty placeholder video
            clips = [{"path": "", "duration": 10, "media_type": "clip", "scene_id": "scene_1"}]

        # ── Build resolved clip list (generate placeholders for missing files) ──
        resolved = []
        for i, clip in enumerate(clips):
            clip_path = clip.get("path", "")
            duration = max(1.0, float(clip.get("duration", 5)))
            media_type = clip.get("media_type", "clip")

            if not clip_path or not os.path.exists(clip_path):
                # Generate gradient placeholder
                placeholder = self._generate_placeholder(
                    index=i,
                    duration=duration,
                    width=w,
                    height=h,
                    label=clip.get("description", f"Scene {i+1}"),
                )
                clip_path = placeholder

            resolved.append({
                "path": clip_path,
                "duration": duration,
                "media_type": media_type,
                "scene_id": clip.get("scene_id", f"scene_{i+1}"),
            })

        # ── Build FFmpeg command ──
        input_args = []
        filter_parts = []

        for i, clip in enumerate(resolved):
            clip_path = clip["path"]
            duration = clip["duration"]
            media_type = clip["media_type"]

            if media_type == "image":
                # Static image → loop with ken burns (zoompan)
                input_args.extend(["-loop", "1", "-t", str(duration), "-i", clip_path])
                filter_parts.append(
                    f"[{i}:v]scale={w*2}:{h*2},zoompan=z='if(lte(zoom,1.0),1.0,zoom-0.001)':d={int(duration * 25)}:"
                    f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={w}x{h}:fps=25,"
                    f"setsar=1,setpts=PTS-STARTPTS[v{i}]"
                )
            else:
                # Video clip — trim to duration, scale to output size
                input_args.extend(["-i", clip_path])
                scale_filter = (
                    f"[{i}:v]trim=duration={duration},"
                    f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
                    f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black,"
                    f"setsar=1,setpts=PTS-STARTPTS"
                )
                if i == 0 and hook_style:
                    from tools.hook_effects import apply_hook_effect
                    hook_filter = apply_hook_effect(
                        input_label=f"{i}:v",
                        output_label=f"v{i}",
                        style=hook_style,
                        duration_sec=duration,
                        hook_text=hook_text,
                    )
                    filter_parts.append(hook_filter)
                else:
                    filter_parts.append(f"{scale_filter}[v{i}]")

        # Apply image ken burns or hook on scene 0 after scaling
        # (hook effect already set above for clip type)

        # ── Chain xfade transitions ──
        if len(resolved) == 1:
            filter_complex = ";".join(filter_parts)
            last_label = "v0"
        else:
            xfade_parts = []
            cumulative_offset = 0.0
            prev_label = "v0"

            for i in range(len(resolved) - 1):
                cumulative_offset += resolved[i]["duration"] - transition_duration
                next_in = f"v{i+1}"
                out_label = f"vx{i}"
                xfade_parts.append(
                    f"[{prev_label}][{next_in}]xfade=transition={xfade_name}:"
                    f"duration={transition_duration}:offset={cumulative_offset:.3f}[{out_label}]"
                )
                prev_label = out_label

            filter_complex = ";".join(filter_parts) + ";" + ";".join(xfade_parts)
            last_label = f"vx{len(resolved) - 2}"

        # ── Compose final FFmpeg command ──
        cmd = ["ffmpeg", "-y", *input_args]

        if voiceover_path and os.path.exists(voiceover_path):
            audio_idx = len(resolved)
            cmd.extend(["-i", voiceover_path])
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
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode != 0:
                raise RuntimeError(f"FFmpeg error: {result.stderr[-600:]}")
        except FileNotFoundError:
            print(f"[WARNING] FFmpeg not found. Generating dummy video: {output_path}")
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(str(output_path), "wb") as f:
                f.write(b"DUMMY MP4 VIDEO CONTENT FOR TESTING")

        return str(output_path)

    def _generate_placeholder(
        self,
        index: int,
        duration: float,
        width: int = 1080,
        height: int = 1920,
        label: str = "",
    ) -> str:
        """Generate a gradient placeholder video for missing clips."""
        placeholder_path = self.output_dir / "placeholders" / f"placeholder_{index}.mp4"
        placeholder_path.parent.mkdir(parents=True, exist_ok=True)

        # Cycle through attractive gradient colors
        colors = [
            "0x1a1a2e:0x16213e",  # Deep navy
            "0x1a1a2e:0x533483",  # Purple
            "0x0f3460:0x533483",  # Blue-purple
            "0x1b4332:0x081c15",  # Forest green
            "0x641220:0x6e1423",  # Deep red
            "0x212529:0x343a40",  # Dark grey
        ]
        c1, c2 = colors[index % len(colors)].split(":")

        # Label text for placeholder (escape special chars)
        safe_label = label[:40].replace(":", "\\:").replace("'", "\\'") if label else f"Scene {index + 1}"

        filter_str = (
            f"gradients=s={width}x{height}:c0={c1}:c1={c2}:x0=0:y0=0:x1={width}:y1={height}:duration={duration}:speed=0,"
            f"drawtext=fontsize=36:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2:"
            f"text='Scene {index+1}':alpha=0.8,"
            f"drawtext=fontsize=22:fontcolor=white@0.5:x=(w-text_w)/2:y=(h-text_h)/2+50:"
            f"text='{safe_label}':alpha=0.6"
        )

        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"color=c={c1}:s={width}x{height}:d={duration}",
            "-vf", f"drawtext=fontsize=40:fontcolor=white@0.9:x=(w-text_w)/2:y=(h-text_h)/2:text='Scene {index+1}':font=Arial",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-t", str(duration),
            str(placeholder_path),
        ]

        try:
            subprocess.run(cmd, capture_output=True, timeout=30)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            # Fallback: write dummy
            with open(str(placeholder_path), "wb") as f:
                f.write(b"DUMMY PLACEHOLDER VIDEO")

        return str(placeholder_path)

    # ─────────────────────────────────────────────────────────────────────────
    # Legacy Assembly (kept for backward compatibility)
    # ─────────────────────────────────────────────────────────────────────────

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
        """
        Legacy clip assembly. Wraps assemble_from_scenes for backward compatibility.
        """
        return self.assemble_from_scenes(
            clips=clips,
            voiceover_path=voiceover_path,
            output_name=output_name,
            hook_style=hook_style,
            hook_text=hook_text,
        )

    def add_subtitles(self, video_path: str, subtitle_path: str) -> str:
        output_path = video_path.replace(".mp4", "_subtitled.mp4")
        # Escape Windows paths for FFmpeg subtitle filter
        safe_srt = subtitle_path.replace("\\", "/").replace(":", "\\:")
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-vf", f"subtitles='{safe_srt}':force_style='FontSize=14,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,Outline=2'",
            "-c:a", "copy",
            output_path,
        ]
        try:
            subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return video_path  # Return original if subtitles fail
        return output_path
