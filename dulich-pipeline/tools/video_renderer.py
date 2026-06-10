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
            clips = [{"path": "", "duration": 10, "media_type": "clip", "scene_id": "scene_1"}]

        # ── Phase 1: Resolve + Normalize every clip → temp H264 MP4 ─────────
        # This handles iPhone MOV, HEVC, VFR, metadata rotation, etc.
        norm_dir = self.output_dir / "normalized" / output_name
        norm_dir.mkdir(parents=True, exist_ok=True)

        normalized: list[dict] = []
        for i, clip in enumerate(clips):
            clip_path = clip.get("path", "")
            target_dur = max(1.0, float(clip.get("duration", 5)))
            media_type  = clip.get("media_type", "clip")
            scene_id    = clip.get("scene_id", f"scene_{i+1}")

            if not clip_path or not os.path.exists(clip_path):
                # Generate colour-card placeholder
                clip_path = self._generate_placeholder(
                    index=i, duration=target_dur, width=w, height=h,
                    label=clip.get("description", f"Scene {i+1}"),
                )
                media_type = "clip"     # placeholder is already a proper mp4

            norm_path = str(norm_dir / f"norm_{i:03d}.mp4")

            if media_type == "image":
                # Static image → zoompan / ken-burns
                ok = self._normalize_image(clip_path, norm_path, target_dur, w, h)
            else:
                # Video → transcode to H264 CFR 30 fps, crop to target size
                ok = self._normalize_clip(clip_path, norm_path, target_dur, w, h)

            if not ok:
                # Fall back to placeholder when normalisation fails
                print(f"[VideoEngine] ⚠ Norm failed for scene {i+1}, using placeholder", flush=True)
                placeholder = self._generate_placeholder(i, target_dur, w, h, f"Scene {i+1}")
                ok = self._normalize_clip(placeholder, norm_path, target_dur, w, h)
                if not ok:
                    import shutil
                    shutil.copy(placeholder, norm_path)

            # Measure actual duration of normalised clip
            actual_dur = self._probe_duration(norm_path) or target_dur
            normalized.append({"path": norm_path, "duration": actual_dur, "scene_id": scene_id})
            print(f"[VideoEngine] ✓ norm_{i:03d}.mp4 — {actual_dur:.1f}s  ({scene_id})", flush=True)

        # ── Phase 2: Concatenate with xfade transitions ───────────────────────
        if len(normalized) == 1:
            # Single clip — just copy (possibly with audio mix)
            single = normalized[0]["path"]
            cmd = ["ffmpeg", "-y", "-i", single]
            if voiceover_path and os.path.exists(voiceover_path):
                cmd += ["-i", voiceover_path,
                        "-filter_complex", "[0:v]copy[vout];[1:a]acopy[aout]",
                        "-map", "[vout]", "-map", "[aout]"]
            else:
                cmd += ["-vn" if False else "-map", "0:v"]
            cmd += ["-c:v", "libx264", "-preset", "fast", "-crf", "23",
                    "-c:a", "aac", "-b:a", "128k", "-shortest", str(output_path)]
        else:
            # Multi-clip xfade
            td = min(transition_duration, 0.5)   # cap at 0.5 s
            input_args = []
            for n in normalized:
                input_args += ["-i", n["path"]]

            # Build filter_complex  (all clips already normalised — no scale needed)
            fparts = []
            for i in range(len(normalized)):
                fparts.append(f"[{i}:v]setpts=PTS-STARTPTS[v{i}]")

            # Chain xfade
            prev = "v0"
            offset = 0.0
            xfade_parts = []
            for i in range(len(normalized) - 1):
                offset += normalized[i]["duration"] - td
                out = f"vx{i}"
                xfade_parts.append(
                    f"[{prev}][v{i+1}]xfade=transition={xfade_name}:"
                    f"duration={td:.3f}:offset={offset:.3f}[{out}]"
                )
                prev = out

            last_v = prev   # e.g. "vx3"

            # Audio: mix voiceover with video audio (or just voiceover)
            audio_filter = ""
            audio_map   = []
            if voiceover_path and os.path.exists(voiceover_path):
                vo_idx = len(normalized)
                input_args += ["-i", voiceover_path]
                audio_filter = f";[{vo_idx}:a]acopy[aout]"
                audio_map   = ["-map", "[aout]"]
            else:
                # No voiceover — silence
                audio_filter = f";aevalsrc=0:d={sum(n['duration'] for n in normalized)}[aout]"
                audio_map   = ["-map", "[aout]"]

            filter_complex = (
                ";".join(fparts)
                + ";"
                + ";".join(xfade_parts)
                + audio_filter
            )

            cmd = (
                ["ffmpeg", "-y"]
                + input_args
                + ["-filter_complex", filter_complex]
                + ["-map", f"[{last_v}]"]
                + audio_map
                + ["-c:v", "libx264", "-preset", "fast", "-crf", "23",
                   "-pix_fmt", "yuv420p",
                   "-c:a", "aac", "-b:a", "128k",
                   "-movflags", "+faststart",
                   "-shortest",
                   str(output_path)]
            )

        print(f"[VideoEngine] FFmpeg assemble: {' '.join(cmd[:8])} ...", flush=True)
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            if result.returncode != 0:
                raise RuntimeError(f"FFmpeg error: {result.returncode} (Invalid argument)\n{result.stderr[-800:]}")
        except FileNotFoundError:
            print("[WARNING] FFmpeg not found — writing dummy file")
            with open(str(output_path), "wb") as f:
                f.write(b"DUMMY MP4 VIDEO CONTENT FOR TESTING")

        return str(output_path)

    # ── Normalize helpers ─────────────────────────────────────────────────────

    def _normalize_clip(self, src: str, dst: str, duration: float, w: int, h: int) -> bool:
        """
        Transcode a video clip to H264 MP4 with:
          - CFR 30 fps (handles iPhone VFR)
          - Scale + pad to (w x h) with black bars
          - Auto-rotate metadata (handles portrait/landscape rotation)
          - Trim to `duration` seconds
        Returns True on success.
        """
        vf = (
            f"fps=30,"
            f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
            f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black,"
            f"setsar=1,setpts=PTS-STARTPTS"
        )
        cmd = [
            "ffmpeg", "-y",
            "-i", src,
            "-t", str(duration),        # trim to target duration
            "-vf", vf,
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-an",                      # strip audio (added back later)
            dst,
        ]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if r.returncode == 0 and os.path.exists(dst) and os.path.getsize(dst) > 1000:
                return True
            print(f"[VideoEngine] _normalize_clip failed ({r.returncode}): {r.stderr[-300:]}", flush=True)
            return False
        except Exception as e:
            print(f"[VideoEngine] _normalize_clip exception: {e}", flush=True)
            return False

    def _normalize_image(self, src: str, dst: str, duration: float, w: int, h: int) -> bool:
        """Convert a static image to a MP4 clip with zoompan (ken burns) effect."""
        vf = (
            f"scale={w*2}:{h*2},"
            f"zoompan=z='if(lte(zoom,1.0),1.0,zoom-0.0005)':d={int(duration*25)}:"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={w}x{h}:fps=25,"
            f"setsar=1,setpts=PTS-STARTPTS"
        )
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", src,
            "-t", str(duration),
            "-vf", vf,
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-an", dst,
        ]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            return r.returncode == 0 and os.path.exists(dst) and os.path.getsize(dst) > 1000
        except Exception:
            return False

    def _probe_duration(self, path: str) -> Optional[float]:
        """Use ffprobe to get actual video duration in seconds."""
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            path,
        ]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            return float(r.stdout.strip())
        except Exception:
            return None


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
