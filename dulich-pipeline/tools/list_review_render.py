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


def _word_timings(vo_path: str, vo_text: str) -> list[dict] | None:
    """Timing từng từ của file VO để phụ đề khớp giọng.
    1) Edge TTS đã ghi sẵn <vo>.words.json. 2) gtts/vbee → Whisper OpenAI (word timestamps).
    Không có → None (fallback chia đều)."""
    import json as _json
    wp = Path(vo_path).with_suffix(".words.json")
    if wp.exists():
        try:
            words = _json.loads(wp.read_text(encoding="utf-8"))
            if words:
                return words
        except Exception:
            pass
    key = os.getenv("OPENAI_API_KEY")
    if not key or key.startswith("your-"):
        return None
    try:
        import requests
        with open(vo_path, "rb") as f:
            r = requests.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {key}"},
                files={"file": (Path(vo_path).name, f, "audio/mpeg")},
                data={"model": "whisper-1", "language": "vi",
                      "response_format": "verbose_json",
                      "timestamp_granularities[]": "word",
                      # prompt = kịch bản gốc → Whisper bám đúng chữ
                      "prompt": (vo_text or "")[:800]},
                timeout=120)
        if r.status_code != 200:
            print(f"[list_review] whisper {r.status_code}: {r.text[:200]}", file=sys.stderr)
            return None
        words = [{"word": w.get("word", ""), "start": float(w.get("start", 0)), "end": float(w.get("end", 0))}
                 for w in (r.json().get("words") or [])]
        if words:
            wp.write_text(_json.dumps(words, ensure_ascii=False), encoding="utf-8")  # cache
            return words
    except Exception as e:
        print(f"[list_review] whisper lỗi: {e}", file=sys.stderr)
    return None


_END_PUNCT = (".", "!", "?", "…", ":", ";")
_MID_PUNCT = (",",)


def _group_words(words: list[dict], dur: float,
                 min_words: int = 3, max_words: int = 5,
                 pause: float = 0.30, glue: float = 0.08) -> list[tuple[str, float, float]]:
    """Nhóm từ thành cue 3-6 chữ, cắt HỢP LÝ: ưu tiên sau dấu chấm/phẩy (từ đã được
    gắn dấu câu từ kịch bản gốc), rồi tới khoảng nghỉ của giọng; không xé cụm dính
    liền (vd 'Đà Lạt'). Cue hiện đúng lúc đọc, không lấn câu sau."""
    cues, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        nxt = words[i + 1] if i + 1 < len(words) else None
        gap = (nxt["start"] - w["end"]) if nxt else 999.0
        tok = (w.get("word") or "").strip()
        end_p = tok.endswith(_END_PUNCT)
        mid_p = tok.endswith(_MID_PUNCT)
        cut = (
            nxt is None
            or end_p                                            # hết câu → cắt
            or (mid_p and len(cur) >= min_words)                # sau dấu phẩy (đủ 3 chữ)
            or (gap >= pause and len(cur) >= min_words)         # nghỉ giọng rõ
            or (len(cur) >= max_words and gap >= glue)          # đủ dài + không dính cụm
        )
        over = len(cur) >= max_words + 3
        if cut or over:
            carry = []
            if over and not cut and nxt is not None:
                # buộc cắt nhưng tránh xé cụm: lùi về khoảng hở gần nhất trong cue
                for k in range(len(cur) - 1, 0, -1):
                    if (cur[k]["start"] - cur[k - 1]["end"]) >= glue:
                        carry = cur[k:]; cur = cur[:k]
                        break
            text = " ".join(x["word"].strip() for x in cur if x["word"].strip())
            st = float(cur[0]["start"])
            en = min(float(cur[-1]["end"]) + 0.25, dur)   # đệm nhẹ
            nxt_start = float(carry[0]["start"]) if carry else (float(nxt["start"]) if nxt else None)
            if nxt_start is not None:
                en = min(en, nxt_start)
            if text:
                cues.append((text, st, max(en, st + 0.35)))
            cur = carry
    return cues


def _valid_timings(words: list[dict], vo_text: str, dur: float) -> bool:
    """Chặn Whisper 'bịa' (hallucination): timing phải phủ phần lớn audio và
    số từ phải gần với kịch bản."""
    if not words:
        return False
    # Phủ audio: từ đầu tiên phải gần đầu file, từ cuối gần cuối file (Whisper sót
    # 1 câu đầu/cuối → lệch → loại, dùng fallback theo câu cho khớp giọng).
    first_start = float(words[0]["start"])
    last_end = float(words[-1]["end"])
    if first_start > 1.2:                       # bỏ sót phần đầu
        return False
    if (last_end / max(dur, 0.1)) < 0.75:       # bỏ sót phần cuối
        return False
    if (last_end - first_start) / max(dur, 0.1) < 0.6:
        return False
    if vo_text:
        expect = max(1, len(vo_text.split()))
        if len(words) < 0.75 * expect:          # số từ phải gần kịch bản (siết 0.5→0.75)
            return False
    return True


def _semantic_lines(vo_text: str, vo_path: str = "") -> list[str] | None:
    """AI chia kịch bản thành các dòng phụ đề THEO CỤM NGHĨA (3-8 từ) — quan trọng nghĩa
    hơn số từ. Giữ nguyên 100% từ ngữ. Cache cạnh file VO. Lỗi/thiếu key → None."""
    key = os.getenv("OPENROUTER_KEY") or os.getenv("OPENROUTER_API_KEY")
    if not key or not (vo_text or "").strip():
        return None
    import json as _json
    cache = Path(vo_path).with_suffix(".lines.json") if vo_path else None
    if cache and cache.exists():
        try:
            lines = _json.loads(cache.read_text(encoding="utf-8"))
            if lines:
                return lines
        except Exception:
            pass
    try:
        import requests
        r = requests.post("https://openrouter.ai/api/v1/chat/completions", timeout=45,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": "openai/gpt-4o-mini", "temperature": 0,
                  "response_format": {"type": "json_object"},
                  "messages": [
                      {"role": "system", "content":
                       "Chia câu tiếng Việt thành các dòng phụ đề ngắn. LUẬT: mỗi dòng là 1 CỤM CÓ NGHĨA "
                       "trọn vẹn (ưu tiên nghĩa hơn số từ), thường 3-8 từ; cắt tại ranh giới cụm "
                       "(sau dấu câu, giữa chủ ngữ/vị ngữ, trước liên từ); TUYỆT ĐỐI không thêm/bớt/"
                       "sửa/đảo bất kỳ từ nào — ghép lại phải y hệt bản gốc. "
                       'Trả DUY NHẤT JSON: {"lines": ["...", "..."]}'},
                      {"role": "user", "content": vo_text.strip()}]})
        if r.status_code != 200:
            return None
        lines = _json.loads(r.json()["choices"][0]["message"]["content"]).get("lines") or []
        lines = [str(l).strip() for l in lines if str(l).strip()]
        # bắt buộc giữ nguyên từ ngữ: ghép lại phải khớp bản gốc (so theo token)
        if lines and " ".join(" ".join(lines).split()) == " ".join(vo_text.split()):
            if cache:
                try:
                    cache.write_text(_json.dumps(lines, ensure_ascii=False), encoding="utf-8")
                except Exception:
                    pass
            return lines
    except Exception as e:
        print(f"[list_review] semantic lines lỗi: {e}", file=sys.stderr)
    return None


def _cues_from_lines(lines: list[str], words: list[dict], dur: float) -> list[tuple[str, float, float]]:
    """Map các dòng (đã chia theo nghĩa, tổng token khớp kịch bản) vào timing từng từ."""
    cues, i = [], 0
    for ln in lines:
        n = len(ln.split())
        seg = words[i:i + n]
        i += n
        if not seg:
            break
        st = float(seg[0]["start"])
        en = min(float(seg[-1]["end"]) + 0.25, dur)
        if i < len(words):
            en = min(en, float(words[i]["start"]))
        cues.append((ln, st, max(en, st + 0.35)))
    return cues


def _no_overlap(cues: list[tuple[str, float, float]],
                gap: float = 0.06) -> list[tuple[str, float, float]]:
    """ffmpeg enable='between(t,a,b)' tính CẢ 2 đầu mút → cue trước phải kết thúc
    TRƯỚC cue sau 1 khe nhỏ, không thì 2 dòng chồng dính nhau tại điểm giao."""
    out = []
    for i, (txt, st, en) in enumerate(cues):
        if i + 1 < len(cues):
            en = min(en, cues[i + 1][1] - gap)
        out.append((txt, st, max(en, st + 0.2)))
    return out


def _timed_cues(vo_path: str, vo_text: str, dur: float) -> list[tuple[str, float, float]]:
    """Cue phụ đề (text, start, end). Ưu tiên timing thật (words.json/Whisper);
    fallback chia đều như cũ."""
    words = _word_timings(vo_path, vo_text)
    if words and not _valid_timings(words, vo_text, dur):
        # Whisper bịa/thiếu (vd đoạn nhạc) → bỏ cache hỏng, dùng fallback
        print(f"[list_review] words không khớp audio ({Path(vo_path).name}) → chia đều", file=sys.stderr)
        try:
            Path(vo_path).with_suffix(".words.json").unlink(missing_ok=True)
        except Exception:
            pass
        words = None
    if words:
        try:
            if vo_text:
                # gắn lại dấu câu từ kịch bản gốc để cắt sau dấu phẩy/chấm
                try:
                    from agents.subtitle_agent import align_words_with_punctuation
                    words = align_words_with_punctuation(words, vo_text) or words
                except Exception:
                    pass
                # AI chia dòng theo CỤM NGHĨA — chậm (+5-10s/cảnh vì thêm 1 call AI).
                # Mặc định TẮT (cắt theo dấu câu đủ tốt); bật lại: SUBTITLE_SEMANTIC=1
                if (os.getenv("SUBTITLE_SEMANTIC", "0") == "1"
                        and len(words) == len(vo_text.split())):
                    lines = _semantic_lines(vo_text, vo_path)
                    if lines:
                        out = _cues_from_lines(lines, words, dur)
                        if out:
                            return _no_overlap(out)
            out = _group_words(words, dur)
            if out:
                return _no_overlap(out)
        except Exception as e:
            print(f"[list_review] cue lỗi ({e}) → chia theo câu", file=sys.stderr)
    # Fallback KHÔNG dùng Whisper: chia theo CÂU, cấp thời lượng tỉ lệ số ký tự
    # (Vbee đọc đều → bám giọng tốt hơn nhiều so với chia đều theo dòng).
    return _no_overlap(_proportional_cues(vo_text, dur))


def _proportional_cues(vo_text: str, dur: float) -> list[tuple[str, float, float]]:
    """Chia câu → cue 3-5 chữ, phân bổ thời gian theo tỉ lệ ký tự trên tổng thời lượng."""
    import re as _re
    text = unicodedata.normalize("NFC", (vo_text or "").strip())
    if not text or dur <= 0:
        return []
    sents = [s.strip() for s in _re.split(r"(?<=[\.\!\?…])\s+|\n+", text) if s.strip()]
    if not sents:
        sents = [text]
    total = sum(len(s) for s in sents) or 1
    cues: list[tuple[str, float, float]] = []
    t = 0.0
    for s in sents:
        seg = dur * (len(s) / total)
        s0, s1 = t, min(dur, t + seg)
        t = s1
        # trong câu: gom 3-5 chữ 1 cue, chia thời gian câu theo số chữ mỗi cue
        words = s.split()
        chunks, i = [], 0
        while i < len(words):
            chunks.append(words[i:i + 5]); i += 5
        cw = sum(len(c) for c in chunks) or 1
        ct = s0
        for c in chunks:
            frac = len(c) / cw
            c0, c1 = ct, min(s1, ct + seg * frac)
            ct = c1
            cues.append((" ".join(c), c0, max(c1, c0 + 0.3)))
    return cues


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

def _run(cmd, cwd=None, timeout=240):
    # KHÔNG ép -threads: decode 4K HEVC cần full thread (ép 2 làm chậm gấp đôi trên VPS);
    # ffmpeg + OS tự chia CPU khi nhiều segment chạy song song.
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        print(f"[list_review] ffmpeg TIMEOUT ({timeout}s): {' '.join(str(c) for c in cmd)}", file=sys.stderr)
        raise RuntimeError(f"ffmpeg quá thời gian ({timeout}s) — có thể do source lỗi/quá nặng.") from e
    if r.returncode != 0:
        print(f"[list_review] ffmpeg lỗi (rc={r.returncode}): {' '.join(str(c) for c in cmd)}\n{r.stderr}", file=sys.stderr)
        raise RuntimeError(f"ffmpeg lỗi: {' '.join(str(c) for c in cmd[:6])}...\n{r.stderr[-1500:]}")
    return r


def _normalize(src: str, dst: str, max_dur: float | None = None):
    """Scale-cover về 1080x1920, 30fps, bỏ audio. max_dur: chỉ encode tối đa n giây
    (source nặng/dài không bị transcode toàn bộ khi chỉ dùng vài giây).
    File trung gian → preset ultrafast (chất lượng cuối do bước encode sau quyết)."""
    cmd = ["ffmpeg", "-y", "-i", src,
           "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS}",
           "-an", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "20", "-pix_fmt", "yuv420p"]
    if max_dur and max_dur > 0:
        cmd += ["-t", f"{max_dur:.2f}"]
    cmd += [dst]
    _run(cmd)


def _concat_clips(norm_paths: list[str], dst: str, work: Path):
    if len(norm_paths) == 1:
        shutil.copy2(norm_paths[0], dst); return
    # tên list file theo dst — các segment chạy SONG SONG không đè nhau
    lst = work / f"concat_{Path(dst).stem}.txt"
    lst.write_text("".join(f"file '{Path(p).name}'\n" for p in norm_paths), encoding="utf-8")
    _run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst.name,
          "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", Path(dst).name], cwd=str(work))


def _concat_with_xfade(segs: list[str], out_path: Path, work: Path,
                       transition: str = "slideleft", d: float = 0.4):
    """Ghép các segment bằng xfade (hình) + acrossfade (tiếng) — chuyển cảnh kiểu swoosh.
    Cả A/V đều rút lại d giây mỗi mối nối nên không lệch tiếng-hình."""
    n = len(segs)
    if n == 1:
        _run(["ffmpeg", "-y", "-i", Path(segs[0]).name,
              "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
              "-movflags", "+faststart",   # moov đầu file → phone/stream phát ngay
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
          "-movflags", "+faststart",   # moov đầu file → phone/stream phát ngay
          "-c:a", "aac", "-b:a", "160k", str(out_path)], cwd=str(work))


def _render_segment(kind: str, seg: dict, idx: int, work: Path,
                    hook_style: str, voice_provider: str, voice_id: str,
                    html_png: str | None = None, badge_mode: str = "full") -> str | None:
    from tools.voice_generator import VoiceGenerator

    vo_text = (seg.get("vo") or "").strip()
    if not vo_text:
        return None

    import time as _pt
    _t0 = _pt.time()
    # 1) Voiceover
    vg = VoiceGenerator(provider=voice_provider or "gtts")
    vo_path = vg.generate_voice(text=vo_text, voice_id=voice_id or "",
                                output_name=f"lr_{work.name}_{kind}{idx}", speed=1.08)
    if not vo_path or not os.path.exists(vo_path):
        print(f"[list_review] VO lỗi segment {kind}{idx}", file=sys.stderr)
        return None
    dur = max(1.2, _ffprobe_dur(vo_path))
    print(f"[perf] {kind}{idx} VO: {_pt.time()-_t0:.1f}s", file=sys.stderr); _t1 = _pt.time()

    # 2) Visual base (concat clips → loop/trim về đúng dur)
    clips = [c for c in (seg.get("clips") or []) if c and os.path.exists(c)]
    base = work / f"base_{kind}{idx}.mp4"
    if len(clips) == 1 and _ffprobe_dur(clips[0]) >= dur:
        # 1 clip đủ dài → normalize + cắt đúng dur làm base LUÔN (bỏ 2 lần encode thừa)
        _normalize(clips[0], str(base), max_dur=dur)
        print(f"[perf] {kind}{idx} normalize(base 1-clip): {_pt.time()-_t1:.1f}s", file=sys.stderr); _t1 = _pt.time()
    elif clips:
        norm = []
        for j, c in enumerate(clips):
            n = work / f"n_{kind}{idx}_{j}.mp4"
            _normalize(c, str(n), max_dur=dur + 0.5); norm.append(str(n))
        print(f"[perf] {kind}{idx} normalize x{len(clips)}: {_pt.time()-_t1:.1f}s", file=sys.stderr); _t1 = _pt.time()
        cat = work / f"cat_{kind}{idx}.mp4"
        _concat_clips(norm, str(cat), work)
        _run(["ffmpeg", "-y", "-stream_loop", "-1", "-i", str(cat), "-t", f"{dur:.2f}",
              "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-an", str(base)])
        print(f"[perf] {kind}{idx} concat+loop: {_pt.time()-_t1:.1f}s", file=sys.stderr); _t1 = _pt.time()
    else:
        # KHÔNG có clip nguồn → nền navy (blue screen). Log rõ để biết cảnh nào thiếu footage.
        print(f"[list_review] ⚠ segment {kind}{idx} KHÔNG có clip nguồn → nền navy "
              f"(clips nhận vào: {seg.get('clips')})", file=sys.stderr)
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

    # 4) Caption đáy KHỚP GIỌNG: timing thật từ words.json (Edge) / Whisper OpenAI (gtts/vbee);
    #    fallback chia đều. Engine HTML: chữ on-screen đã nằm trong overlay.
    cap_pngs = []
    if not html_png:
        for li, (ln, st, en) in enumerate(_timed_cues(vo_path, vo_text, dur)):
            p = work / f"cap_{kind}{idx}_{li}.png"
            build_caption_png(ln, str(p))
            cap_pngs.append((p.name, st, en))
    print(f"[perf] {kind}{idx} subtitle(whisper+png): {_pt.time()-_t1:.1f}s", file=sys.stderr); _t1 = _pt.time()

    # 5) Gộp base + overlay (HTML: fade-in) + caption động + audio → segment hoàn chỉnh
    out = work / f"seg_{idx:03d}.mp4"
    # PNG tĩnh PHẢI '-loop 1 -framerate FPS' để thành stream liên tục suốt thời lượng segment —
    # thiếu cờ này, ffmpeg chỉ decode 1 frame rồi EOF; một số bản ffmpeg/điều kiện máy sẽ lỗi
    # filter graph (đặc biệt khi overlay có enable='between(...)' ở t>0) thay vì "giữ khung hình cuối".
    if html_png:
        inputs = ["-i", base.name, "-loop", "1", "-framerate", str(FPS), "-i", overlay.name]
        fc = "[1:v]format=rgba,fade=t=in:st=0:d=0.30:alpha=1[ov];[0:v][ov]overlay=0:0:shortest=1[v0]"
    else:
        inputs = ["-i", base.name, "-loop", "1", "-framerate", str(FPS), "-i", overlay.name]
        fc = "[0:v][1:v]overlay=0:0:shortest=1[v0]"
    for nm, _, _ in cap_pngs:
        inputs += ["-loop", "1", "-framerate", str(FPS), "-i", nm]
    last = "v0"
    for k, (_, st, en) in enumerate(cap_pngs):
        nxt = f"v{k+1}"
        fc += f";[{last}][{k+2}:v]overlay=0:0:shortest=1:enable='between(t,{st:.2f},{en:.2f})'[{nxt}]"
        last = nxt
    audio_idx = 2 + len(cap_pngs)
    _run(["ffmpeg", "-y", *inputs, "-i", vo_path,
          "-filter_complex", fc,
          "-map", f"[{last}]", "-map", f"{audio_idx}:a", "-t", f"{dur:.2f}",
          "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
          "-c:a", "aac", "-shortest", out.name], cwd=str(work))
    print(f"[perf] {kind}{idx} overlay+mux: {_pt.time()-_t1:.1f}s | segment total {_pt.time()-_t0:.1f}s", file=sys.stderr)
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

        # Render các segment SONG SONG (3 luồng) — phần lớn thời gian là chờ API
        # (Vbee/Whisper); file mỗi segment đều có suffix riêng nên không đụng nhau.
        tasks = []
        if spec.get("intro"):
            tasks.append(("intro", spec["intro"], 0, ov.get("intro")))
        for i, spot in enumerate(spec.get("spots", []), start=1):
            tasks.append(("spot", spot, i, ov.get(f"spot{i}")))
        if spec.get("outro"):
            tasks.append(("outro", spec["outro"], 99, ov.get("outro")))

        from concurrent.futures import ThreadPoolExecutor
        results: dict = {}
        with ThreadPoolExecutor(max_workers=min(3, max(1, len(tasks)))) as ex:
            futs = {ex.submit(_render_segment, kind, seg, idx, work, hook_style,
                              vp, vid, html_png=png, badge_mode=badge_mode): order
                    for order, (kind, seg, idx, png) in enumerate(tasks)}
            for f, order in futs.items():
                try:
                    results[order] = f.result()
                except Exception as e:
                    print(f"[list_review] segment {order} lỗi: {e}", file=sys.stderr)
                    results[order] = None
        segs = [results[o] for o in sorted(results) if results[o]]

        if not segs:
            return {"success": False, "error": "Không render được segment nào (thiếu VO?)."}

        out_path = OUTPUT_DIR / f"listreview_{job_id}.mp4"
        if len(segs) >= 2:
            # Chuyển cảnh fade mượt cho tất cả nv (thay vì cắt cứng).
            _concat_with_xfade(segs, out_path, work, transition="fade", d=0.3)
        else:
            _run(["ffmpeg", "-y", "-i", Path(segs[0]).name,
                  "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
                  "-movflags", "+faststart",
                  "-c:a", "aac", "-b:a", "160k", str(out_path)], cwd=str(work))

        # Thumbnail JPG nhẹ (~30KB) — thư viện hiện ảnh này thay vì load video (hết lag)
        thumb_path = out_path.with_suffix(".jpg")
        try:
            _run(["ffmpeg", "-y", "-ss", "1", "-i", str(out_path), "-frames:v", "1",
                  "-vf", "scale=360:-2", "-q:v", "5", str(thumb_path)])
        except Exception as _e:
            print(f"[list_review] thumb lỗi: {_e}", file=sys.stderr)
            thumb_path = None

        return {"success": True, "video_path": str(out_path.resolve()),
                "thumb_path": str(thumb_path.resolve()) if thumb_path and thumb_path.exists() else "",
                "segments": len(segs), "duration": _ffprobe_dur(str(out_path))}
    finally:
        # giữ work dir nếu debug; xoá để gọn
        shutil.rmtree(work, ignore_errors=True)
