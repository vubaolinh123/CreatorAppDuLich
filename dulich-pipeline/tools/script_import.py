"""
script_import.py — Tạo kịch bản từ nguồn ngoài (giảm lặp nội dung):
  scenes_from_text(text)  — dán kịch bản thô → AI chia thành scenes chuẩn editor.
  scenes_from_link(url)   — link TikTok/YouTube → yt-dlp tải audio → Whisper đọc
                            → AI viết kịch bản MỚI theo tinh thần clip (không copy).
"""
from __future__ import annotations
import os, json, sys, tempfile
from pathlib import Path

try:
    from dotenv import load_dotenv, find_dotenv
    load_dotenv(find_dotenv(usecwd=True))
except ImportError:
    pass

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "openai/gpt-4o-mini"
MAX_CLIP_SEC = 300   # chỉ nhận clip ≤5 phút (đỡ tốn Whisper)


def _ai_scenes(prompt_user: str) -> list | None:
    """Gọi AI trả JSON {intro:{title,vo}, spots:[{name,vo}], outro:{vo}} → scenes editor."""
    import requests
    key = os.getenv("OPENROUTER_KEY") or os.getenv("OPENROUTER_API_KEY")
    if not key:
        return None
    r = requests.post(
        OPENROUTER_URL, timeout=60,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"model": MODEL, "temperature": 0.9, "max_tokens": 1200,
              "response_format": {"type": "json_object"},
              "messages": [
                  {"role": "system", "content":
                   "Bạn là biên kịch video TikTok du lịch Đà Lạt, giọng gần gũi. Chỉ trả về JSON."},
                  {"role": "user", "content": prompt_user}]})
    if r.status_code != 200:
        print(f"[script_import] OpenRouter {r.status_code}: {r.text[:200]}", file=sys.stderr)
        return None
    txt = r.json()["choices"][0]["message"]["content"].strip()
    if txt.startswith("```"):
        txt = txt.strip("`").lstrip("json").strip()
    d = json.loads(txt)
    intro = d.get("intro") or {}
    spots = d.get("spots") or []
    outro = d.get("outro") or {}
    scenes = [{"scene_id": "intro", "kind": "intro", "label": "HOOK",
               "title": (intro.get("title") or "").strip(),
               "caption": (intro.get("vo") or "").strip(),
               "min_duration_sec": 13, "sources_needed": 2, "type": "clip"}]
    for i, sp in enumerate(spots, 1):
        scenes.append({"scene_id": f"spot{i}", "kind": "spot", "label": f"CẢNH {i}",
                       "name": (sp.get("name") or "").strip(),
                       "caption": (sp.get("vo") or "").strip(),
                       "min_duration_sec": 9, "sources_needed": 3, "type": "clip"})
    scenes.append({"scene_id": "outro", "kind": "outro", "label": "OUTRO",
                   "caption": (outro.get("vo") or "").strip(),
                   "min_duration_sec": 4, "sources_needed": 2, "type": "clip"})
    return scenes if any(s.get("caption") for s in scenes) else None


_FORMAT_RULE = (
    'Trả về JSON: {"intro":{"title":"tiêu đề ngắn hiện trên hook","vo":"lời thoại mở đầu 2-3 câu"},'
    '"spots":[{"name":"tên cảnh/quán","vo":"lời thoại 2-3 câu"}...],'
    '"outro":{"vo":"lời chốt + kêu gọi 1-2 câu"}}. '
    "2-4 spots. Lời thoại tự nhiên như nói chuyện, tiếng Việt có dấu, không emoji, không hashtag."
)


def scenes_from_text(text: str) -> list | None:
    """Người dùng dán kịch bản/ý tưởng thô → chia thành scenes chuẩn (giữ nội dung, chỉ cấu trúc lại)."""
    text = (text or "").strip()[:6000]
    if not text:
        return None
    return _ai_scenes(
        "Cấu trúc lại kịch bản/ý tưởng sau thành kịch bản video list-review Đà Lạt. "
        "GIỮ nguyên ý và giọng của người viết, chỉ chia cảnh + chỉnh cho trơn miệng.\n\n"
        f"NỘI DUNG:\n{text}\n\n{_FORMAT_RULE}")


def _transcribe_link(url: str) -> str:
    """yt-dlp tải audio (TikTok/YouTube) → Whisper (OpenAI API) đọc thành văn bản."""
    import yt_dlp, requests
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise ValueError("Thiếu OPENAI_API_KEY (Whisper)")
    tmp = Path(tempfile.mkdtemp(prefix="lnk_"))
    try:
        opts = {"quiet": True, "outtmpl": str(tmp / "audio.%(ext)s"),
                "format": "bestaudio/best", "noplaylist": True}
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
        if info.get("duration") and info["duration"] > MAX_CLIP_SEC:
            raise ValueError(f"Clip dài quá {MAX_CLIP_SEC // 60} phút — chọn clip ngắn hơn")
        files = list(tmp.glob("audio.*"))
        if not files:
            raise ValueError("Không tải được audio từ link")
        with open(files[0], "rb") as f:
            r = requests.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {key}"},
                data={"model": "whisper-1", "language": "vi"},
                files={"file": (files[0].name, f)}, timeout=180)
        if r.status_code != 200:
            raise ValueError(f"Whisper {r.status_code}: {r.text[:150]}")
        return (r.json().get("text") or "").strip()
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


def scenes_from_link(url: str, employee: str = "") -> list | None:
    """Đọc clip từ link → AI viết kịch bản MỚI theo tinh thần clip (không copy nguyên văn).
    Chỉ thị viết-lại lấy từ prompt tuỳ chỉnh của nv (trang Prompt), không thì mặc định."""
    transcript = _transcribe_link(url)
    if not transcript:
        return None
    try:
        from tools.script_prompts import effective_link_prompt
        rewrite = effective_link_prompt(employee)
    except Exception:
        rewrite = ("Dưới đây là nội dung (transcript) của 1 clip du lịch tham khảo. "
                   "Viết 1 kịch bản MỚI cùng chủ đề/tinh thần nhưng KHÔNG copy nguyên văn — "
                   "đổi cách diễn đạt, có thể đổi góc nhìn, giữ các thông tin địa điểm đúng.")
    return _ai_scenes(f"{rewrite}\n\nTRANSCRIPT:\n{transcript[:5000]}\n\n{_FORMAT_RULE}")
