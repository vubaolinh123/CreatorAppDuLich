"""
album_titles.py — Random hoá title/hook/subtitle album bằng AI (OpenRouter DeepSeek).
Dùng chung cho mọi album: ai_cover_texts(kind, fallback, user_prompt="").
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

_HIST_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "album_text_history.json")


def _recent_texts(kind: str, n: int = 8) -> list:
    try:
        with open(_HIST_FILE, encoding="utf-8") as f:
            return (json.load(f).get(kind) or [])[-n:]
    except Exception:
        return []


def _remember_text(kind: str, out: dict) -> None:
    """Lưu 1 chuỗi gọn của bản vừa tạo để lần sau tránh lặp (giữ tối đa 12/kind)."""
    line = " | ".join(str(v).replace("\n", " ") for v in out.values() if v)[:200]
    if not line:
        return
    try:
        try:
            with open(_HIST_FILE, encoding="utf-8") as f:
                d = json.load(f)
        except Exception:
            d = {}
        lst = d.get(kind) or []
        lst.append(line)
        d[kind] = lst[-12:]
        os.makedirs(os.path.dirname(_HIST_FILE), exist_ok=True)
        with open(_HIST_FILE, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[album_titles] lưu history lỗi: {e}")

# Góc sáng tạo để AI không lặp chủ đề (bốc random 2 góc mỗi lần)
_ANGLES = [
    "cặp đôi hẹn hò", "gia đình có con nhỏ", "solo chữa lành", "nhóm bạn thân",
    "đi lần đầu", "đi mùa mưa", "đi mùa hoa", "săn mây sáng sớm", "đón Giáng sinh",
    "đi Tết", "ngân sách tiết kiệm", "team ăn uống", "team sống ảo",
    "đi xe máy phượt", "nghỉ dưỡng sang chảnh", "trốn nóng Sài Gòn", "đi cuối tuần",
]

# Mô tả riêng từng album: giọng văn + ràng buộc từng field
_KIND_DESC = {
    "le1": ("Cover album LỊCH TRÌNH Đà Lạt đăng group du lịch/mẹ bỉm trên Facebook, "
            "giọng gần gũi kiểu xin ý kiến. "
            "title: tối đa 8 từ, nêu chủ đề plan Đà Lạt (tự chọn tháng/dịp bất kỳ, không bó vào tháng 6). "
            "subtitle: tối đa 10 từ, câu xin ý kiến/tương tác. "
            "month_tag: dạng 'Tháng X' khớp với title (nếu title không nói tháng thì chọn 1 tháng bất kỳ)."),
    "le2": ("Cover album REVIEW địa điểm Đà Lạt, hook gây tò mò kiểu %s. "
            "percent: 2 chữ số + đúng 1 dấu %. "
            "title: đối tượng, tối đa 3 từ, chữ thường (vd 'khách du lịch', 'dân sành ăn', 'phượt thủ'). "
            "line1: tối đa 6 từ, bắt đầu bằng '/'. line2: tối đa 6 từ, kết thúc bằng '/'. "
            "line1+line2 đọc liền thành 1 câu có nghĩa."),
    "hien1": ("Album BẢN ĐỒ MÓN NGON / quán ăn nhất định phải thử ở Đà Lạt (KHÔNG nói về đèo). "
              "line1: dòng 1 title cover, 3-4 từ, chủ đề món ngon/quán ăn Đà Lạt (vd 'Bản đồ món ngon'). "
              "line2: dòng 2 title cover, 3-6 từ, KHÔNG kèm ngày tháng (vd 'Đà Lạt phải thử')."),
    "hien2": ("Cover album spotlight địa điểm Đà Lạt, hook kiểu POV tâm trạng giới trẻ. "
              "pov: đúng 3 dòng ngăn bằng \\n, dòng 1 là 'POV:', 2 dòng sau kể 1 tình huống "
              "đời thường dẫn tới việc đi Đà Lạt (thất tình, tăng lương, stress, hứng lên lúc nửa đêm...), "
              "mỗi dòng tối đa 9 từ."),
    "muoi1": ("Cover album lời khuyên du lịch Đà Lạt, chữ IN HOA dạng khẩu hiệu. "
              "line1/line2/line3: 3 dòng hook IN HOA, mỗi dòng tối đa 5 từ, "
              "line3 có thể để chuỗi rỗng nếu 2 dòng đủ nghĩa. Đọc liền phải có nghĩa."),
    "muoi2": ("3 title cho 3 trang danh sách địa điểm Đà Lạt. "
              "t1: title trang QUÁN ĂN (4-6 từ). t2: title trang THAM QUAN/CHECK-IN (4-6 từ). "
              "t3: title trang CÀ PHÊ (4-6 từ). Giọng trẻ, bắt trend nhẹ."),
    "vy1": ("Cover album tổng hợp địa điểm Đà Lạt. "
            "hook: headline 2 dòng ngăn bằng \\n, tổng tối đa 12 từ, giọng rủ rê/khẳng định "
            "(vd 'Đi hết những điểm này\\nở Đà Lạt')."),
    "vy2": ("Cover album cẩm nang du lịch Đà Lạt theo số giờ/ngày. "
            "hook: 2 dòng ngăn bằng \\n, dòng 1 nêu thời lượng chuyến đi (tự chọn: 48h, 72h, 3n2đ...), "
            "dòng 2 là câu hỏi/thách thức ngắn, mỗi dòng tối đa 6 từ."),
    "uyen1": ("Album travel tips Đà Lạt giọng teen viết tắt (r, ko, dc, mng, tui, oki...). "
              "intro: 1 dòng duy nhất (KHÔNG xuống dòng), tối đa 16 từ, giọng tâm sự rút kinh nghiệm, "
              "có thể kèm ':))))'. "
              "t1..t5: 5 title tip IN HOA bắt đầu bằng 'KO' hoặc từ phủ định/nhấn mạnh, mỗi cái tối đa 8 từ, "
              "giữ đúng chủ đề lần lượt: ảnh mạng ảo, săn mây, book phòng/dịch vụ, đồ dùng cần thiết, hỏi giá khi ăn. "
              "CHỈ dùng chữ tiếng Việt + số + dấu câu cơ bản (. , ! ? : ) ( ). TUYỆT ĐỐI KHÔNG dùng "
              "dấu %, ký hiệu đặc biệt, emoji, icon."),
    "uyen2": ("Cover album nhật ký review quán ăn Đà Lạt giọng teen. "
              "intro: đúng 3 dòng ngăn bằng \\n, dòng 1 nêu chuyến đi (vd 'Đà Lạt 3n2d'), "
              "dòng 2-3 kể việc ăn theo review + cái kết, mỗi dòng tối đa 6 từ, có thể kèm ':))))'. "
              "CHỈ dùng chữ tiếng Việt + số + dấu câu cơ bản (. , ! ? : ) ( ). TUYỆT ĐỐI KHÔNG dùng "
              "dấu %, ký hiệu đặc biệt, emoji, icon."),
}


def ai_cover_texts(kind: str, fallback: dict, user_prompt: str = "") -> dict:
    key = os.getenv("OPENROUTER_KEY") or os.getenv("OPENROUTER_API_KEY")
    desc = _KIND_DESC.get(kind)
    if not key or not desc:
        return fallback
    user_prompt = (user_prompt or os.getenv("ALBUM_TITLE_PROMPT", "")).strip()
    angles = ", ".join(random.sample(_ANGLES, 2))
    hist = _recent_texts(kind)
    avoid = ("\nCÁC BẢN ĐÃ TẠO GẦN ĐÂY — PHẢI KHÁC HẲN (đừng lặp chữ/ý/cấu trúc):\n- "
             + "\n- ".join(hist)) if hist else ""
    prompt = (
        "Viết lại bộ chữ cho ảnh cover album du lịch Đà Lạt.\n"
        f"Mô tả template: {desc}\n"
        f"Mẫu gốc (JSON): {json.dumps(fallback, ensure_ascii=False)}\n"
        "Yêu cầu: giữ đúng tinh thần + format từng field (số dòng \\n, IN HOA/thường, "
        "ký tự đặc biệt như 'POV:', '/', '%'), nhưng ĐỔI câu chữ hoàn toàn mới, sáng tạo, "
        f"không sao chép mẫu gốc. Gợi ý góc khai thác (tùy chọn): {angles}.\n"
        "CHÍNH TẢ + NGỮ PHÁP tiếng Việt CHUẨN, không viết sai/ngô nghê "
        "(vd đúng: 'không nên quá tin', 'đừng quá tin' — SAI: 'không đến quá tin'). "
        "Đọc lên phải xuôi tai, tự nhiên. Tiếng Việt có dấu, không emoji, không hashtag."
        f"{avoid}\n"
        f"Trả về JSON có đúng các key: {list(fallback.keys())}"
        + f"\n(seed đa dạng: {random.randint(1000, 9999)})"
    )
    if user_prompt:
        prompt = f"YÊU CẦU RIÊNG CỦA USER (ưu tiên cao nhất): {user_prompt}\n\n" + prompt
    try:
        r = requests.post(
            OPENROUTER_URL, timeout=30,
            headers={"Authorization": f"Bearer {key}",
                     "Content-Type": "application/json"},
            json={
                "model": MODEL,
                "temperature": 0.9,
                "max_tokens": 400,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": "Bạn là copywriter du lịch. Chỉ trả về JSON."},
                    {"role": "user", "content": prompt},
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
            if k in fallback and isinstance(v, str):
                v = v.strip().replace("\\n", "\n")
                if k == "percent":
                    v = v.rstrip("%") + "%"
                if v or k == "line3":   # line3 muoi1 được phép rỗng
                    out[k] = v
        print(f"[album_titles] {kind}: {out}")
        _remember_text(kind, out)   # ghi nhớ để lần sau tránh lặp
        return out
    except Exception as e:
        print(f"[album_titles] lỗi ({e}) → dùng mặc định")
        return fallback
