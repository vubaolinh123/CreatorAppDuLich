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
        hook_title: str = "",
        hook_subtitle: str = "",
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

            # Apply hook effect to the first clip (i == 0) if specified
            if i == 0 and hook_style == "hook_overlay":
                print(f"[VideoEngine] Đang tạo Hook Overlay PNG cho Cảnh 1...", flush=True)
                temp_hook_path = str(norm_dir / f"norm_000_hook.mp4")
                try:
                    from tools.hook_overlay import build_overlay as build_hook_overlay
                    overlay_png = str(norm_dir / "hook_overlay.png")
                    # Split subtitle into lines (separated by |) or use as single line
                    script_lines_list = [s.strip() for s in (hook_subtitle or "").split("|") if s.strip()]
                    if not script_lines_list:
                        script_lines_list = [hook_subtitle or "Review và chấm điểm"]
                    build_hook_overlay(
                        title=hook_title or "ĐÀ LẠT",
                        script_lines=tuple(script_lines_list),
                        caption="",
                        out_path=overlay_png,
                        with_caption=False,
                    )
                    # Composite overlay PNG onto scaled video
                    filter_str = (
                        f"[0:v]scale=1080:1920:force_original_aspect_ratio=decrease,"
                        f"pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1[bg];"
                        f"[bg][1:v]overlay=0:0:format=auto[vout]"
                    )
                    cmd = [
                        "ffmpeg", "-y",
                        "-i", norm_path,
                        "-i", overlay_png,
                        "-filter_complex", filter_str,
                        "-map", "[vout]",
                        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                        "-pix_fmt", "yuv420p",
                        temp_hook_path
                    ]

                    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                    if r.returncode == 0 and os.path.exists(temp_hook_path) and os.path.getsize(temp_hook_path) > 1000:
                        os.replace(temp_hook_path, norm_path)
                        print(f"[VideoEngine] ✓ Đã áp dụng thành công Hook Overlay lên Cảnh 1.", flush=True)
                    else:
                        print(f"[VideoEngine] ⚠ Lỗi áp dụng Hook Overlay (FFmpeg): {r.stderr[-300:]}", flush=True)
                except Exception as e:
                    print(f"[VideoEngine] ⚠ Lỗi tạo Hook Overlay: {e}", flush=True)
            elif i == 0 and hook_style:
                print(f"[VideoEngine] Đang áp dụng hiệu ứng Hook: '{hook_style}' cho Cảnh 1...", flush=True)
                temp_hook_path = str(norm_dir / f"norm_000_hook.mp4")
                try:
                    from tools.hook_effects import apply_hook_effect
                    filter_str = apply_hook_effect(
                        input_label="0:v",
                        output_label="vout",
                        style=hook_style,
                        duration_sec=actual_dur,
                        hook_text=hook_text,
                        hook_title=hook_title,
                        hook_subtitle=hook_subtitle,
                    )

                    cmd = [
                        "ffmpeg", "-y",
                        "-i", norm_path,
                        "-filter_complex", filter_str,
                        "-map", "[vout]",
                        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                        "-pix_fmt", "yuv420p",
                        temp_hook_path
                    ]

                    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                    if r.returncode == 0 and os.path.exists(temp_hook_path) and os.path.getsize(temp_hook_path) > 1000:
                        os.replace(temp_hook_path, norm_path)
                        print(f"[VideoEngine] ✓ Đã áp dụng thành công hiệu ứng Hook lên Cảnh 1.", flush=True)
                    else:
                        print(f"[VideoEngine] ⚠ Lỗi áp dụng hiệu ứng Hook (FFmpeg): {r.stderr[-300:]}", flush=True)
                except Exception as e:
                    print(f"[VideoEngine] ⚠ Lỗi áp dụng hiệu ứng Hook: {e}", flush=True)

            normalized.append({"path": norm_path, "duration": actual_dur, "scene_id": scene_id})
            print(f"[VideoEngine] ✓ norm_{i:03d}.mp4 — {actual_dur:.1f}s  ({scene_id})", flush=True)

        # ── Phase 2: Concatenate with xfade transitions ───────────────────────
        if len(normalized) == 1:
            # Single clip — just copy (possibly with audio mix)
            single = normalized[0]["path"]
            cmd = ["ffmpeg", "-y", "-i", single]
            if voiceover_path and os.path.exists(voiceover_path):
                cmd += ["-i", voiceover_path,
                        "-filter_complex", "[0:v]copy[vout];[1:a]anull[aout]",
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
                audio_filter = f";[{vo_idx}:a]anull[aout]"
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
            f"zoompan=z='if(lte(zoom,1.0),1.0,zoom-0.0005)':d={int(duration*30)}:"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={w}x{h}:fps=30,"
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
        # Delete existing placeholder file (might be corrupted or dummy from previous failed runs)
        if placeholder_path.exists():
            try:
                placeholder_path.unlink()
            except Exception:
                pass

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
        except Exception:
            pass

        # Fail-safe: try generating a simple color-only placeholder if drawtext failed
        if not placeholder_path.exists():
            print(f"[VideoEngine] ⚠ Drawtext placeholder failed, falling back to simple color placeholder", flush=True)
            simple_cmd = [
                "ffmpeg", "-y",
                "-f", "lavfi", "-i", f"color=c={c1}:s={width}x{height}:d={duration}",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-t", str(duration),
                str(placeholder_path),
            ]
            try:
                subprocess.run(simple_cmd, capture_output=True, timeout=30)
            except Exception:
                pass

        # Last resort: write dummy file if both failed
        if not placeholder_path.exists():
            print(f"[VideoEngine] ⚠ FFmpeg placeholder failed entirely, writing dummy file", flush=True)
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

    def _convert_srt_to_ass(self, srt_path: str, ass_path: str, is_personal: bool = True) -> bool:
        try:
            import re
            with open(srt_path, "r", encoding="utf-8") as f:
                content = f.read()

            def clean_timestamp(ts: str) -> str:
                ts = ts.replace(",", ".")
                parts = ts.split(".")
                time_part = parts[0]
                ms_part = parts[1] if len(parts) > 1 else "000"
                centis = ms_part[:2]
                if time_part.startswith("0") and len(time_part) > 5:
                    time_part = time_part[1:]
                return f"{time_part}.{centis}"

            # SRT regex pattern to extract indices, timestamps, and texts
            pattern = re.compile(
                r"(\d+)\n"
                r"(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\n"
                r"((?:.|\n)*?)(?=\n\d+\n|\Z)",
                re.MULTILINE
            )
            matches = pattern.findall(content)
            
            dialogues = []
            for m in matches:
                start = clean_timestamp(m[1])
                end = clean_timestamp(m[2])
                # ASS uses \N for newline, strip outer spaces/newlines
                text = m[3].strip().replace("\n", "\\N")
                dialogues.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}")

            if is_personal:
                font_size = 52       # Font size a bit smaller
                margin_v = 280       # higher up, safe from TikTok controls but clearly at bottom
                outline = 4.0
                shadow = 1.0
            else:
                font_size = 64
                margin_v = 150       # lower down
                outline = 3.0
                shadow = 0.0

            ass_content = (
                "[Script Info]\n"
                "ScriptType: v4.00+\n"
                "PlayResX: 1080\n"
                "PlayResY: 1920\n\n"
                "[V4+ Styles]\n"
                "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
                f"Style: Default,Arial,{font_size},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,{outline},{shadow},2,80,80,{margin_v},1\n\n"
                "[Events]\n"
                "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
            ) + "\n".join(dialogues)

            with open(ass_path, "w", encoding="utf-8") as f:
                f.write(ass_content)
            return True
        except Exception as e:
            print(f"[VideoEngine] ⚠ Lỗi chuyển đổi SRT sang ASS: {e}", flush=True)
            return False

    def add_subtitles(self, video_path: str, subtitle_path: str, video_type: str = "personal") -> str:
        output_path = video_path.replace(".mp4", "_subtitled.mp4")
        temp_ass_path = subtitle_path.replace(".srt", "_temp.ass")

        # Convert SRT to ASS to ensure correct scaling/margins relative to 1080x1920 canvas
        is_personal = (video_type == "personal")
        success = self._convert_srt_to_ass(subtitle_path, temp_ass_path, is_personal=is_personal)
        
        # Determine path to render
        render_path = temp_ass_path if success else subtitle_path
        safe_render = render_path.replace("\\", "/").replace(":", "\\:")

        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-vf", f"subtitles='{safe_render}'",
            "-c:a", "copy",
            output_path,
        ]
        try:
            subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return video_path  # Return original if subtitles fail
        finally:
            if success and os.path.exists(temp_ass_path):
                try:
                    os.remove(temp_ass_path)
                except Exception:
                    pass
        return output_path

