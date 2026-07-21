"""script_prompts.py — Prompt viết kịch bản chỉnh sửa được theo từng nhân viên.

Mỗi nv (1-5) + tin tức có 1 'persona' (giọng/phong cách) sửa được + 'examples' (mẫu tham khảo).
Phần định dạng JSON output là CỐ ĐỊNH (do pipeline render phụ thuộc) nên không cho sửa.
Lưu override ở data/script_prompts.json; trống → dùng persona mặc định.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DATA_DIR / "script_prompts.json"
_LOCK = threading.RLock()

# Persona mặc định (phần giọng/phong cách) — hiện cho user xem + sửa.
DEFAULT_PERSONA_NV = (
    "Bạn viết kịch bản video TikTok review quán ăn Đà Lạt theo tông kênh 'các con vợ' "
    "(nam, xưng 'anh', gọi người xem 'các con vợ/mấy vợ', vui, đời thường, hơi lầy). "
    "Dựa trên DANH SÁCH QUÁN cho sẵn, viết kịch bản list review: hook mở đầu hấp dẫn → lần lượt từng quán. "
    "Mỗi quán TỰ CHẤM điểm trên 10 (8.5 đến 10, quán signature ngon thì cao). "
    "Lời thoại mỗi quán 2-3 câu, CÀI ĐỊA CHỈ + nhắc món signature tự nhiên. Kết bằng câu chốt rủ lưu lại."
)
DEFAULT_PERSONA_NEWS = (
    "Bạn là copywriter viết kịch bản video du lịch ngắn (TikTok/Reels) tiếng Việt. "
    "Giọng thân mật, hook gây tò mò, nhịp nhanh, xưng hô gần gũi như 'các vợ/mình/nha'."
)

# Chỉ thị viết lại kịch bản từ transcript clip TikTok (dán link) — sửa được ở trang Prompt.
DEFAULT_LINK_PROMPT = (
    "Dưới đây là nội dung (transcript) của 1 clip du lịch tham khảo. "
    "Viết 1 kịch bản MỚI cùng chủ đề/tinh thần nhưng KHÔNG copy nguyên văn — "
    "đổi cách diễn đạt, có thể đổi góc nhìn, giữ các thông tin địa điểm đúng."
)


def default_persona(employee: str) -> str:
    return DEFAULT_PERSONA_NEWS if (employee or "").lower() == "tintuc" else DEFAULT_PERSONA_NV


def _load() -> dict:
    try:
        return json.loads(DB_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def get_script_prompt(employee: str) -> dict:
    """Trả {prompt, examples, link_prompt} đã lưu (rỗng nếu chưa set)."""
    employee = (employee or "").strip().lower()
    with _LOCK:
        rec = (_load().get(employee) or {})
    return {"prompt": (rec.get("prompt") or "").strip(),
            "examples": (rec.get("examples") or "").strip(),
            "link_prompt": (rec.get("link_prompt") or "").strip()}


def set_script_prompt(employee: str, prompt: str, examples: str, link_prompt: str = "") -> None:
    employee = (employee or "").strip().lower()
    with _LOCK:
        data = _load()
        data[employee] = {"prompt": (prompt or "").strip(),
                          "examples": (examples or "").strip(),
                          "link_prompt": (link_prompt or "").strip()}
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        DB_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def effective_persona(employee: str) -> str:
    """Persona dùng để gọi AI: custom nếu có, không thì mặc định."""
    return get_script_prompt(employee)["prompt"] or default_persona(employee)


def effective_link_prompt(employee: str) -> str:
    """Chỉ thị viết-lại-từ-link: custom nếu có, không thì mặc định."""
    return get_script_prompt(employee)["link_prompt"] or DEFAULT_LINK_PROMPT
