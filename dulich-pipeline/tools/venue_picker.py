"""
venue_picker.py — Shared venue selection helpers cho tất cả generate scripts.
"""

from __future__ import annotations

import random
from tools.venues_db import get_all, resolve_image


class VenuePicker:
    def __init__(self, seed: int | None = None):
        self._all = get_all()
        if seed is not None:
            random.seed(seed)
        self._used: set = set()

    def reset_used(self):
        self._used = set()

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
               unique: bool = True) -> list:
        result = []
        for _ in range(n):
            v = self.pick_one(co_nguoi, loai_quan, track=unique)
            if v:
                result.append(v)
        return result

    def pick_category_rotation(self, n: int,
                                categories: list | None = None,
                                co_nguoi: str | None = None) -> list:
        """Pick n venues rotating through loai_quan categories."""
        cats = categories or ["quán ăn", "quán cà phê", "khách sạn", "tham quan"]
        result = []
        for i in range(n):
            cat = cats[i % len(cats)]
            v = self.pick_one(co_nguoi, cat)
            if v:
                result.append(v)
        return result

    @staticmethod
    def image(venue: dict) -> str:
        return resolve_image(venue)
