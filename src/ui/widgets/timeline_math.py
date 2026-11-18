# timeline_math.py
"""타임라인이 쓰는 계산 도우미: 눈금 간격, 눈금 표기, 필름스트립 칸 길이, 썸네일 캐시."""
from __future__ import annotations

import bisect
import math
from collections import OrderedDict

from PySide6.QtGui import QPixmap

RULER_STEPS = (0.1, 0.2, 0.5, 1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 900, 1800, 3600, 7200)
# 필름스트립 한 칸의 길이는 이 값들 중에서 고릅니다. 확대 비율이 조금 바뀌어도 칸의 시각이 같게 유지되어
# 이미 받아 둔 썸네일을 다시 쓸 수 있습니다.
_TILE_BASE = (1.0, 1.5, 2.0, 3.0, 5.0, 7.5)


def ruler_step(pixels_per_second: float, min_gap: float = 90.0) -> float:
    for step in RULER_STEPS:
        if step * pixels_per_second >= min_gap:
            return float(step)
    return float(RULER_STEPS[-1])


def minor_step(step: float, pixels_per_second: float, min_gap: float = 8.0) -> float:
    for divisor in (5, 2):
        if step / divisor * pixels_per_second >= min_gap:
            return step / divisor
    return 0.0


def format_tick(t: float, step: float, long_video: bool) -> str:
    """눈금 표기: 1초보다 촘촘하면 `0:03.5`, 1시간 이상 영상이면 `1:02:03`, 그 밖에는 `2:05`."""
    if step < 1:
        tenths = int(round(t * 10))
        minutes, rem = divmod(tenths, 600)
        return f"{minutes}:{rem // 10:02d}.{rem % 10}"
    total = int(round(t))
    hours, rem = divmod(total, 3600)
    minutes, seconds = divmod(rem, 60)
    if long_video:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{hours * 60 + minutes}:{seconds:02d}"


def tile_span(nominal: float, frame_step: float) -> float:
    """칸 하나가 맡을 시간(초)을 1-1.5-2-3-5-7.5 × 10ⁿ 가운데 nominal보다 크거나 같은 값으로 고릅니다."""
    nominal = max(nominal, frame_step, 0.01)
    exponent = math.floor(math.log10(nominal))
    for power in (exponent, exponent + 1):
        for base in _TILE_BASE:
            value = base * (10 ** power)
            if value >= nominal - 1e-9:
                return value
    return nominal


class ThumbCache:
    """시각(ms) → 썸네일. 정확한 칸이 아직 없으면 가장 가까운 썸네일을 임시로 보여 줄 수 있습니다."""

    def __init__(self, limit: int = 600):
        self.limit = limit
        self._items: OrderedDict[int, QPixmap] = OrderedDict()
        self._keys: list[int] = []

    def clear(self) -> None:
        self._items.clear()
        self._keys.clear()

    def __len__(self) -> int:
        return len(self._items)

    def put(self, ms: int, pixmap: QPixmap) -> None:
        if ms not in self._items:
            bisect.insort(self._keys, ms)
        self._items[ms] = pixmap
        self._items.move_to_end(ms)
        while len(self._items) > self.limit:
            old, _ = self._items.popitem(last=False)
            index = bisect.bisect_left(self._keys, old)
            if index < len(self._keys) and self._keys[index] == old:
                self._keys.pop(index)

    def get(self, ms: int) -> QPixmap | None:
        pixmap = self._items.get(ms)
        if pixmap is not None:
            self._items.move_to_end(ms)
        return pixmap

    def nearest(self, ms: int, max_distance: float) -> QPixmap | None:
        if not self._keys:
            return None
        index = bisect.bisect_left(self._keys, ms)
        candidates = [self._keys[i] for i in (index - 1, index) if 0 <= i < len(self._keys)]
        best = min(candidates, key=lambda key: abs(key - ms))
        return self._items.get(best) if abs(best - ms) <= max_distance else None
