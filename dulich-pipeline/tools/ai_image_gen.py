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

MODEL = "gemini-2.5-flash-image"   # Nano Banana (thường) — ~1.000đ/ảnh (rẻ hơn Pro ~3.500đ);
# đánh đổi: chữ tiếng Việt dễ sai/méo hơn Pro (user chọn ưu tiên chi phí). Đổi lại "gemini-3-pro-image-preview" nếu cần chữ chuẩn.
API = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
OUT_DIR = Path(__file__).resolve().parent.parent / "output" / "ai_images"
REF_DIR = Path(__file__).resolve().parent.parent.parent / "source-anh-moi"   # mẫu gốc

# Mẫu tham chiếu mặc định cho từng template (bám bố cục các poster viral)
DEFAULT_REFS = {
    "list8": REF_DIR / "z8041268500730_52f56108db2080fd03d64e29021e4c22.jpg",
    "map3d": REF_DIR / "z8041268511802_c6fed680e170559a721044f8e431638b.jpg",
}


# Quy tắc chữ — điểm mấu chốt để không sai chính tả (headline brush hay bịa chữ nhất).
_TEXT_RULE = (
    "\n\nQUY TẮC CHỮ (QUAN TRỌNG NHẤT — đọc kỹ):\n"
    "1. Ảnh tham chiếu CHỈ để bám BỐ CỤC + PHONG CÁCH. TUYỆT ĐỐI KHÔNG chép lại chữ có trong ảnh mẫu.\n"
    "2. CHỈ render đúng các chuỗi chữ tôi ghi ở trên — đúng TỪNG KÝ TỰ và TỪNG DẤU thanh tiếng Việt "
    "(sắc/huyền/hỏi/ngã/nặng và ă â ê ô ơ ư đ).\n"
    "3. KHÔNG thêm, KHÔNG bớt, KHÔNG bịa/đổi chữ. Chữ tiêu đề dù vẽ brush vẫn phải ĐỌC RA ĐÚNG chính tả, "
    "không được méo thành chữ vô nghĩa (vd KHÔNG được biến 'YÊU'→'VƯU', 'NÊN'→'ĐẾN', 'LẤP'→'LẦP').\n"
    "4. CHỈ render đúng những chuỗi chữ tôi cung cấp. Mọi vùng chữ phụ KHÔNG có trong danh sách của tôi "
    "(dòng 'mẹo nhỏ' ở chân poster, ghi chú dán tay, tem, caption nhỏ...) thì ĐỂ TRỐNG hoặc thay bằng icon — "
    "TUYỆT ĐỐI KHÔNG tự bịa thêm chữ tiếng Việt (rất hay sai chính tả).\n"
    "5. Nếu không chắc 1 chữ, viết đơn giản rõ ràng còn hơn viết sai."
)


def _prompt_list8(spec: dict) -> str:
    items = spec.get("items") or []
    lines = "\n".join(
        f'{i}. "{it.get("name", "")}" — {it.get("sub", "")} — {it.get("desc", "")}'
        for i, it in enumerate(items, 1))
    return (
        "Tạo poster infographic du lịch Đà Lạt bám SÁT bố cục, phong cách scrapbook, typography brush "
        "vẽ tay và chất lượng của ảnh tham chiếu (ảnh mẫu chỉ để tham khảo bố cục + phong cách), "
        "dùng nội dung + màu sau:\n"
        "CHỮ TIÊU ĐỀ (render chính xác từng ký tự):\n"
        f"• Tiêu đề lớn: \"{spec.get('title', '')}\"\n"
        f"• Ribbon phụ: \"{spec.get('subtitle', '')}\"\n"
        f"• Tagline: \"{spec.get('tagline', '')}\"\n"
        f"- Tông màu chủ đạo: {spec.get('palette', 'xanh rêu + kem giấy')}.\n"
        f"- 8 mục (mỗi card: số, ảnh ĐÚNG món/địa điểm đó, tên đậm, icon 📍 + địa chỉ, mô tả, giá tham khảo hợp lý):\n{lines}\n"
        f"- Watermark góc: \"{spec.get('handle', '@dalatnow')}\"."
        + _TEXT_RULE
    )


def _prompt_map3d(spec: dict) -> str:
    places = ", ".join(spec.get("places") or [])
    return (
        "Tạo poster BẢN ĐỒ DU LỊCH ĐÀ LẠT bám sát phong cách, bố cục, chất lượng 3D isometric "
        "của ảnh tham chiếu (thành phố thu nhỏ, nhãn tên địa danh trong bong bóng trắng chỉ đúng "
        "công trình, chữ 3D lớn ĐÀ LẠT màu đá trắng ở giữa, headline brush vẽ tay trên cùng); "
        "ảnh mẫu chỉ để tham khảo bố cục + phong cách:\n"
        "CHỮ TIÊU ĐỀ (render chính xác từng ký tự):\n"
        "• Headline trên cùng: \"BẢN ĐỒ DU LỊCH ĐÀ LẠT\"\n"
        f"- Khung cảnh/màu sắc: {spec.get('palette', 'nắng vàng rực rỡ, trời xanh')}.\n"
        f"- Nhãn địa danh (mỗi nhãn 1 bong bóng, render chính xác): {places}.\n"
        f"- Watermark: \"{spec.get('handle', '@dalatnow')}\"."
        + _TEXT_RULE
    )


def _norm_text(s: str) -> str:
    """Chuẩn hoá để so khớp: chữ HOA, chỉ giữ ký tự chữ/số (bỏ dấu cách, dấu câu)."""
    return "".join(ch for ch in (s or "").upper() if ch.isalnum())


def _ocr_title(png_path: str, key: str) -> str:
    """OCR nhanh (Gemini flash) đọc chữ TIÊU ĐỀ LỚN của ảnh vừa tạo — để verify chính tả."""
    import requests
    try:
        b64 = base64.b64encode(Path(png_path).read_bytes()).decode()
        r = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={key}",
            timeout=90, json={"contents": [{"parts": [
                {"text": "Đọc CHÍNH XÁC toàn bộ chữ TIÊU ĐỀ LỚN (headline + ribbon + tagline) ở đầu poster này, "
                         "giữ nguyên dấu tiếng Việt. Trả JSON {\"title\":\"...\"} gộp hết thành 1 chuỗi."},
                {"inline_data": {"mime_type": "image/png", "data": b64}}]}],
                "generationConfig": {"responseMimeType": "application/json"}})
        if r.status_code != 200:
            return ""
        return (json.loads(r.json()["candidates"][0]["content"]["parts"][0]["text"]).get("title") or "").strip()
    except Exception:
        return ""


def _title_ok(intended: str, ocr: str) -> bool:
    """True nếu mọi TỪ (>=3 ký tự) của tiêu đề mong muốn đều xuất hiện trong chữ OCR đọc được.
    OCR rỗng → coi như pass (tránh render lại vô ích khi OCR lỗi)."""
    got = _norm_text(ocr)
    if not got:
        return True
    for w in (intended or "").split():
        wn = _norm_text(w)
        if len(wn) >= 3 and wn not in got:
            return False
    return True


def generate_infographic(spec: dict, out_name: str = "", size: str = "2K", verify: bool = True) -> dict:
    """Gọi Nano Banana Pro → PNG trong output/ai_images/. Trả {success, path|error}.
    verify=True: OCR lại tiêu đề, nếu sai chính tả thì render lại (tối đa 2 lần)."""
    import requests
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GEMINI_KEY")
    if not key:
        return {"success": False, "error": "Thiếu GEMINI_API_KEY"}
    tpl = (spec.get("template") or "list8").lower()
    prompt = _prompt_map3d(spec) if tpl == "map3d" else _prompt_list8(spec)

    ref_part = None
    ref = spec.get("reference") or DEFAULT_REFS.get(tpl)
    if ref and Path(ref).exists():
        mime = mimetypes.guess_type(str(ref))[0] or "image/jpeg"
        ref_part = {"inline_data": {"mime_type": mime,
                                    "data": base64.b64encode(Path(ref).read_bytes()).decode()}}

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / (out_name or f"aiimg_{tpl}_{int(time.time())}.png")
    intended = " ".join(x for x in (spec.get("title", ""), spec.get("subtitle", ""),
                                    spec.get("tagline", "")) if x)
    max_try = 2 if verify else 1
    last_err, warnings = "", []
    for attempt in range(1, max_try + 1):
        parts = [{"text": prompt}] + ([ref_part] if ref_part else [])
        try:
            r = requests.post(
                f"{API}?key={key}", timeout=600,
                json={"contents": [{"parts": parts}],
                      "generationConfig": {
                          "responseModalities": ["IMAGE"],
                          "imageConfig": {"aspectRatio": "9:16", "imageSize": size}}})
            if r.status_code != 200:
                last_err = f"Gemini {r.status_code}: {r.text[:300]}"; continue
            img_b64 = next((p["inlineData"]["data"]
                            for p in r.json()["candidates"][0]["content"]["parts"]
                            if "inlineData" in p), None)
            if not img_b64:
                last_err = "Gemini không trả ảnh (bị chặn nội dung?)"; continue
            out.write_bytes(base64.b64decode(img_b64))
        except Exception as e:
            last_err = str(e); continue
        # Verify tiêu đề — sai + còn lượt thì render lại (ảnh sinh ngẫu nhiên nên lần sau thường đúng)
        if verify and intended:
            ocr = _ocr_title(str(out), key)
            if _title_ok(intended, ocr):
                return {"success": True, "path": str(out)}
            warnings = [f"Tiêu đề có thể sai chính tả (AI đọc lại: '{ocr}')"]
            print(f"[ai_image] verify lần {attempt} nghi sai tiêu đề, OCR='{ocr}'", file=sys.stderr)
            continue
        return {"success": True, "path": str(out)}
    if out.exists():
        return {"success": True, "path": str(out), "text_warnings": warnings}
    return {"success": False, "error": last_err or "Không tạo được ảnh"}


def _resize_1080(png_path: str) -> None:
    """Thu ảnh 2K về 1080×1920 (đủ đăng TikTok, nhẹ hơn)."""
    try:
        from PIL import Image
        im = Image.open(png_path)
        if im.width > 1080:
            im = im.resize((1080, round(im.height * 1080 / im.width)), Image.LANCZOS)
            im.save(png_path, optimize=True)
    except Exception as e:
        print(f"[ai_image] resize lỗi: {e}", file=sys.stderr)


def spec_from_reference_images(image_paths: list[str]) -> dict | None:
    """Gemini đọc bài mẫu (ảnh) → spec {title, subtitle, tagline, palette, category, items}."""
    import requests
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GEMINI_KEY")
    if not key or not image_paths:
        return None
    parts = [{"text":
        "Đọc bộ ảnh infographic du lịch Đà Lạt này và trích xuất nội dung. Trả về JSON:\n"
        '{"title":"headline chính","subtitle":"dòng phụ/ribbon","tagline":"câu mô tả ngắn",'
        '"palette":"mô tả tông màu chủ đạo của bài (để tạo lại giống)",'
        '"category":"quán ăn"|"quán cà phê"|"khách sạn"|"tham quan",'
        '"items":[{"name":"tên địa điểm","sub":"địa chỉ/sđt nếu có","desc":"mô tả 1 câu"}...]}\n'
        "Lấy TẤT CẢ các mục trong bài. Chỉ trả JSON."}]
    for p in image_paths[:3]:
        mime = mimetypes.guess_type(p)[0] or "image/jpeg"
        parts.append({"inline_data": {"mime_type": mime,
                                      "data": base64.b64encode(Path(p).read_bytes()).decode()}})
    try:
        r = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={key}",
            timeout=180, json={"contents": [{"parts": parts}],
                               "generationConfig": {"responseMimeType": "application/json"}})
        if r.status_code != 200:
            print(f"[ai_image] đọc mẫu {r.status_code}: {r.text[:200]}", file=sys.stderr)
            return None
        txt = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        d = json.loads(txt)
        return d if d.get("items") else None
    except Exception as e:
        print(f"[ai_image] đọc mẫu lỗi: {e}", file=sys.stderr)
        return None


def mix_in_seeding_venues(spec: dict, replace_n: int) -> dict:
    """Thay replace_n mục trong spec.items bằng quán thư viện loại 'cần seeding' (quán mình + đối tác)."""
    import random
    from tools.venues_db import get_all
    items = list(spec.get("items") or [])
    if not items or replace_n <= 0:
        return spec
    cat = (spec.get("category") or "").strip()
    seeding = [v for v in get_all() if (v.get("loai") or "").strip() == "cần seeding"]
    pool = [v for v in seeding if (v.get("loai_quan") or "").strip() == cat] or seeding
    random.shuffle(pool)
    n = min(replace_n, len(items), len(pool))
    idxs = random.sample(range(len(items)), n)
    for k, i in enumerate(idxs):
        v = pool[k]
        items[i] = {"name": v.get("name", ""),
                    "sub": (v.get("address") or "").split(",")[0].strip(),
                    "desc": (v.get("signature") or v.get("feature") or "Địa điểm được yêu thích ở Đà Lạt.").strip()[:90]}
    spec["items"] = items
    spec["_replaced"] = [items[i]["name"] for i in idxs]
    return spec


def generate_from_tiktok(url: str, replace_n: int = 4, handle: str = "@dalatnow") -> dict:
    """Flow đầy đủ: link bài ảnh TikTok → đọc mẫu → trộn quán seeding → render lại 1080."""
    import shutil
    from tools.tiktok_photos import download_photos
    imgs, tmp = download_photos(url, max_imgs=3)
    try:
        if not imgs:
            return {"success": False, "error": "Không tải được ảnh từ link (link phải là bài ẢNH TikTok)"}
        spec = spec_from_reference_images(imgs)
        if not spec:
            return {"success": False, "error": "AI không đọc được nội dung bài mẫu"}
        spec = mix_in_seeding_venues(spec, replace_n)
        spec["template"] = "list8"
        spec["handle"] = handle
        # reference = ảnh trang list (ảnh 2 nếu có, không thì ảnh đầu) để bám bố cục
        spec["reference"] = imgs[1] if len(imgs) > 1 else imgs[0]
        res = generate_infographic(spec, size="2K")
        if res.get("success"):
            _resize_1080(res["path"])
            res["replaced"] = spec.get("_replaced", [])
            res["title"] = spec.get("title", "")
        return res
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ── Tạo lại TOÀN BỘ ảnh trong 1 bài carousel (vẽ y hệt từng trang) ────────────
_RECREATE_PROMPT = (
    "Đây là 1 trang trong bộ carousel infographic du lịch Đà Lạt. VẼ LẠI trang này GIỐNG HỆT ảnh gốc: "
    "y nguyên bố cục, phong cách thiết kế, phối màu, ảnh nền, các icon (ngón tay lên/xuống, ghim địa điểm, "
    "tim, mũi tên...) và TOÀN BỘ chữ. Sao chép CHÍNH XÁC từng chữ tiếng Việt như trong ảnh gốc — đúng chính tả "
    "và dấu thanh 100% (sắc/huyền/hỏi/ngã/nặng, ă â ê ô ơ ư đ), KHÔNG thêm/bớt/đổi/bịa chữ, không để chữ méo "
    "thành chữ vô nghĩa. Chỉ thay đổi DUY NHẤT: watermark/handle (nếu có) đổi thành \"{handle}\". "
    "Render sắc nét, chất lượng cao."
)

_RATIOS = {"1:1": 1.0, "3:4": 0.75, "2:3": 0.667, "9:16": 0.5625, "4:3": 1.333, "3:2": 1.5, "16:9": 1.778}


def _nearest_ratio(path: str) -> str:
    """Chọn aspectRatio Gemini gần nhất với ảnh gốc (bài TikTok thường 3:4 / 9:16 / 1:1)."""
    try:
        from PIL import Image
        w, h = Image.open(path).size
        r = w / h
        return min(_RATIOS, key=lambda k: abs(_RATIOS[k] - r))
    except Exception:
        return "3:4"


def _recreate_one(ref_path: str, handle: str, key: str, size: str = "2K"):
    """Vẽ lại 1 ảnh y hệt ảnh gốc bằng Nano Banana Pro. Trả (bytes|None, error)."""
    import requests
    try:
        mime = mimetypes.guess_type(ref_path)[0] or "image/jpeg"
        parts = [{"text": _RECREATE_PROMPT.format(handle=handle)},
                 {"inline_data": {"mime_type": mime,
                                  "data": base64.b64encode(Path(ref_path).read_bytes()).decode()}}]
        r = requests.post(
            f"{API}?key={key}", timeout=600,
            json={"contents": [{"parts": parts}],
                  "generationConfig": {"responseModalities": ["IMAGE"],
                                       "imageConfig": {"aspectRatio": _nearest_ratio(ref_path)}}})
        if r.status_code != 200:
            return None, f"Gemini {r.status_code}: {r.text[:150]}"
        img = next((p["inlineData"]["data"]
                    for p in r.json()["candidates"][0]["content"]["parts"] if "inlineData" in p), None)
        return (base64.b64decode(img) if img else None), ("" if img else "không trả ảnh (bị chặn?)")
    except Exception as e:
        return None, str(e)


def recreate_all_from_tiktok(url: str, handle: str = "@dalatnow", max_imgs: int = 10) -> dict:
    """Link bài ảnh TikTok → tải HẾT N ảnh → vẽ lại y hệt từng ảnh (đổi watermark = handle).
    Trả {success, paths:[...], count, source_count, errors}."""
    import shutil
    from tools.tiktok_photos import download_photos
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GEMINI_KEY")
    if not key:
        return {"success": False, "error": "Thiếu GEMINI_API_KEY"}
    imgs, tmp = download_photos(url, max_imgs=max_imgs)
    try:
        if not imgs:
            return {"success": False, "error": "Không tải được ảnh từ link (link phải là bài ẢNH TikTok)"}
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        stamp = int(time.time())
        out_paths, errs = [], []
        for i, ref in enumerate(imgs):
            data, err = _recreate_one(ref, handle, key)
            if not data:
                errs.append(f"ảnh {i + 1}: {err}")
                print(f"[ai_image] recreate ảnh {i + 1} lỗi: {err}", file=sys.stderr)
                continue
            p = OUT_DIR / f"recr_{stamp}_{i:02d}.png"
            p.write_bytes(data)
            _resize_1080(str(p))
            out_paths.append(str(p))
        if not out_paths:
            return {"success": False, "error": "Không tạo lại được ảnh nào. " + "; ".join(errs[:3])}
        return {"success": True, "paths": out_paths, "count": len(out_paths),
                "source_count": len(imgs), "errors": errs}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


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
