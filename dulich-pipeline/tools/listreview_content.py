"""
listreview_content.py — Sinh sẵn nội dung video nv1 (list review quán) từ thư viện quán.
AI (OpenRouter) viết kịch bản theo tông nv1 "các con vợ", tự chấm điểm; fallback deterministic.
Nhân viên chỉ việc thả source vào từng scene.
"""
from __future__ import annotations

import os
import json
from pathlib import Path

from tools.venue_library import inhouse_food

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CACHE = DATA_DIR / "prefill" / "nv1.json"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Cấu hình template từng nhân viên: badge_mode + transition (chuyển cảnh).
#  full = tên+điểm+địa chỉ (nv1); name = chỉ tên quán (nv2/3/5); none = không badge (nv4 montage).
#  transition: none = ghép cứng; swoosh = chuyển cảnh slide (chỉ hiệu ứng hình).
_TEMPLATES = {
    "nv1": {"badge_mode": "full", "transition": "fade"},
    "nv2": {"badge_mode": "name", "transition": "fade"},
    "nv3": {"badge_mode": "name", "transition": "fade"},
    "nv4": {"badge_mode": "none", "transition": "fade"},
    "nv5": {"badge_mode": "name", "transition": "fade"},
}
_DEFAULT_TEMPLATE = {"badge_mode": "name", "transition": "fade"}


def _hook_style(employee: str) -> str:
    """Hook khung của nhân viên (red/green/brown/serif/meo) — lấy từ users.json."""
    try:
        u = json.loads((DATA_DIR / "users.json").read_text(encoding="utf-8"))
        return (u.get(employee, {}) or {}).get("hook_style", "hook_red")
    except Exception:
        return "hook_red"


# Định dạng JSON output — CỐ ĐỊNH (pipeline render phụ thuộc), không cho user sửa.
_FORMAT_NV = (
    " Mỗi scene kèm field 'ref' = 1 câu ngắn GỢI Ý loại clip nhân viên nên quay/tìm cho cảnh đó "
    "(vd 'Clip cận món gà đốt + không gian quán', 'Clip toàn cảnh con đường vào Đà Lạt'). "
    'Trả DUY NHẤT JSON: {"intro":{"title":"cụm ngắn in khung hook","vo":"...","ref":"..."},'
    '"spots":[{"name":"đúng tên quán","rating":"9","address":"đúng địa chỉ","vo":"...","ref":"..."}],'
    '"outro":{"vo":"...","ref":"..."}}. Giữ nguyên tên + địa chỉ quán. Chỉ JSON.'
)


def _ai_script(venues: list[dict], employee: str = "nv1") -> dict | None:
    key = os.getenv("OPENROUTER_KEY") or os.getenv("OPENROUTER_API_KEY")
    if not key:
        return None
    lines = "\n".join(
        f"- {v['name']} | địa chỉ: {v['address']} | đặc điểm: {v['feature']} | món signature: {v['signature']}"
        for v in venues
    )
    from tools.script_prompts import effective_persona, get_script_prompt
    persona = effective_persona(employee)
    ex = get_script_prompt(employee)["examples"]
    system = persona + _FORMAT_NV + (f"\n\nVÍ DỤ THAM KHẢO (học giọng, đừng chép):\n{ex}" if ex else "")
    try:
        import requests
        r = requests.post(OPENROUTER_URL, timeout=60,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": "openai/gpt-4o-mini",
                  "messages": [{"role": "system", "content": system},
                               {"role": "user", "content": f"DANH SÁCH QUÁN:\n{lines}"}],
                  "response_format": {"type": "json_object"}, "temperature": 0.9})
        if r.status_code != 200:
            print(f"[listreview] OpenRouter {r.status_code}: {r.text[:160]}")
            return None
        d = json.loads(r.json()["choices"][0]["message"]["content"])
        if d.get("intro") and d.get("spots"):
            return d
    except Exception as e:
        print(f"[listreview] AI lỗi: {e}")
    return None


def _fallback_script(venues: list[dict]) -> dict:
    ratings = ["9", "10", "8.5", "9.5", "9", "8.5"]
    spots = []
    for i, v in enumerate(venues):
        sig = f" Món tủ là {v['signature']} nha." if v.get("signature") else ""
        feat = v["feature"].lower() if v.get("feature") else "không gian + món ăn"
        spots.append({
            "name": v["name"], "rating": ratings[i % len(ratings)], "address": v["address"],
            "vo": f"{v['name']} nè các con vợ, {v['feature'].lower() if v['feature'] else 'quán ngon ở Đà Lạt'}."
                  f"{sig} Quán ở {v['address']}, ghé thử đi nha.",
            "ref": f"Clip cảnh {v['name']}: {feat}"
                   + (f", cận món {v['signature']}" if v.get("signature") else "") + ", góc check-in.",
        })
    return {
        "intro": {"title": "Ăn gì ở Đà Lạt",
                  "vo": "hé lô các con vợ của anh, hôm nay anh chỉ cho mấy em mấy quán ăn ở Đà Lạt ngon mà chất nha",
                  "ref": "Clip mở đầu: toàn cảnh Đà Lạt / con đường / nhiều quán ăn cho hấp dẫn."},
        "spots": spots,
        "outro": {"vo": "đó là mấy quán anh tâm đắc, lưu lại đi Đà Lạt ghé thử cho biết nha mấy con vợ",
                  "ref": "Clip chốt: cảnh đẹp Đà Lạt / khách ăn vui / quay tay vẫy chào."},
    }


def _to_scenes(script: dict, venues: list[dict], badge_mode: str = "full") -> list[dict]:
    """badge_mode='full' → tên+điểm+địa chỉ (nv1); 'name' → CHỈ tên quán (nv2-5);
    'none' → không badge (nv4 montage). Mọi scene có reference_source (gợi ý clip)."""
    intro = script.get("intro") or {}
    outro = script.get("outro") or {}
    ai_spots = script.get("spots") or []
    full = (badge_mode == "full")
    scenes = [{
        "scene_id": "intro", "kind": "intro", "label": "HOOK",
        "title": (intro.get("title") or "Ăn gì ở Đà Lạt").strip(),
        "caption": (intro.get("vo") or "").strip(),
        "reference_source": (intro.get("ref") or "").strip(),
        "min_duration_sec": 13, "sources_needed": 2, "type": "clip",
    }]
    for i, v in enumerate(venues, start=1):
        sp = ai_spots[i - 1] if i - 1 < len(ai_spots) else {}
        sc = {
            "scene_id": f"spot{i}", "kind": "spot", "label": f"QUÁN {i}",
            "name": (sp.get("name") or v["name"]).strip(),
            "caption": (sp.get("vo") or "").strip(),
            "reference_source": (sp.get("ref") or "").strip(),
            "min_duration_sec": 9, "sources_needed": 3, "type": "clip",
        }
        if full:
            sc["rating"] = (str(sp.get("rating") or "9")).replace("/10", "").strip()
            sc["address"] = (sp.get("address") or v["address"]).strip()
        scenes.append(sc)
    scenes.append({
        "scene_id": "outro", "kind": "outro", "label": "OUTRO",
        "caption": (outro.get("vo") or "").strip(),
        "reference_source": (outro.get("ref") or "").strip(),
        "min_duration_sec": 4, "sources_needed": 2, "type": "clip",
    })
    return scenes


def build_prefill(employee: str, regen: bool = False) -> dict:
    """Nội dung điền sẵn cho 1 nhân viên — list review quán từ thư viện (engine PIL, hook khung).
    nv1: badge đầy đủ (tên+điểm+địa chỉ). nv2-5: chỉ tên quán. Cache data/prefill/<emp>.json."""
    employee = (employee or "nv1").strip().lower()
    cache = DATA_DIR / "prefill" / f"{employee}.json"
    tpl = _TEMPLATES.get(employee, _DEFAULT_TEMPLATE)
    badge_mode = tpl["badge_mode"]
    transition = tpl["transition"]
    if cache.exists() and not regen:
        try:
            d = json.loads(cache.read_text(encoding="utf-8"))
            # chỉ dùng cache nếu đã là schema PIL mới + có reference_source (bỏ qua cache cũ)
            if (d.get("scenes") and d.get("overlay_engine") == "pil"
                    and all("reference_source" in s for s in d["scenes"])):
                return d
        except Exception:
            pass
    venues = inhouse_food(3)
    if not venues:
        return {"scenes": [], "generated_by": "none", "error": "Không đọc được thư viện quán."}
    script = _ai_script(venues, employee)
    by = "ai" if script else "fallback"
    if not script:
        script = _fallback_script(venues)
    result = {
        "scenes": _to_scenes(script, venues, badge_mode),
        "generated_by": by,
        "overlay_engine": "pil",
        "hook_style": _hook_style(employee),
        "badge_mode": badge_mode,
        "transition": transition,
        "style": "",
    }
    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[listreview] cache lỗi: {e}")
    return result


def build_nv1_prefill(regen: bool = False) -> dict:
    return build_prefill("nv1", regen=regen)
