# ffmpeg.py
"""ffmpeg/ffprobe 탐색과 실행, 동영상 정보 조회, 프레임 추출을 담당합니다."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from . import config

CANCEL_POLL = 0.05     # 취소 신호를 확인하는 간격(초)


class Cancelled(Exception):
    """취소 신호(threading.Event)를 받아 실행 중인 외부 명령을 멈췄습니다."""


def exe_name(name: str) -> str:
    return name + (".exe" if os.name == "nt" else "")


def search_dirs() -> list[Path]:
    """ffmpeg를 찾는 폴더 순서: 실행 폴더의 bin → 데이터 폴더의 bin → (v2.x) ffmpeg-bin"""
    dirs: list[Path] = []
    for folder in (config.APP_DIR / config.TOOLS_DIR_NAME, config.tools_dir(), config.legacy_ffmpeg_dir()):
        if folder not in dirs:
            dirs.append(folder)
    return dirs


def is_managed(path: str) -> bool:
    """앱이 직접 관리하는(bin 폴더에 받아 둔) ffmpeg인지. 시스템에 설치된 ffmpeg는 업데이트하지 않습니다."""
    if not path:
        return False
    parent = Path(path).resolve().parent
    return any(parent == folder.resolve() for folder in search_dirs())


def find_executable(name: str) -> str:
    """bin 폴더를 먼저 찾고, 없으면 시스템 PATH에서 찾습니다. 못 찾으면 빈 문자열입니다."""
    for folder in search_dirs():
        candidate = folder / exe_name(name)
        if candidate.is_file():
            return str(candidate)
    return shutil.which(name) or ""


def popen_kwargs() -> dict:
    """Windows에서 콘솔 창이 깜빡이지 않도록 하는 subprocess 옵션입니다."""
    kwargs: dict = {"stdin": subprocess.DEVNULL}
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = 0  # SW_HIDE
        kwargs["startupinfo"] = startup
    return kwargs


def run(cmd: list[str], *, timeout: float | None = None, binary: bool = False,
        cancel: threading.Event | None = None) -> subprocess.CompletedProcess:
    """외부 명령을 창 없이 실행하고 출력을 모아서 반환합니다.

    cancel을 주면 실행 중에도 신호를 확인해서, 켜지면 프로세스를 끝내고 Cancelled를 냅니다.
    시간 초과는 subprocess.run과 같이 TimeoutExpired입니다.
    """
    kwargs = popen_kwargs()
    if not binary:
        kwargs.update(text=True, encoding="utf-8", errors="replace")
    if cancel is None:
        return subprocess.run(cmd, capture_output=True, timeout=timeout, **kwargs)
    if cancel.is_set():
        raise Cancelled()
    deadline = None if timeout is None else time.monotonic() + timeout
    with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs) as proc:
        while True:
            try:
                stdout, stderr = proc.communicate(timeout=CANCEL_POLL)
                return subprocess.CompletedProcess(cmd, proc.returncode, stdout, stderr)
            except subprocess.TimeoutExpired:
                expired = deadline is not None and time.monotonic() >= deadline
                if not (cancel.is_set() or expired):
                    continue
                proc.kill()
                proc.communicate()
                if cancel.is_set():
                    raise Cancelled() from None
                raise subprocess.TimeoutExpired(cmd, timeout or 0) from None


def ffmpeg_version(ffmpeg: str) -> str:
    """`ffmpeg -version` 첫 줄에서 버전 문자열만 뽑습니다. (예: 9.0.2-essentials_build-www.gyan.dev)"""
    try:
        first = run([ffmpeg, "-hide_banner", "-version"], timeout=10).stdout.splitlines()[0]
    except (OSError, subprocess.SubprocessError, IndexError):
        return ""
    parts = first.split()
    return parts[2] if len(parts) > 2 and parts[1] == "version" else first.strip()


def short_version(version: str) -> str:
    """`9.0.2-essentials_build-www.gyan.dev` → `9.0.2` (화면 표시용)"""
    return version.split("-", 1)[0] if version else ""


# --- 동영상 정보 ---

@dataclass(frozen=True)
class VideoInfo:
    path: str
    duration: float
    width: int = 0          # 회전 정보를 반영한 표시 크기
    height: int = 0
    fps: float = 0.0
    codec: str = ""

    @property
    def aspect(self) -> float:
        return self.width / self.height if self.width > 0 and self.height > 0 else 16 / 9

    @property
    def frame_step(self) -> float:
        """한 프레임의 길이(초). 프레임 레이트를 모르면 30fps로 가정합니다."""
        return 1.0 / self.fps if self.fps > 0 else 1 / 30


def _parse_rate(value: str | None) -> float:
    try:
        rate = Fraction(value or "0")
    except (ValueError, ZeroDivisionError):
        return 0.0
    return float(rate) if rate > 0 else 0.0


def _parse_float(value) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return number if number > 0 else 0.0


def _rotation(stream: dict) -> int:
    for side in stream.get("side_data_list") or []:
        if "rotation" in side:
            try:
                return int(float(side["rotation"]))
            except (TypeError, ValueError):
                pass
    try:
        return int((stream.get("tags") or {}).get("rotate", 0))
    except (TypeError, ValueError):
        return 0


def parse_probe_json(path: str, text: str) -> VideoInfo:
    data = json.loads(text or "{}")
    streams = data.get("streams") or []
    if not streams:
        raise ValueError("no video stream")
    stream = streams[0]
    duration = _parse_float((data.get("format") or {}).get("duration")) or _parse_float(stream.get("duration"))
    if duration <= 0:
        raise ValueError("unknown duration")

    width, height = int(stream.get("width") or 0), int(stream.get("height") or 0)
    if abs(_rotation(stream)) % 180 == 90:
        width, height = height, width
    fps = _parse_rate(stream.get("avg_frame_rate")) or _parse_rate(stream.get("r_frame_rate"))
    return VideoInfo(path, duration, width, height, fps if fps < 1000 else 0.0, stream.get("codec_name") or "")


def probe_video(ffprobe: str, path: str, *, timeout: float = 30) -> VideoInfo:
    """ffprobe로 첫 번째 비디오 스트림의 길이, 크기, 프레임 레이트를 읽습니다."""
    proc = run([ffprobe, "-v", "error", "-select_streams", "v:0",
                "-show_format", "-show_streams", "-of", "json", path], timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "ffprobe failed")
    return parse_probe_json(path, proc.stdout)


# --- 프레임 추출 ---

def grab_frame(ffmpeg: str, path: str, ts: float, max_w: int, max_h: int, *,
               quality: int = 3, timeout: float = 30, cancel: threading.Event | None = None) -> bytes:
    """지정한 시각의 프레임을 비율을 유지한 채 max_w×max_h 안에 맞춰 JPEG 바이트로 반환합니다.

    마지막 프레임 이후를 탐색하면 프레임이 나오지 않으므로, 결과가 비면 조금 앞에서 다시 시도합니다.
    cancel이 켜지면 추출 중인 ffmpeg를 끝내고 Cancelled를 냅니다.
    """
    vf = f"scale=w={max_w}:h={max_h}:force_original_aspect_ratio=decrease:flags=bilinear:out_range=full"
    for attempt_ts in (max(0.0, ts), max(0.0, ts - 0.5), max(0.0, ts - 2.0)):
        proc = run([ffmpeg, "-hide_banner", "-nostdin", "-loglevel", "error",
                    "-ss", f"{attempt_ts:.3f}", "-i", path, "-an", "-sn", "-dn",
                    "-frames:v", "1", "-vf", vf,
                    "-f", "image2pipe", "-c:v", "mjpeg", "-q:v", str(quality), "-"],
                   timeout=timeout, binary=True, cancel=cancel)
        if proc.stdout:
            return proc.stdout
        if attempt_ts == 0.0:
            break
    message = proc.stderr.decode("utf-8", "replace").strip() if proc.stderr else ""
    raise RuntimeError(message or f"no frame at {ts:.3f}s")


def export_clip(ffmpeg: str, path: str, start: float, length: float, output: str | Path,
                *, timeout: float = 300, cancel: threading.Event | None = None) -> subprocess.CompletedProcess:
    """구간 재생용 MP4를 만듭니다. 키프레임에 끌려가지 않도록 스트림 복사 대신 빠르게 재인코딩합니다."""
    return run([ffmpeg, "-hide_banner", "-nostdin", "-loglevel", "error",
                "-ss", f"{start:.3f}", "-t", f"{length:.3f}", "-i", path,
                "-map", "0:v:0", "-map", "0:a:0?",
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "20", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
                "-y", str(output)], timeout=timeout, cancel=cancel)
