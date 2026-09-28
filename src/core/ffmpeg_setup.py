# ffmpeg_setup.py
"""ffmpeg·ffprobe(영상 변환 도구)를 준비하고 최신 상태로 유지합니다.

- 없으면 Windows용 공식 빌드를 내려받아 bin 폴더에 넣습니다. SHA-256 체크섬이 맞는 파일만 씁니다.
- 새 버전이 있으면 `ffmpeg.exe.new`처럼 이름을 바꿔 받아 두었다가 적용합니다. 실행 중이라 바꿀 수 없으면
  다음 실행 때(ffmpeg를 쓰기 전에) 적용합니다.
- bin 폴더에는 앱 실행 파일도 함께 있으므로, 이 모듈은 ffmpeg·ffprobe 두 파일 외에는 건드리지 않습니다.
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import tempfile
import threading
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import config
from ..i18n import tr
from .ffmpeg import exe_name, ffmpeg_version, find_executable, is_managed, short_version

LogFn = Callable[[str], None]
ProgressFn = Callable[[int, int], None]   # (받은 바이트, 전체 바이트 — 모르면 0)

GYAN_RELEASE = ("https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip",
                "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip.sha256")
BTBN_MASTER = ("https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip",
               "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/checksums.sha256")
RELEASE_VERSION_URL = "https://www.gyan.dev/ffmpeg/builds/release-version"
STAGED_SUFFIX = ".new"
CHUNK = 256 * 1024
_VERSION_RE = re.compile(r"\d+(?:\.\d+)*")


class SetupCancelled(Exception):
    pass


def _noop(*_args) -> None:
    pass


def tool_names() -> tuple[str, str]:
    return exe_name("ffmpeg"), exe_name("ffprobe")


def tools_ready() -> bool:
    return bool(find_executable("ffmpeg") and find_executable("ffprobe"))


# --- 준비 ---

def ensure_ffmpeg(log: LogFn = _noop, progress: ProgressFn | None = None,
                  cancel: threading.Event | None = None) -> bool:
    """ffmpeg/ffprobe를 찾고, 없으면 내려받습니다. 준비되면 True를 반환합니다."""
    if tools_ready():
        return True
    if os.name != "nt":
        log("[WARN] " + tr("ffmpeg.unsupported_os"))
        return False
    target = config.tools_dir()
    for url, checksum_url in (GYAN_RELEASE, BTBN_MASTER):
        try:
            install_from_zip(url, checksum_url, target, log, progress, cancel)
        except SetupCancelled:
            raise
        except Exception as exc:  # 네트워크·압축 오류는 다음 미러로 넘어갑니다.
            log("[ERR] " + tr("ffmpeg.download_failed", error=exc))
            continue
        if tools_ready():
            log("[OK] " + tr("ffmpeg.installed", path=target))
            return True
    log("[ERR] " + tr("ffmpeg.setup_failed"))
    return False


def install_from_zip(url: str, checksum_url: str, target: Path, log: LogFn, progress: ProgressFn | None,
                     cancel: threading.Event | None, suffix: str = "") -> None:
    """ZIP을 받아 SHA-256을 확인하고 ffmpeg·ffprobe만 target에 꺼냅니다. suffix를 주면 그 이름으로 받아 둡니다."""
    log("[DL] " + tr("ffmpeg.downloading", url=url))
    fd, tmp_name = tempfile.mkstemp(prefix="ffmpeg-", suffix=".zip", dir=config.temp_dir())
    os.close(fd)
    archive = Path(tmp_name)
    try:
        # 체크섬을 먼저 받아 둡니다. 확인할 수 없는 파일은 쓰지 않습니다(SHA-256 필수).
        expected = _fetch_checksum(checksum_url, url.rsplit("/", 1)[-1])
        if not expected:
            raise RuntimeError(tr("ffmpeg.no_checksum"))
        digest = _download(url, archive, progress, cancel)
        if expected != digest:
            raise RuntimeError(tr("ffmpeg.verify_fail"))
        log("[OK] " + tr("ffmpeg.verify_ok"))
        log("[INFO] " + tr("ffmpeg.extracting"))
        extract_binaries(archive, target, suffix)
    finally:
        archive.unlink(missing_ok=True)


def _open(url: str, timeout: float = 30):
    request = urllib.request.Request(url, headers={"User-Agent": config.USER_AGENT})
    return urllib.request.urlopen(request, timeout=timeout)


def _download(url: str, dest: Path, progress: ProgressFn | None, cancel: threading.Event | None) -> str:
    """파일을 받으면서 SHA-256을 함께 계산해서 반환합니다."""
    sha = hashlib.sha256()
    with _open(url) as resp, open(dest, "wb") as out:
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        while True:
            if cancel is not None and cancel.is_set():
                raise SetupCancelled()
            chunk = resp.read(CHUNK)
            if not chunk:
                break
            out.write(chunk)
            sha.update(chunk)
            done += len(chunk)
            if progress:
                progress(done, total)
    return sha.hexdigest()


def parse_checksum(text: str, filename: str) -> str:
    """`<hash>` 한 줄 또는 `<hash>  <파일명>` 목록 형식에서 해당 파일의 SHA-256을 찾습니다."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines:
        parts = line.split()
        if len(parts) >= 2 and parts[-1].lstrip("*") == filename and len(parts[0]) == 64:
            return parts[0].lower()
    if len(lines) == 1 and len(lines[0].split()[0]) == 64:
        return lines[0].split()[0].lower()
    return ""


def _fetch_checksum(url: str, filename: str) -> str:
    try:
        with _open(url, timeout=15) as resp:
            return parse_checksum(resp.read().decode("utf-8", "replace"), filename)
    except Exception:
        return ""


def extract_binaries(archive: Path, target: Path, suffix: str = "") -> None:
    """압축 파일에서 bin/ffmpeg.exe, bin/ffprobe.exe만 꺼냅니다. (다른 파일은 건드리지 않음)"""
    wanted = set(tool_names())
    with zipfile.ZipFile(archive) as zf:
        members = {}
        for info in zf.infolist():
            path = "/" + info.filename.replace("\\", "/").lower()
            name = path.rsplit("/", 1)[-1]
            if name in wanted and "/bin/" in path:
                members[name] = info
        missing = wanted - members.keys()
        if missing:
            raise RuntimeError("missing in archive: " + ", ".join(sorted(missing)))
        target.mkdir(parents=True, exist_ok=True)
        for name, info in members.items():
            part = target / (name + ".part")
            with zf.open(info) as src, open(part, "wb") as dst:
                shutil.copyfileobj(src, dst, 1024 * 1024)
            os.replace(part, target / (name + suffix))


# --- 예전 폴더 옮기기, 받아 둔 새 버전 적용 ---

def migrate_legacy_dir() -> bool:
    """v2.x의 ffmpeg-bin에 있던 ffmpeg·ffprobe를 bin으로 옮깁니다. 옮겼으면 True입니다."""
    legacy, target = config.legacy_ffmpeg_dir(), config.tools_dir()
    names = tool_names()
    if not all((legacy / name).is_file() for name in names) or all((target / n).is_file() for n in names):
        return False
    target.mkdir(parents=True, exist_ok=True)
    try:
        for name in names:
            os.replace(legacy / name, target / name)
    except OSError:
        return False
    for leftover in ("ffmpeg-download.zip",):
        (legacy / leftover).unlink(missing_ok=True)
    try:
        legacy.rmdir()   # 비어 있을 때만 지워집니다.
    except OSError:
        pass
    return True


def has_staged(target: Path | None = None) -> bool:
    folder = target or config.tools_dir()
    return all((folder / (name + STAGED_SUFFIX)).is_file() for name in tool_names())


def apply_staged(target: Path | None = None) -> bool:
    """받아 둔 새 버전(.new)을 제자리에 적용합니다. ffmpeg가 실행 중이라 바꿀 수 없으면 False입니다."""
    folder = target or config.tools_dir()
    if not has_staged(folder):
        return False
    try:
        for name in tool_names():
            os.replace(folder / (name + STAGED_SUFFIX), folder / name)
    except OSError:
        return False
    return True


# --- 새 버전 확인과 업데이트 ---

def version_tuple(text: str) -> tuple[int, ...] | None:
    match = _VERSION_RE.match((text or "").strip())
    return tuple(int(part) for part in match.group(0).split(".")) if match else None


def latest_release_version(timeout: float = 10) -> str:
    """공식 빌드(gyan.dev)의 최신 릴리즈 버전 번호. (예: 9.0.2)"""
    with _open(RELEASE_VERSION_URL, timeout=timeout) as resp:
        text = resp.read(64).decode("utf-8", "replace").strip()
    if version_tuple(text) is None:
        raise ValueError(f"unexpected version text: {text!r}")
    return text


@dataclass(frozen=True)
class ToolStatus:
    installed: str     # 지금 쓰는 버전 (모르면 빈 문자열)
    latest: str        # 공식 빌드의 최신 버전
    managed: bool      # 앱의 bin 폴더에 있는 ffmpeg인지 (시스템 ffmpeg는 건드리지 않음)

    @property
    def newer(self) -> bool:
        latest, installed = version_tuple(self.latest), version_tuple(self.installed)
        return latest is not None and (installed is None or latest > installed)


def check_tools() -> ToolStatus:
    ffmpeg_path = find_executable("ffmpeg")
    installed = short_version(ffmpeg_version(ffmpeg_path)) if ffmpeg_path else ""
    return ToolStatus(installed, latest_release_version(), is_managed(ffmpeg_path))


def update_tools(log: LogFn = _noop, progress: ProgressFn | None = None,
                 cancel: threading.Event | None = None) -> bool:
    """최신 공식 빌드를 받아 두고 바로 적용해 봅니다. 적용했으면 True, 다음 실행 때 적용할 예정이면 False입니다."""
    target = config.tools_dir()
    install_from_zip(*GYAN_RELEASE, target, log, progress, cancel, suffix=STAGED_SUFFIX)
    return apply_staged(target)
