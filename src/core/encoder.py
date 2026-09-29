# encoder.py
"""GIF 인코딩을 실행합니다. 진행률 보고와 다른 스레드에서의 취소를 지원합니다.

- 1-pass: 영상을 한 번만 읽어 팔레트 생성과 변환을 함께 합니다. 메모리가 넉넉할 때(gif.uses_one_pass) 씁니다.
- 2-pass: 팔레트를 먼저 만들고(1단계) 다시 읽어 변환합니다(2단계). 크거나 긴 GIF에 씁니다.
두 방식의 결과 파일은 같습니다. 진행률은 ffmpeg 로그의 showinfo 줄(중복 제거 전 원본 기준 시각)로 계산하므로
중복 제거 모드에서도 실제 처리 위치를 따라갑니다. (-progress는 출력 기준이라 정지 구간이 접히면 덜 올라가고,
1-pass에서는 GIF를 쓰기 시작할 때까지 아예 나오지 않습니다.)
"""
from __future__ import annotations

import collections
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import config
from .ffmpeg import popen_kwargs
from .gif import GifOptions, build_gif_command, build_one_pass_command, build_palette_command, uses_one_pass
from .gifinfo import GifInfo, read_gif_info

StageFn = Callable[[str], None]        # 2-pass: "palette" → "encode", 1-pass: "encode"
ProgressFn = Callable[[float], None]   # 0.0 ~ 1.0 (GIF 변환 단계)
LogFn = Callable[[str], None]

_PTS_TIME = re.compile(r"\bpts_time:(-?\d+(?:\.\d+)?)")
_LEVEL = re.compile(r"\[(panic|fatal|error|warning|info|verbose|debug|trace)\] ")
_KEPT_LEVELS = frozenset({"panic", "fatal", "error"})


def parse_log_line(line: str) -> tuple[float | None, str]:
    """ffmpeg 로그 한 줄을 (showinfo의 원본 기준 시각, 오류로 남길 글)로 나눕니다. 해당 없으면 None·빈 문자열입니다.

    등급 표시(level+)가 붙은 줄은 오류 등급만 남기고, 표시가 없는 줄은 형식이 바뀌었을 수 있으니 그대로 남깁니다.
    """
    text = line.rstrip()
    if "showinfo" in text:
        match = _PTS_TIME.search(text)
        if match:
            return float(match.group(1)), ""
    level = _LEVEL.search(text)
    if level is None:
        return None, text
    if level.group(1) not in _KEPT_LEVELS:
        return None, ""
    return None, (text[:level.start()] + text[level.end():]).strip()


class EncodeCancelled(Exception):
    pass


class EncodeError(RuntimeError):
    def __init__(self, message: str, details: str = ""):
        super().__init__(message)
        self.details = details


@dataclass(frozen=True)
class EncodeResult:
    path: str
    info: GifInfo | None
    elapsed: float


class GifEncoder:
    """출력은 `<파일>.part`에 먼저 쓰고, 성공했을 때만 목표 파일로 교체합니다."""

    def __init__(self, ffmpeg: str, source: str, start: float, end: float,
                 options: GifOptions, output: str | Path):
        if end <= start:
            raise ValueError("invalid time range")
        self.ffmpeg = ffmpeg
        self.source = source
        self.start = start
        self.end = end
        self.options = options
        self.output = Path(output)
        self._cancel = threading.Event()
        self._lock = threading.Lock()
        self._proc: subprocess.Popen | None = None

    @property
    def cancelled(self) -> bool:
        return self._cancel.is_set()

    def cancel(self) -> None:
        self._cancel.set()
        with self._lock:
            if self._proc is not None and self._proc.poll() is None:
                try:
                    self._proc.terminate()
                except OSError:
                    pass

    def run(self, *, on_stage: StageFn | None = None, on_progress: ProgressFn | None = None,
            on_log: LogFn | None = None) -> EncodeResult:
        started = time.monotonic()
        length = self.end - self.start
        self.output.parent.mkdir(parents=True, exist_ok=True)
        work = Path(tempfile.mkdtemp(prefix="encode-", dir=config.temp_dir()))
        part = self.output.with_name(self.output.name + ".part")
        try:
            if uses_one_pass(length, self.options):
                if on_stage:
                    on_stage("encode")
                self._run(build_one_pass_command(self.ffmpeg, self.source, self.start, length,
                                                 self.options, part), length, on_progress, on_log)
            else:
                palette = work / "palette.png"
                if on_stage:
                    on_stage("palette")
                self._run(build_palette_command(self.ffmpeg, self.source, self.start, length,
                                                self.options, palette), length, None, on_log)
                if not palette.is_file():
                    raise EncodeError("palette was not created")
                if on_stage:
                    on_stage("encode")
                self._run(build_gif_command(self.ffmpeg, self.source, self.start, length,
                                            self.options, palette, part), length, on_progress, on_log)
            if not part.is_file() or part.stat().st_size == 0:
                raise EncodeError("output file was not created")
            os.replace(part, self.output)
        finally:
            shutil.rmtree(work, ignore_errors=True)
            try:
                part.unlink(missing_ok=True)
            except OSError:
                pass

        try:
            info = read_gif_info(self.output)
        except (OSError, ValueError):
            info = None
        return EncodeResult(str(self.output), info, time.monotonic() - started)

    def _run(self, cmd: list[str], length: float, on_progress: ProgressFn | None,
             on_log: LogFn | None) -> None:
        if self._cancel.is_set():
            raise EncodeCancelled()
        if on_log:
            on_log("[RUN] " + subprocess.list2cmdline(cmd))

        with self._lock:
            proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                    text=True, encoding="utf-8", errors="replace", **popen_kwargs())
            self._proc = proc

        stderr = proc.stderr
        if stderr is None:   # PIPE로 열었으므로 일어나지 않지만 타입을 좁힙니다.
            proc.kill()
            raise EncodeError("ffmpeg pipes are unavailable")

        # 진행률은 1% 단위로만 알리고, 오류 메시지는 마지막 40줄만 보관합니다.
        tail: collections.deque[str] = collections.deque(maxlen=40)
        shown = -1
        try:
            for line in stderr:
                seconds, message = parse_log_line(line)
                if seconds is not None:
                    percent = int(min(1.0, max(0.0, seconds / length)) * 100) if length > 0 else 0
                    if on_progress and percent > shown:
                        shown = percent
                        on_progress(percent / 100)
                elif message:
                    tail.append(message)
            code = proc.wait()
        finally:
            with self._lock:
                self._proc = None
            stderr.close()

        if self._cancel.is_set():
            raise EncodeCancelled()
        if code != 0:
            raise EncodeError(f"ffmpeg exited with code {code}", "\n".join(tail))
        if on_progress:
            on_progress(1.0)
