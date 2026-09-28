# encoder.py
"""2-pass GIF 인코딩을 실행합니다. 진행률 보고와 다른 스레드에서의 취소를 지원합니다."""
from __future__ import annotations

import collections
import os
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
from .gif import GifOptions, build_gif_command, build_palette_command
from .gifinfo import GifInfo, read_gif_info

StageFn = Callable[[str], None]        # "palette" → "encode"
ProgressFn = Callable[[float], None]   # 0.0 ~ 1.0 (GIF 변환 단계)
LogFn = Callable[[str], None]


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

        full = [cmd[0], "-progress", "pipe:1", "-nostats", *cmd[1:]]
        with self._lock:
            proc = subprocess.Popen(full, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    text=True, encoding="utf-8", errors="replace", **popen_kwargs())
            self._proc = proc

        stdout, stderr = proc.stdout, proc.stderr
        if stdout is None or stderr is None:   # PIPE로 열었으므로 일어나지 않지만 타입을 좁힙니다.
            proc.kill()
            raise EncodeError("ffmpeg pipes are unavailable")

        # stderr 버퍼가 차서 멈추지 않도록 별도 스레드에서 비웁니다. (오류 메시지는 마지막 40줄만 보관)
        tail: collections.deque[str] = collections.deque(maxlen=40)
        drain = threading.Thread(target=lambda: tail.extend(line.rstrip() for line in stderr),
                                 daemon=True)
        drain.start()
        try:
            for line in stdout:
                if on_progress and length > 0 and line.startswith("out_time_us="):
                    try:
                        micros = int(line.split("=", 1)[1])
                    except ValueError:
                        continue
                    on_progress(min(1.0, max(0.0, micros / 1_000_000 / length)))
            code = proc.wait()
            drain.join(timeout=2)
        finally:
            with self._lock:
                self._proc = None
            stdout.close()
            stderr.close()

        if self._cancel.is_set():
            raise EncodeCancelled()
        if code != 0:
            raise EncodeError(f"ffmpeg exited with code {code}", "\n".join(tail))
        if on_progress:
            on_progress(1.0)
