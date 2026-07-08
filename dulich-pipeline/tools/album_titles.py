"""
album_titles.py — Random hoá title/subtitle cover album bằng AI (OpenRouter DeepSeek).
Fail ở bất kỳ bước nào → trả fallback, không chặn render.
"""
from __future__ import annotations
import os, json, random, requests

try:
    from dotenv import load_dotenv, find_dotenv
    load_dotenv(find_dotenv(usecwd=True))
except ImportError:
    pass

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "deepseek/deepseek-chat"

_PROMPTS = {
    "le1": (
        "Viết lại title + subtitle cho ảnh cover album lịch trình du lịch Đà Lạt "
        "(phong cách hỏi xin ý kiến trong group mẹ bỉm / du lịch trên Facebook).\n"
        'Mẫu gốc: title "Soạn Plan đi Đà Lạt tháng 6", subtitle "Các mom cho em xin ý kiến nhé".\n'
        "Yêu cầu: giữ đúng tinh thần (plan đi Đà Lạt tháng 6, giọng gần gũi), "
        "nhưng ĐỔI cách diễn đạt cho mới. Title tối đa 8 từ, subtitle tối đa 10 từ. "
        "Tiếng Việt có dấu, không emoji, không hashtag.\n"
        'Trả về JSON đúng dạng: {"title": "...", "subtitle": "..."}'
    ),
    "le2": (
        "Viết lại bộ chữ hook cho ảnh cover album review địa điểm Đà Lạt.\n"
        'Mẫu gốc: percent "99%", title "khách du lịch", '
        'line1 "/chưa biết những điều này", line2 "hoặc chưa từng trải nghiệm /".\n'
        "Yêu cầu: giữ format hook gây tò mò kiểu %s + đối tượng + 2 dòng phụ, "
        "nhưng ĐỔI câu chữ cho mới (vd 95%, dân sành ăn, người mê Đà Lạt...). "
        "percent là 2 chữ số kèm 1 dấu % duy nhất. title tối đa 3 từ. line1/line2 mỗi dòng tối đa 6 từ, "
        "line1 bắt đầu bằng '/', line2 kết thúc bằng '/'. Tiếng Việt có dấu, không emoji.\n"
        'Trả về JSON đúng dạng: {"percent": "99%", "title": "...", "line1": "...", "line2": "..."}'
    ),
}


def ai_cover_texts(kind: str, fallback: dict) -> dict:
    key = os.getenv("OPENROUTER_KEY") or os.getenv("OPENROUTER_API_KEY")
    prompt = _PROMPTS.get(kind)
    if not key or not prompt:
        return fallback
    try:
        r = requests.post(
            OPENROUTER_URL, timeout=30,
            headers={"Authorization": f"Bearer {key}",
                     "Content-Type": "application/json"},
            json={
                "model": MODEL,
                "temperature": 1.1,
                "max_tokens": 200,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": "Bạn là copywriter du lịch. Chỉ trả về JSON."},
                    {"role": "user", "content": prompt +
                     f"\n(seed đa dạng: {random.randint(1000, 9999)})"},
                ],
            },
        )
        if r.status_code != 200:
            print(f"[album_titles] OpenRouter {r.status_code}: {r.text[:200]}")
            return fallback
        txt = r.json()["choices"][0]["message"]["content"].strip()
        if txt.startswith("```"):
            txt = txt.strip("`").lstrip("json").strip()
        data = json.loads(txt)
        out = dict(fallback)
        for k, v in data.items():
            if k in fallback and isinstance(v, str) and v.strip():
                v = v.strip()
                if k == "percent":
                    v = v.rstrip("%") + "%"
                out[k] = v
        print(f"[album_titles] {kind}: {out}")
        return out
    except Exception as e:
        print(f"[album_titles] lỗi ({e}) → dùng mặc định")
        return fallback
