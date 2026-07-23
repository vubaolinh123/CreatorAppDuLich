"""
venue_picker.py — Shared venue selection helpers cho tất cả generate scripts.
"""

from __future__ import annotations

import random
from pathlib import Path
from tools.venues_db import get_all, resolve_image

# Nhóm loại "chỗ chơi / check-in" dùng chung cho các slide không phải quán ăn/khách sạn.
CHECKIN_CATS = ("điểm checkin", "điểm checkin free", "điểm săn mây")
CHOI_CATS    = CHECKIN_CATS + ("quán cà phê",)

# ── Ảnh chung (data/album): dùng cho ảnh nền KHÔNG phải của quán, hoặc quán chưa có ảnh ──
_ALBUM_USED: set = set()


def _album_candidates() -> list:
    from tools import album_db
    root = Path(__file__).resolve().parent.parent
    out = []
    for im in album_db.get_all():
        p = root / im.get("file", "")
        if p.exists():
            out.append(str(p))
    return out


def album_bg() -> str:
    """Random 1 ảnh từ kho ảnh chung, KHÔNG trùng ảnh đã dùng trong lần chạy này
    (mỗi album chạy 1 process riêng nên set reset theo từng album)."""
    cands = _album_candidates()
    if not cands:
        return ""
    fresh = [p for p in cands if p not in _ALBUM_USED]
    if not fresh:
        _ALBUM_USED.clear()
        fresh = cands
    p = random.choice(fresh)
    _ALBUM_USED.add(p)
    return p


class VenuePicker:
    def __init__(self, seed: int | None = None):
        self._all = get_all()
        if seed is not None:
            random.seed(seed)
        self._used: set = set()

    def reset_used(self):
        self._used = set()

    @staticmethod
    def is_seeding(v: dict) -> bool:
        """Quán 'cần seeding' (quán mình + đối tác) cần ưu tiên lên đầu poster."""
        return (v.get("loai") or "").strip().lower() == "cần seeding"

    @staticmethod
    def seeding_first(venues: list) -> list:
        """Đưa quán seeding lên ĐẦU, phần còn lại giữ nguyên thứ tự."""
        seed = [v for v in venues if VenuePicker.is_seeding(v)]
        rest = [v for v in venues if not VenuePicker.is_seeding(v)]
        return seed + rest

    def _pool(self, co_nguoi: str | None = None, loai_quan: str | None = None,
              exclude: set | None = None) -> list:
        pool = self._all
        if co_nguoi:
            pool = [v for v in pool if v.get("co_nguoi") == co_nguoi]
        if loai_quan:
            if isinstance(loai_quan, str):
                pool = [v for v in pool if v.get("loai_quan") == loai_quan]
            else:
                pool = [v for v in pool if v.get("loai_quan") in loai_quan]
        ex = (exclude or set()) | self._used
        avail = [v for v in pool if v["name"] not in ex]
        return avail if avail else pool

    def pick_one(self, co_nguoi: str | None = None,
                 loai_quan: str | list | None = None,
                 exclude: set | None = None,
                 track: bool = True) -> dict | None:
        pool = self._pool(co_nguoi, loai_quan, exclude)
        if not pool:
            return None
        v = random.choice(pool)
        if track:
            self._used.add(v["name"])
        return v

    def pick_n(self, n: int, co_nguoi: str | None = None,
               loai_quan: str | list | None = None,
               unique: bool = True, seeding_first: bool = True) -> list:
        """Chọn n venue. seeding_first=True (mặc định): quán 'cần seeding' (quán mình + đối tác)
        lên ĐẦU danh sách, phần còn lại chọn ngẫu nhiên — để poster quán/khách sạn ưu tiên seeding.
        Loại không có quán seeding (tham quan, cà phê...) thì tự động về chọn ngẫu nhiên như cũ."""
        result = []
        if seeding_first:
            seed = [v for v in self._pool(co_nguoi, loai_quan) if VenuePicker.is_seeding(v)]
            random.shuffle(seed)
            for v in seed[:n]:
                result.append(v)
                if unique:
                    self._used.add(v["name"])
        for _ in range(n - len(result)):
            v = self.pick_one(co_nguoi, loai_quan, track=unique)
            if v:
                result.append(v)
        return result

    def pick_category_rotation(self, n: int,
                                categories: list | None = None,
                                co_nguoi: str | None = None) -> list:
        """Pick n venues rotating through loai_quan categories."""
        cats = categories or ["quán ăn", "quán cà phê", "khách sạn", "điểm checkin"]
        result = []
        for i in range(n):
            cat = cats[i % len(cats)]
            v = self.pick_one(co_nguoi, cat)
            if v:
                result.append(v)
        return result

    @staticmethod
    def album_bg() -> str:
        """Ảnh nền chung không trùng — dùng cho ảnh KHÔNG phải của quán."""
        return album_bg()

    @staticmethod
    def image(venue: dict) -> str:
        """Ảnh của venue — chọn NGẪU NHIÊN trong bộ ảnh (theo seed của script) để
        mỗi lần tạo album ảnh nền khác nhau, thay vì luôn lấy ảnh đầu.
        Quán chưa có ảnh (status none) → lấy ảnh chung."""
        root = Path(__file__).resolve().parent.parent
        cands = []
        for i in (venue.get("images") or []):
            s = str(i).strip()
            if not s or s.startswith("http"):
                continue
            p = Path(s)
            if not p.is_absolute():
                p = root / s
            if p.exists():
                cands.append(str(p))
        if cands:
            return random.choice(cands)
        return resolve_image(venue) or album_bg()
