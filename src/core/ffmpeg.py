# ffmpeg.py
"""ffmpeg/ffprobe 탐색과 실행, 동영상 정보 조회, 프레임 추출을 담당합니다."""
from __future__ import annotations

import functools
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
from .color import SDR, ColorInfo, from_probe, to_rgb_filter, tonemap_filter

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


@functools.lru_cache(maxsize=4)
def filters(ffmpeg: str) -> frozenset[str]:
    """이 ffmpeg가 가진 필터 이름들. (시스템 PATH의 ffmpeg는 빌드에 따라 zscale 등이 없을 수 있음)"""
    try:
        text = run([ffmpeg, "-hide_banner", "-filters"], timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return frozenset()
    return frozenset(parts[1] for parts in map(str.split, text.splitlines())
                     if len(parts) >= 3 and "->" in parts[2])


def can_tonemap(ffmpeg: str) -> bool:
    """HDR 영상을 SDR로 바꿀 수 있는지. (zscale은 libzimg가 들어간 빌드에만 있습니다. gyan.dev 빌드는 있음)"""
    names = filters(ffmpeg)
    return "zscale" in names and "tonemap" in names


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
    color: ColorInfo = SDR

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
    return VideoInfo(path, duration, width, height, fps if fps < 1000 else 0.0, stream.get("codec_name") or "",
                     from_probe(stream, width, height))


def probe_video(ffprobe: str, path: str, *, timeout: float = 30) -> VideoInfo:
    """ffprobe로 첫 번째 비디오 스트림의 길이, 크기, 프레임 레이트를 읽습니다."""
    proc = run([ffprobe, "-v", "error", "-select_streams", "v:0",
                "-show_format", "-show_streams", "-of", "json", path], timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "ffprobe failed")
    return parse_probe_json(path, proc.stdout)


# --- 프레임 추출 ---

JPEG_COLOR = ("-colorspace", "bt470bg", "-color_range", "pc")    # JPEG 규격: BT.601 행렬, 0~255

def preview_filter(max_w: int, max_h: int, color: ColorInfo, tonemap: bool) -> str:
    """미리보기 프레임: max_w×max_h 안에 맞춰 줄이고 원본 행렬로 RGB를 만듭니다. HDR은 GIF와 같이 톤매핑합니다.

    JPEG로 바꿀 때의 행렬은 grab_frame이 JPEG 규격(BT.601, 0~255)으로 못 박습니다. Qt는 JPEG를 늘 BT.601로 읽는데,
    ffmpeg 7.1부터는 원본 태그(BT.709)를 이어 받아 변환하기 때문입니다. (실측: Qt로 읽은 색 차이 ΔE 5.1 → 0.9)
    """
    fit = f"scale=w={max_w}:h={max_h}:force_original_aspect_ratio=decrease:flags=bilinear"
    if tonemap:
        return f"{fit},format=yuv444p10le,{tonemap_filter(color)},{to_rgb_filter('bt709', 'pc', 'rgb24')}"
    return f"{fit}:in_color_matrix={color.yuv_matrix}:in_range={color.yuv_range},format=rgb24"


def grab_frame(ffmpeg: str, path: str, ts: float, max_w: int, max_h: int, *, color: ColorInfo = SDR,
               quality: int = 3, timeout: float = 30, cancel: threading.Event | None = None) -> bytes:
    """지정한 시각의 프레임을 비율을 유지한 채 max_w×max_h 안에 맞춰 JPEG 바이트로 반환합니다.

    마지막 프레임 이후를 탐색하면 프레임이 나오지 않으므로, 결과가 비면 조금 앞에서 다시 시도합니다.
    cancel이 켜지면 추출 중인 ffmpeg를 끝내고 Cancelled를 냅니다.
    """
    vf = preview_filter(max_w, max_h, color, bool(color.hdr) and can_tonemap(ffmpeg))
    for attempt_ts in (max(0.0, ts), max(0.0, ts - 0.5), max(0.0, ts - 2.0)):
        proc = run([ffmpeg, "-hide_banner", "-nostdin", "-loglevel", "error",
                    "-ss", f"{attempt_ts:.3f}", "-i", path, "-an", "-sn", "-dn",
                    "-frames:v", "1", "-vf", vf, *JPEG_COLOR,
                    "-f", "image2pipe", "-c:v", "mjpeg", "-q:v", str(quality), "-"],
                   timeout=timeout, binary=True, cancel=cancel)
        if proc.stdout:
            return proc.stdout
        if attempt_ts == 0.0:
            break
    message = proc.stderr.decode("utf-8", "replace").strip() if proc.stderr else ""
    raise RuntimeError(message or f"no frame at {ts:.3f}s")


CLIP_MAX_SIDE = 1920    # 구간 재생용 영상의 긴 변 최대 길이. 4K를 그대로 다시 압축하면 느리고 파일이 큽니다.


def clip_filter(color: ColorInfo, tonemap: bool) -> str:
    side = CLIP_MAX_SIDE
    fit = (f"scale=w='if(gte(iw,ih),min({side},iw),-2)':h='if(gte(iw,ih),-2,min({side},ih))':flags=bicubic")
    return f"{fit},{tonemap_filter(color, out_range='tv')}" if tonemap else fit


def export_clip(ffmpeg: str, path: str, start: float, length: float, output: str | Path, *,
                color: ColorInfo = SDR, timeout: float = 300,
                cancel: threading.Event | None = None) -> subprocess.CompletedProcess:
    """구간 재생용 MP4를 만듭니다. 키프레임에 끌려가지 않도록 스트림 복사 대신 빠르게 재인코딩합니다.
    긴 변은 CLIP_MAX_SIDE까지 줄이고, HDR은 GIF와 같은 색으로 보이도록 SDR로 톤매핑합니다."""
    tonemap = bool(color.hdr) and can_tonemap(ffmpeg)
    tags = ["-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709"] if tonemap else []
    return run([ffmpeg, "-hide_banner", "-nostdin", "-loglevel", "error",
                "-ss", f"{start:.3f}", "-t", f"{length:.3f}", "-i", path,
                "-map", "0:v:0", "-map", "0:a:0?", "-vf", clip_filter(color, tonemap),
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "20", "-pix_fmt", "yuv420p", *tags,
                "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
                "-y", str(output)], timeout=timeout, cancel=cancel)
