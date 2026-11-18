# timecode.py
"""시간 문자열 표시와 파싱을 담당합니다."""
from __future__ import annotations

import math


def format_time(seconds: float, *, force_hours: bool = False) -> str:
    """초를 `mm:ss.mmm` 또는 `hh:mm:ss.mmm` 형식으로 바꿉니다.

    밀리초 단위로 먼저 반올림하므로 59.9996초가 "00:60.000"처럼 표시되지 않습니다.
    """
    total_ms = max(0, int(round(seconds * 1000)))
    hours, rem = divmod(total_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, ms = divmod(rem, 1000)
    if hours or force_hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{ms:03d}"
    return f"{minutes:02d}:{secs:02d}.{ms:03d}"


def format_seconds(seconds: float, decimals: int = 2) -> str:
    """구간 길이처럼 짧은 시간을 `3.50` 형태로 바꿉니다. (단위는 호출하는 쪽에서 붙임)"""
    return f"{max(0.0, seconds):.{decimals}f}"


def parse_time(text: str) -> float:
    """사용자가 입력한 시간을 초로 바꿉니다.

    허용 형식: `90`, `90.5`, `1:30`, `01:30.250`, `1:02:03.5`, `3.5s`, 소수점 쉼표(`1,5`).
    콜론 형식에서 초는 60 미만, 시·분·초 형식에서 분도 60 미만이어야 합니다.
    잘못된 입력이면 ValueError를 발생시킵니다.
    """
    s = (text or "").strip().lower().replace(",", ".")
    if s.endswith("s"):
        s = s[:-1].strip()
    if not s:
        raise ValueError("empty time")

    parts = s.split(":")
    if len(parts) > 3:
        raise ValueError(f"invalid time: {text!r}")
    try:
        head = [int(p) for p in parts[:-1]]
        last = float(parts[-1])
    except ValueError:
        raise ValueError(f"invalid time: {text!r}") from None

    if not math.isfinite(last) or last < 0 or any(v < 0 for v in head):
        raise ValueError(f"invalid time: {text!r}")
    if len(parts) >= 2 and last >= 60:
        raise ValueError(f"seconds must be < 60: {text!r}")
    if len(parts) == 3 and head[1] >= 60:
        raise ValueError(f"minutes must be < 60: {text!r}")

    total = 0.0
    for value in head:
        total = total * 60 + value
    return total * 60 + last if head else last
