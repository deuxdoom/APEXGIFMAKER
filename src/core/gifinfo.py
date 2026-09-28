# gifinfo.py
"""GIF 파일의 크기, 프레임 수, 재생 시간을 읽는 가벼운 파서입니다."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GifInfo:
    width: int
    height: int
    frames: int
    duration_ms: int      # 프레임 지연 시간의 합 (1/100초 단위를 ms로 환산)
    loop: int | None      # 0 = 무한 반복, None = 반복 정보 없음(한 번 재생)
    file_size: int


def _skip_sub_blocks(data: bytes, i: int) -> int:
    while True:
        size = data[i]
        i += 1
        if size == 0:
            return i
        i += size


def _color_table_size(packed: int) -> int:
    return 3 * (2 ** ((packed & 0x07) + 1)) if packed & 0x80 else 0


def parse_gif(data: bytes) -> GifInfo:
    if len(data) < 13 or data[:6] not in (b"GIF87a", b"GIF89a"):
        raise ValueError("not a GIF file")
    width = int.from_bytes(data[6:8], "little")
    height = int.from_bytes(data[8:10], "little")
    i = 13 + _color_table_size(data[10])

    frames = 0
    delay_cs = 0
    loop: int | None = None
    try:
        while i < len(data):
            marker = data[i]
            if marker == 0x21:                          # 확장 블록
                label = data[i + 1]
                i += 2
                if label == 0xF9 and data[i] >= 4:      # Graphic Control Extension
                    delay_cs += int.from_bytes(data[i + 2:i + 4], "little")
                elif label == 0xFF and data[i] == 11 and data[i + 1:i + 12] in (b"NETSCAPE2.0", b"ANIMEXTS1.0"):
                    sub = i + 12
                    if data[sub] >= 3 and data[sub + 1] == 1:
                        loop = int.from_bytes(data[sub + 2:sub + 4], "little")
                i = _skip_sub_blocks(data, i)
            elif marker == 0x2C:                        # Image Descriptor
                packed = data[i + 9]
                i += 10 + _color_table_size(packed)
                i += 1                                  # LZW 최소 코드 크기
                i = _skip_sub_blocks(data, i)
                frames += 1
            elif marker == 0x3B:                        # Trailer
                break
            else:
                raise ValueError(f"unexpected block 0x{marker:02x} at offset {i}")
    except IndexError:
        raise ValueError("truncated GIF file") from None

    return GifInfo(width, height, frames, delay_cs * 10, loop, len(data))


def read_gif_info(path: str | Path) -> GifInfo:
    return parse_gif(Path(path).read_bytes())
