"""
ai_image_gen.py — Tạo infographic Đà Lạt bằng Gemini 3 Pro Image ("Nano Banana Pro",
model có thinking, chữ tiếng Việt chuẩn — cùng model với các mẫu viral).
Hỗ trợ ẢNH THAM CHIẾU: đưa poster mẫu vào, chỉ đổi nội dung + màu.

API: REST generativelanguage (requests, không cần lib mới). Key: GEMINI_API_KEY.

Dùng trong app:
    from tools.ai_image_gen import generate_infographic
    res = generate_infographic(spec)   # → {"success": True, "path": ".../xxx.png"}

spec = {
  "template": "list8" | "map3d",
  "title": "8 MÓN ĂN VẶT PHẢI THỬ",
  "subtitle": "Ở ĐÀ LẠT - THÁNG 8",
  "tagline": "NGON - RẺ - CHUẨN VỊ ĐỊA PHƯƠNG",
  "palette": "cam đất + nâu gỗ hoàng hôn",
  "items": [{"name","sub","desc"} x8],      # list8
  "places": ["Hồ Xuân Hương", ...],          # map3d
  "handle": "@dalatnow",
  "reference": "path/to/mau.jpg",            # optional — poster mẫu để bám bố cục
}

CLI demo:  python -X utf8 tools/ai_image_gen.py --demo 1
"""
from __future__ import annotations
import os, sys, json, base64, time, mimetypes
from pathlib import Path

try:
    from dotenv import load_dotenv, find_dotenv
    load_dotenv(find_dotenv(usecwd=True))
except ImportError:
    pass

MODEL = "gemini-3-pro-image-preview"   # Nano Banana Pro — thinking + text tiếng Việt chuẩn
API = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
OUT_DIR = Path(__file__).resolve().parent.parent / "output" / "ai_images"
REF_DIR = Path(__file__).resolve().parent.parent.parent / "source-anh-moi"   # mẫu gốc

# Mẫu tham chiếu mặc định cho từng template (bám bố cục các poster viral)
DEFAULT_REFS = {
    "list8": REF_DIR / "z8041268500730_52f56108db2080fd03d64e29021e4c22.jpg",
    "map3d": REF_DIR / "z8041268511802_c6fed680e170559a721044f8e431638b.jpg",
}


def _prompt_list8(spec: dict) -> str:
    items = spec.get("items") or []
    lines = "\n".join(
        f'{i}. "{it.get("name", "")}" — {it.get("sub", "")} — {it.get("desc", "")}'
        for i, it in enumerate(items, 1))
    return (
        "Tạo poster infographic du lịch Đà Lạt GIỐNG HỆT bố cục, phong cách scrapbook, "
        "typography brush vẽ tay và chất lượng của ảnh tham chiếu, nhưng ĐỔI nội dung và màu:\n"
        f"- Headline: \"{spec.get('title', '')}\" + ribbon \"{spec.get('subtitle', '')}\""
        f" + tagline \"{spec.get('tagline', '')}\".\n"
        f"- Tông màu chủ đạo: {spec.get('palette', 'xanh rêu + kem giấy')}.\n"
        f"- 8 mục (mỗi card: số, ảnh ĐÚNG món/địa điểm đó, tên đậm, icon 📍 + địa chỉ, mô tả, giá tham khảo hợp lý):\n{lines}\n"
        f"- Watermark góc: \"{spec.get('handle', '@dalatnow')}\".\n"
        "TOÀN BỘ chữ tiếng Việt phải ĐÚNG CHÍNH TẢ VÀ DẤU 100%."
    )


def _prompt_map3d(spec: dict) -> str:
    places = ", ".join(spec.get("places") or [])
    return (
        "Tạo poster BẢN ĐỒ DU LỊCH ĐÀ LẠT giống hệt phong cách, bố cục, chất lượng 3D isometric "
        "của ảnh tham chiếu (thành phố thu nhỏ, nhãn tên địa danh trong bong bóng trắng chỉ đúng "
        "công trình, chữ 3D lớn ĐÀ LẠT màu đá trắng ở giữa, headline brush vẽ tay trên cùng), nhưng ĐỔI:\n"
        f"- Khung cảnh/màu sắc: {spec.get('palette', 'nắng vàng rực rỡ, trời xanh')}.\n"
        f"- Các địa danh phải có: {places}.\n"
        f"- Watermark: \"{spec.get('handle', '@dalatnow')}\".\n"
        "TOÀN BỘ chữ tiếng Việt ĐÚNG CHÍNH TẢ VÀ DẤU 100%."
    )


def generate_infographic(spec: dict, out_name: str = "", size: str = "2K") -> dict:
    """Gọi Nano Banana Pro → PNG trong output/ai_images/. Trả {success, path|error}."""
    import requests
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        return {"success": False, "error": "Thiếu GEMINI_API_KEY"}
    tpl = (spec.get("template") or "list8").lower()
    prompt = _prompt_map3d(spec) if tpl == "map3d" else _prompt_list8(spec)

    parts = [{"text": prompt}]
    ref = spec.get("reference") or DEFAULT_REFS.get(tpl)
    if ref and Path(ref).exists():
        mime = mimetypes.guess_type(str(ref))[0] or "image/jpeg"
        parts.append({"inline_data": {"mime_type": mime,
                                      "data": base64.b64encode(Path(ref).read_bytes()).decode()}})
    try:
        r = requests.post(
            f"{API}?key={key}", timeout=600,
            json={"contents": [{"parts": parts}],
                  "generationConfig": {
                      "responseModalities": ["IMAGE"],
                      "imageConfig": {"aspectRatio": "9:16", "imageSize": size}}})
        if r.status_code != 200:
            return {"success": False, "error": f"Gemini {r.status_code}: {r.text[:300]}"}
        img_b64 = None
        for p in r.json()["candidates"][0]["content"]["parts"]:
            if "inlineData" in p:
                img_b64 = p["inlineData"]["data"]
                break
        if not img_b64:
            return {"success": False, "error": "Gemini không trả ảnh (bị chặn nội dung?)"}
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        out = OUT_DIR / (out_name or f"aiimg_{tpl}_{int(time.time())}.png")
        out.write_bytes(base64.b64decode(img_b64))
        return {"success": True, "path": str(out)}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ── Demo specs ────────────────────────────────────────────────────────────────
DEMOS = {
    "1": {
        "template": "list8",
        "title": "8 MÓN ĂN VẶT PHẢI THỬ",
        "subtitle": "Ở ĐÀ LẠT - THÁNG 8",
        "tagline": "NGON - RẺ - CHUẨN VỊ ĐỊA PHƯƠNG",
        "palette": "cam đất + nâu gỗ ấm áp hoàng hôn (thay xanh rêu)",
        "handle": "@dalatnow",
        "items": [
            {"name": "Bánh tráng nướng Dì Đinh", "sub": "26 Hoàng Diệu", "desc": "Pizza Đà Lạt giòn rụm, trứng béo thơm."},
            {"name": "Sữa đậu nành nóng", "sub": "Chợ đêm Đà Lạt", "desc": "Nóng hổi giữa trời lạnh, kèm bánh ngọt."},
            {"name": "Bánh căn Lệ", "sub": "27/44 Yersin", "desc": "Nhân trứng cút, nước chấm xíu mại đậm đà."},
            {"name": "Kem bơ Thanh Thảo", "sub": "76 Nguyễn Văn Trỗi", "desc": "Bơ sáp dẻo mịn, kem dừa mát lạnh."},
            {"name": "Bắp nướng mỡ hành", "sub": "Hồ Xuân Hương", "desc": "Thơm lừng góc hồ, vừa đi dạo vừa ăn."},
            {"name": "Bánh mì xíu mại", "sub": "Ngã 3 Hoàng Diệu", "desc": "Chén xíu mại nóng, chấm bánh mì giòn."},
            {"name": "Chè hé Đà Lạt", "sub": "11A 3 Tháng 2", "desc": "Quán chè cửa hé huyền thoại, ngọt thanh."},
            {"name": "Ốc bươu nhồi thịt", "sub": "33 Hai Bà Trưng", "desc": "Đậm vị sả ớt, ấm bụng buổi tối."},
        ],
    },
    "2": {
        "template": "map3d",
        "title": "BẢN ĐỒ DU LỊCH ĐÀ LẠT",
        "palette": "hoàng hôn tím hồng cam, đèn vàng bật sáng khắp thành phố, hồ phản chiếu ráng chiều",
        "handle": "@dalatnow",
        "places": ["Hồ Xuân Hương", "Nhà Thờ Con Gà", "Ga Đà Lạt", "Quảng Trường Lâm Viên",
                    "Thung Lũng Tình Yêu", "LangBiang", "Thác Datanla", "Đồi Chè Cầu Đất",
                    "Thiền Viện Trúc Lâm", "Hồ Tuyền Lâm"],
    },
}

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", default="1", choices=list(DEMOS.keys()))
    ap.add_argument("--size", default="2K", choices=["1K", "2K", "4K"])
    a = ap.parse_args()
    print(json.dumps(generate_infographic(DEMOS[a.demo], out_name=f"nb_module_demo{a.demo}.png",
                                          size=a.size), ensure_ascii=False))
