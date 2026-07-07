"""
list_review_render.py — Render video kiểu "list review" cho luồng nhân viên (mẫu nv1 / h.khng.gm2).

Style đã phân tích (data/edit_templates/nv1.json):
  intro talking-head + khung hook nhân viên  → các SPOT (mỗi quán: badge tên + điểm X/10 ở trên,
  2-4 clip b-roll, phụ đề auto-caption dưới)  → outro. Hard cut, nhịp nhanh.

Spec đầu vào:
{
  "job_id": "nv1_demo",
  "hook_style": "hook_red",
  "voice_provider": "gtts", "voice_id": "",
  "intro": {"title": "Ăn gì ở Đà Lạt", "vo": "...", "clips": ["a.mp4", ...]},
  "spots": [{"name": "Cơm tấm Thủ", "rating": "8.5", "vo": "...", "clips": [...]}, ...],
  "outro": {"vo": "...", "clips": [...]}
}
Trả về path mp4 1080x1920.
"""
from __future__ import annotations

import os
import sys
import json
import math
import shutil
import tempfile
import subprocess
import unicodedata
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
FONT_DIR = ROOT / "assets" / "fonts"
OUTPUT_DIR = ROOT / "output" / "renders"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

W, H = 1080, 1920
FPS = 30

SCRIPT_FONT = FONT_DIR / "DancingScript-VF.ttf"      # tên quán (viết tay)
CAPTION_FONT = FONT_DIR / "BeVietnamPro-Bold-full.ttf"  # điểm + phụ đề


def _ffprobe_dur(path: str) -> float:
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                            "-of", "default=noprint_wrappers=1:nokey=1", path],
                           capture_output=True, text=True, timeout=20)
        return float(r.stdout.strip())
    except Exception:
        return 0.0


def _font(path: Path, size: int):
    try:
        return ImageFont.truetype(str(path), size)
    except Exception:
        return ImageFont.load_default()


# ─────────────────────────────────────────────────────────────────────────────
# Overlay PNGs (PIL — không phụ thuộc fontconfig)
# ─────────────────────────────────────────────────────────────────────────────

def _draw_text_stroke(d, xy, text, font, fill, stroke=4, stroke_fill=(0, 0, 0, 255), anchor=None):
    d.text(xy, text, font=font, fill=fill, stroke_width=stroke, stroke_fill=stroke_fill, anchor=anchor)


def build_spot_badge(name: str, rating: str, out_path: str, address: str = "") -> str:
    """Badge tên quán (viết tay) + pill điểm X/10, canh trái-trên ~14% từ đỉnh.
    Có địa chỉ → vẽ dòng nhỏ ngay dưới tên (giúp seeding)."""
    name = unicodedata.normalize("NFC", (name or "").strip())
    rating = (rating or "").strip()
    address = unicodedata.normalize("NFC", (address or "").strip())
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(canvas)

    x0, y0 = 60, int(H * 0.12)
    rf = _font(CAPTION_FONT, 56)
    label = f"{rating}/10" if rating else ""
    rb = d.textbbox((0, 0), label, font=rf) if label else (0, 0, 0, 0)
    rw, rh = rb[2] - rb[0], rb[3] - rb[1]
    pad = 22
    pill_w = (rw + pad * 2 + 26) if label else 0          # bề rộng pill điểm + khoảng cách
    avail = (W - 60) - x0 - pill_w                          # chỗ còn lại cho tên

    # auto-shrink font tên để tên + pill luôn vừa khung
    nsize = 96
    while nsize >= 50:
        nf = _font(SCRIPT_FONT, nsize)
        nb = d.textbbox((x0, y0), name, font=nf, stroke_width=6)
        if (nb[2] - nb[0]) <= avail:
            break
        nsize -= 4
    _draw_text_stroke(d, (x0, y0), name, nf, (255, 255, 255, 255), stroke=6)

    if rating:
        nb = d.textbbox((x0, y0), name, font=nf, stroke_width=6)
        px0, py0 = nb[2] + 26, y0 + 18
        px1, py1 = px0 + rw + pad * 2, py0 + rh + pad * 2
        d.rounded_rectangle([px0, py0, px1, py1], radius=26, fill=(228, 74, 96, 235))
        d.text((px0 + pad, py0 + pad - rb[1]), label, font=rf, fill=(255, 255, 255, 255))

    if address:
        nb = d.textbbox((x0, y0), name, font=nf, stroke_width=6)
        af = _font(CAPTION_FONT, 34)
        _draw_text_stroke(d, (x0 + 4, nb[3] + 6), f"📍 {address}", af, (255, 255, 255, 255), stroke=4)

    canvas.save(out_path)
    return out_path


def build_intro_overlay(hook_style: str, title: str, subtitle: str, out_path: str) -> str:
    """Khung hook nhân viên cho cảnh mở đầu (tái dùng build_hook)."""
    try:
        from tools.hook_overlay import build_hook
        return build_hook(hook_style, title, subtitle, out_path)
    except Exception as e:
        print(f"[list_review] build_hook lỗi ({e}) → bỏ overlay intro", file=sys.stderr)
        Image.new("RGBA", (W, H), (0, 0, 0, 0)).save(out_path)
        return out_path


# ─────────────────────────────────────────────────────────────────────────────
# HTML overlay engine (nv2/nv3) — render TĨNH qua Chromium ở subprocess, fade do FFmpeg
# ─────────────────────────────────────────────────────────────────────────────

def _hook_lines(seg: dict) -> list[str]:
    """Lấy các dòng chữ hook từ seg (hook_lines, hoặc title tách theo \\n / |)."""
    hl = seg.get("hook_lines")
    if isinstance(hl, list) and hl:
        return [str(x).strip() for x in hl if str(x).strip()]
    raw = (seg.get("title") or "").replace("|", "\n")
    return [ln.strip() for ln in raw.split("\n") if ln.strip()]


def _body_lines(seg: dict) -> list[str]:
    """Lấy các dòng chữ on-screen của 1 tip (body: list hoặc string tách \\n)."""
    b = seg.get("body")
    if isinstance(b, list):
        return [str(x).strip() for x in b if str(x).strip()]
    raw = (b if isinstance(b, str) else (seg.get("caption") or ""))
    return [ln.strip() for ln in str(raw).replace("|", "\n").split("\n") if ln.strip()]


def render_html_overlays(spec: dict, work: Path, style: str) -> dict:
    """Batch render mọi overlay HTML của 1 video trong 1 lần mở browser.
    Trả {scene_key: png_path}; scene_key = 'intro' | 'spot{i}' | 'outro'."""
    jobs, mapping = [], {}

    def _add(key, job):
        out = str(work / f"htmlov_{key}.png")
        job["out"] = out
        jobs.append(job); mapping[key] = out

    if spec.get("intro"):
        _add("intro", {"kind": "hook", "style": style, "lines": _hook_lines(spec["intro"])})
    for i, sp in enumerate(spec.get("spots", []), start=1):
        _add(f"spot{i}", {"kind": "section", "style": style,
                          "title": (sp.get("section_title") or "").strip(),
                          "emoji": (sp.get("emoji") or "").strip(),
                          "align": sp.get("align", "left"), "no_pill": bool(sp.get("no_pill")),
                          "body": _body_lines(sp)})
    outro = spec.get("outro") or {}
    if outro and (outro.get("section_title") or outro.get("body")):
        _add("outro", {"kind": "section", "style": style,
                       "title": (outro.get("section_title") or "").strip(),
                       "emoji": (outro.get("emoji") or "").strip(),
                       "body": _body_lines(outro)})

    if not jobs:
        return {}
    jobs_json = work / "html_jobs.json"
    jobs_json.write_text(json.dumps(jobs, ensure_ascii=False), encoding="utf-8")
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, "-m", "tools.html_overlay", str(jobs_json)],
                       capture_output=True, text=True, cwd=str(ROOT), env=env)
    if r.returncode != 0:
        raise RuntimeError(f"html_overlay lỗi:\n{r.stderr[-800:]}")
    return mapping


# ─────────────────────────────────────────────────────────────────────────────
# Caption ASS (auto-caption dưới đáy, chia chunk đều theo thời lượng)
# ─────────────────────────────────────────────────────────────────────────────

def _chunk_caption(text: str, words_per_line: int = 7) -> list[str]:
    words = unicodedata.normalize("NFC", (text or "").strip()).split()
    lines = []
    for i in range(0, len(words), words_per_line):
        lines.append(" ".join(words[i:i + words_per_line]))
    return [l for l in lines if l]


def build_caption_png(text: str, out_path: str, max_w: int = 980):
    """1 dòng phụ đề → PNG trong suốt, chữ trắng viền đen, canh giữa đáy (~82% H)."""
    text = unicodedata.normalize("NFC", (text or "").strip())
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(canvas)
    size = 62
    while size >= 40:
        f = _font(CAPTION_FONT, size)
        b = d.textbbox((0, 0), text, font=f, stroke_width=6)
        if b[2] - b[0] <= max_w:
            break
        size -= 4
    f = _font(CAPTION_FONT, size)
    cx, y = W // 2, int(H * 0.80)
    d.text((cx, y), text, font=f, fill=(255, 255, 255, 255),
           stroke_width=6, stroke_fill=(0, 0, 0, 255), anchor="ms")
    canvas.save(out_path)
    return out_path


# ─────────────────────────────────────────────────────────────────────────────
# FFmpeg helpers
# ─────────────────────────────────────────────────────────────────────────────

def _run(cmd, cwd=None):
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg lỗi: {' '.join(str(c) for c in cmd[:6])}...\n{r.stderr[-800:]}")
    return r


def _normalize(src: str, dst: str, max_dur: float | None = None):
    """Scale-cover về 1080x1920, 30fps, bỏ audio. max_dur: chỉ encode tối đa n giây
    (source nặng/dài không bị transcode toàn bộ khi chỉ dùng vài giây)."""
    cmd = ["ffmpeg", "-y", "-i", src,
           "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS}",
           "-an", "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p"]
    if max_dur and max_dur > 0:
        cmd += ["-t", f"{max_dur:.2f}"]
    cmd += [dst]
    _run(cmd)


def _concat_clips(norm_paths: list[str], dst: str, work: Path):
    if len(norm_paths) == 1:
        shutil.copy2(norm_paths[0], dst); return
    lst = work / "concat.txt"
    lst.write_text("".join(f"file '{Path(p).name}'\n" for p in norm_paths), encoding="utf-8")
    _run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "concat.txt",
          "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", Path(dst).name], cwd=str(work))


def _concat_with_xfade(segs: list[str], out_path: Path, work: Path,
                       transition: str = "slideleft", d: float = 0.4):
    """Ghép các segment bằng xfade (hình) + acrossfade (tiếng) — chuyển cảnh kiểu swoosh.
    Cả A/V đều rút lại d giây mỗi mối nối nên không lệch tiếng-hình."""
    n = len(segs)
    if n == 1:
        _run(["ffmpeg", "-y", "-i", Path(segs[0]).name,
              "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
              "-c:a", "aac", "-b:a", "160k", str(out_path)], cwd=str(work))
        return
    durs = [max(0.3, _ffprobe_dur(p)) for p in segs]
    inputs = []
    for p in segs:
        inputs += ["-i", Path(p).name]
    parts = [f"[{i}:v]setpts=PTS-STARTPTS[v{i}]" for i in range(n)]
    parts += [f"[{i}:a]asetpts=PTS-STARTPTS[a{i}]" for i in range(n)]
    fc = ";".join(parts)
    prev, off = "v0", 0.0
    for i in range(n - 1):
        off += durs[i] - d
        out = f"vx{i}"
        fc += f";[{prev}][v{i+1}]xfade=transition={transition}:duration={d:.3f}:offset={off:.3f}[{out}]"
        prev = out
    aprev = "a0"
    for i in range(n - 1):
        out = f"ax{i}"
        fc += f";[{aprev}][a{i+1}]acrossfade=d={d:.3f}[{out}]"
        aprev = out
    _run(["ffmpeg", "-y", *inputs, "-filter_complex", fc,
          "-map", f"[{prev}]", "-map", f"[{aprev}]",
          "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
          "-c:a", "aac", "-b:a", "160k", str(out_path)], cwd=str(work))


def _render_segment(kind: str, seg: dict, idx: int, work: Path,
                    hook_style: str, voice_provider: str, voice_id: str,
                    html_png: str | None = None, badge_mode: str = "full") -> str | None:
    from tools.voice_generator import VoiceGenerator

    vo_text = (seg.get("vo") or "").strip()
    if not vo_text:
        return None

    # 1) Voiceover
    vg = VoiceGenerator(provider=voice_provider or "gtts")
    vo_path = vg.generate_voice(text=vo_text, voice_id=voice_id or "",
                                output_name=f"lr_{work.name}_{kind}{idx}", speed=1.08)
    if not vo_path or not os.path.exists(vo_path):
        print(f"[list_review] VO lỗi segment {kind}{idx}", file=sys.stderr)
        return None
    dur = max(1.2, _ffprobe_dur(vo_path))

    # 2) Visual base (concat clips → loop/trim về đúng dur)
    clips = [c for c in (seg.get("clips") or []) if c and os.path.exists(c)]
    base = work / f"base_{kind}{idx}.mp4"
    if clips:
        norm = []
        for j, c in enumerate(clips):
            n = work / f"n_{kind}{idx}_{j}.mp4"
            _normalize(c, str(n), max_dur=dur + 0.5); norm.append(str(n))
        cat = work / f"cat_{kind}{idx}.mp4"
        _concat_clips(norm, str(cat), work)
        _run(["ffmpeg", "-y", "-stream_loop", "-1", "-i", str(cat), "-t", f"{dur:.2f}",
              "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-an", str(base)])
    else:
        _run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c=0x10243a:s={W}x{H}:r={FPS}",
              "-t", f"{dur:.2f}", "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", str(base)])

    # 3) Overlay PNG. Engine HTML (nv2/nv3): dùng PNG đã render sẵn; PIL: badge/hook như cũ.
    overlay = work / f"ov_{kind}{idx}.png"
    if html_png and os.path.exists(html_png):
        shutil.copy2(html_png, str(overlay))
    elif kind == "spot" and badge_mode != "none":
        build_spot_badge(seg.get("name", ""), seg.get("rating", ""), str(overlay), seg.get("address", ""))
    elif kind == "intro":
        build_intro_overlay(hook_style, seg.get("title", ""), "", str(overlay))
    else:
        # badge_mode 'none' (nv4 montage) hoặc kind không xác định → overlay trong suốt
        Image.new("RGBA", (W, H), (0, 0, 0, 0)).save(str(overlay))

    # 4) Caption đáy theo từng dòng (chỉ engine PIL). Engine HTML: chữ on-screen đã nằm trong overlay.
    cap_pngs = []
    if not html_png:
        cap_lines = _chunk_caption(vo_text)
        if cap_lines:
            per = dur / len(cap_lines)
            for li, ln in enumerate(cap_lines):
                p = work / f"cap_{kind}{idx}_{li}.png"
                build_caption_png(ln, str(p))
                cap_pngs.append((p.name, li * per, (li + 1) * per))

    # 5) Gộp base + overlay (HTML: fade-in) + caption động + audio → segment hoàn chỉnh
    out = work / f"seg_{idx:03d}.mp4"
    if html_png:
        # PNG cần -loop 1 để thành stream liên tục, fade alpha mới có frame qua thời gian
        inputs = ["-i", base.name, "-loop", "1", "-framerate", str(FPS), "-i", overlay.name]
        fc = "[1:v]format=rgba,fade=t=in:st=0:d=0.30:alpha=1[ov];[0:v][ov]overlay=0:0:shortest=1[v0]"
    else:
        inputs = ["-i", base.name, "-i", overlay.name]
        fc = "[0:v][1:v]overlay=0:0[v0]"
    for nm, _, _ in cap_pngs:
        inputs += ["-i", nm]
    last = "v0"
    for k, (_, st, en) in enumerate(cap_pngs):
        nxt = f"v{k+1}"
        fc += f";[{last}][{k+2}:v]overlay=0:0:enable='between(t,{st:.2f},{en:.2f})'[{nxt}]"
        last = nxt
    audio_idx = 2 + len(cap_pngs)
    _run(["ffmpeg", "-y", *inputs, "-i", vo_path,
          "-filter_complex", fc,
          "-map", f"[{last}]", "-map", f"{audio_idx}:a", "-t", f"{dur:.2f}",
          "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
          "-c:a", "aac", "-shortest", out.name], cwd=str(work))
    return str(out)


def render_list_review(spec: dict) -> dict:
    job_id = spec.get("job_id", "lr_demo")
    hook_style = spec.get("hook_style", "hook_red")
    vp = spec.get("voice_provider", "gtts")
    vid = spec.get("voice_id", "")

    engine = (spec.get("overlay_engine") or "pil").lower()
    style = (spec.get("style") or "").lower()
    badge_mode = (spec.get("badge_mode") or "full").lower()
    transition = (spec.get("transition") or "none").lower()

    work = Path(tempfile.mkdtemp(prefix=f"lr_{job_id}_"))
    segs: list[str] = []
    try:
        # Engine HTML (nv2/nv3): render trước toàn bộ overlay trong 1 lần mở browser.
        ov = render_html_overlays(spec, work, style) if engine == "html" and style else {}

        if spec.get("intro"):
            s = _render_segment("intro", spec["intro"], 0, work, hook_style, vp, vid,
                                html_png=ov.get("intro"), badge_mode=badge_mode)
            if s: segs.append(s)
        for i, spot in enumerate(spec.get("spots", []), start=1):
            s = _render_segment("spot", spot, i, work, hook_style, vp, vid,
                                html_png=ov.get(f"spot{i}"), badge_mode=badge_mode)
            if s: segs.append(s)
        if spec.get("outro"):
            s = _render_segment("outro", spec["outro"], 99, work, hook_style, vp, vid,
                                html_png=ov.get("outro"), badge_mode=badge_mode)
            if s: segs.append(s)

        if not segs:
            return {"success": False, "error": "Không render được segment nào (thiếu VO?)."}

        out_path = OUTPUT_DIR / f"listreview_{job_id}.mp4"
        if len(segs) >= 2:
            # Chuyển cảnh fade mượt cho tất cả nv (thay vì cắt cứng).
            _concat_with_xfade(segs, out_path, work, transition="fade", d=0.3)
        else:
            _run(["ffmpeg", "-y", "-i", Path(segs[0]).name,
                  "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
                  "-c:a", "aac", "-b:a", "160k", str(out_path)], cwd=str(work))

        return {"success": True, "video_path": str(out_path.resolve()),
                "segments": len(segs), "duration": _ffprobe_dur(str(out_path))}
    finally:
        # giữ work dir nếu debug; xoá để gọn
        shutil.rmtree(work, ignore_errors=True)
