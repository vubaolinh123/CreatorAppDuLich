"""
script_ai.py — Generate a Vietnamese travel TikTok script via OpenRouter (cheap OpenAI
model), learning the STYLE from real TikTok transcripts saved in data/transcripts/.
Returns {title, hook, body, cta} or None on failure (caller falls back to a template).
"""

from __future__ import annotations

import os
import json
from pathlib import Path

TRANSCRIPT_DIR = Path(__file__).resolve().parent.parent / "data" / "transcripts"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "openai/gpt-4o-mini"  # cheap OpenAI model via OpenRouter


def _load_examples(max_chars: int = 4500) -> str:
    blocks, total = [], 0
    if TRANSCRIPT_DIR.exists():
        for fp in sorted(TRANSCRIPT_DIR.glob("clip*.txt")):
            if fp.name.endswith(".url.txt"):
                continue
            t = fp.read_text(encoding="utf-8").strip()
            if not t:
                continue
            block = f"--- Mẫu {len(blocks) + 1} ---\n{t}\n"
            if total + len(block) > max_chars:
                break
            blocks.append(block); total += len(block)
    return "\n".join(blocks)


def generate_script_ai(topic: str, employee: str = "tintuc") -> dict | None:
    key = os.getenv("OPENROUTER_KEY") or os.getenv("OPENROUTER_API_KEY")
    if not key:
        return None
    try:
        import requests
    except ImportError:
        return None

    # Persona sửa được theo nhân viên; examples = custom hoặc transcript mẫu sẵn.
    from tools.script_prompts import effective_persona, get_script_prompt
    persona = effective_persona(employee)
    examples = get_script_prompt(employee)["examples"] or _load_examples()
    try:
        from tools.script_drafts import recent_texts
        avoid = recent_texts(employee, 10)
    except Exception:
        avoid = []
    avoid_block = ("\n\n10 KỊCH BẢN GẦN NHẤT — TUYỆT ĐỐI KHÔNG viết giống câu chữ/ý những bài này:\n"
                   + "\n".join(f"- {a}" for a in avoid)) if avoid else ""
    system = (
        persona +
        "\n\nMẫu tham khảo (học giọng, đừng chép):\n" + (examples or "(không có mẫu)") +
        avoid_block +
        "\n\nViết kịch bản MỚI dài ~18 giây cho chủ đề người dùng đưa. Tổng lời đọc khoảng 60-70 từ (đủ ~18s khi đọc). "
        "Trả về DUY NHẤT một JSON: {\"title\":\"...\",\"hook\":\"...\",\"body\":\"...\",\"cta\":\"...\"}. "
        "title = cụm RẤT NGẮN (2-4 từ, thường là địa danh) để in trong khung hook. "
        "hook = 1 câu hook gây tò mò (dòng phụ dưới title). "
        "body = nội dung chính 2-3 câu. cta = 1 câu kêu gọi ngắn. Không thêm chữ nào ngoài JSON."
    )
    import random as _rnd
    _var = _rnd.randint(1000, 9999)
    try:
        r = requests.post(
            OPENROUTER_URL, timeout=60,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": MODEL,
                "messages": [
                    {"role": "system", "content": system + " Mỗi lần viết phải SÁNG TẠO, đổi mở đầu/góc nhìn, KHÔNG lặp lại lần trước."},
                    {"role": "user", "content": f"Chủ đề: {topic}\n[biến thể #{_var} — viết mới, khác các lần trước]"},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 1.0, "presence_penalty": 0.6,
            },
        )
        if r.status_code != 200:
            print(f"[script_ai] OpenRouter {r.status_code}: {r.text[:200]}")
            return None
        content = r.json()["choices"][0]["message"]["content"]
        d = json.loads(content)
        title = str(d.get("title", "")).strip()[:40]
        body = str(d.get("body", "")).strip()
        if not title or not body:
            return None
        return {
            "title": title,
            "hook": str(d.get("hook", "")).strip(),
            "body": body,
            "cta": str(d.get("cta", "")).strip() or "Lưu lại và theo dõi kênh nhé!",
        }
    except Exception as e:
        print(f"[script_ai] error: {e}")
        return None
