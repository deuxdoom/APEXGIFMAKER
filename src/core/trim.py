# trim.py
"""GIF로 만들 구간(시작~끝)의 제약 규칙입니다.

모든 시간은 초 단위이며, 결과는 밀리초로 반올림합니다.

- 드래그(drag_start / drag_end): 잡은 끝점만 움직이고, 최소·최대 길이에 닿으면 멈춥니다.
- 이동(move): 길이를 유지한 채 구간 전체를 옮깁니다.
- 입력(set_start / set_end / set_length): 값이 규칙에 맞으면 그 값만 바꾸고,
  맞지 않으면 길이를 유지한 채 구간을 옮깁니다.
"""
from __future__ import annotations

from dataclasses import dataclass

from .config import DEFAULT_SELECTION_SEC, TRIM_MAX_SEC, TRIM_MIN_SEC

_EPS = 1e-6


def _r(value: float) -> float:
    return round(value, 3)


def _clamp(value: float, lo: float, hi: float) -> float:
    return lo if value < lo else hi if value > hi else value


@dataclass(frozen=True)
class Selection:
    start: float
    end: float

    @property
    def length(self) -> float:
        return self.end - self.start

    def contains(self, t: float) -> bool:
        return self.start <= t <= self.end


@dataclass(frozen=True)
class TrimRules:
    duration: float
    min_len: float = TRIM_MIN_SEC
    max_len: float = TRIM_MAX_SEC

    def __post_init__(self) -> None:
        if not self.duration > 0:
            raise ValueError("duration must be positive")
        if not 0 < self.min_len <= self.max_len:
            raise ValueError("invalid length limits")

    # --- 실제로 적용되는 길이 제한 (영상이 최소 길이보다 짧은 경우 포함) ---
    @property
    def lo(self) -> float:
        return min(self.min_len, self.duration)

    @property
    def hi(self) -> float:
        return max(self.lo, min(self.max_len, self.duration))

    def is_valid_length(self, length: float) -> bool:
        return self.lo - _EPS <= length <= self.hi + _EPS

    # --- 생성·정규화 ---
    def initial(self, preferred: float = DEFAULT_SELECTION_SEC) -> Selection:
        return Selection(0.0, _r(_clamp(preferred, self.lo, self.hi)))

    def normalize(self, sel: Selection) -> Selection:
        length = _clamp(sel.length, self.lo, self.hi)
        start = _clamp(sel.start, 0.0, self.duration - length)
        return Selection(_r(start), _r(min(self.duration, start + length)))

    # --- 드래그 ---
    def drag_start(self, sel: Selection, t: float) -> Selection:
        lo_bound = max(0.0, sel.end - self.hi)
        hi_bound = max(lo_bound, sel.end - self.lo)
        return Selection(_r(_clamp(t, lo_bound, hi_bound)), sel.end)

    def drag_end(self, sel: Selection, t: float) -> Selection:
        hi_bound = min(self.duration, sel.start + self.hi)
        lo_bound = min(hi_bound, sel.start + self.lo)
        return Selection(sel.start, _r(_clamp(t, lo_bound, hi_bound)))

    def move(self, sel: Selection, new_start: float) -> Selection:
        length = _clamp(sel.length, self.lo, self.hi)
        start = _clamp(new_start, 0.0, self.duration - length)
        return Selection(_r(start), _r(start + length))

    # --- 직접 입력 ---
    def set_start(self, sel: Selection, t: float) -> Selection:
        t = _clamp(t, 0.0, self.duration)
        if self.is_valid_length(sel.end - t):
            return Selection(_r(t), sel.end)
        return self.move(sel, t)

    def set_end(self, sel: Selection, t: float) -> Selection:
        t = _clamp(t, 0.0, self.duration)
        if self.is_valid_length(t - sel.start):
            return Selection(sel.start, _r(t))
        return self.move(sel, t - sel.length)

    def set_length(self, sel: Selection, length: float) -> Selection:
        length = _clamp(length, self.lo, self.hi)
        start = min(sel.start, self.duration - length)
        return Selection(_r(max(0.0, start)), _r(max(0.0, start) + length))
