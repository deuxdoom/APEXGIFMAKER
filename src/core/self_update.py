# self_update.py
"""새 버전 ZIP을 받아 검증하고, 작업 폴더에 풀어 둔 뒤 적용 모드를 띄웁니다.

실행 중인 exe는 자기 자신을 덮어쓸 수 없으므로, 교체는 새 exe를 `--apply-update`로 띄워서 맡깁니다
(core/apply_update.py). 여기서는 아무것도 교체하지 않습니다. 이 단계에서 실패해도 지금 버전은 그대로입니다.

바꾸는 것은 `ApexGIFMaker.exe`와 `bin/`(앱 실행 파일)뿐입니다. 같은 `bin/`에 있는 ffmpeg·ffprobe와
`settings.json`은 사용자 것이라 손대지 않습니다(is_preserved). (참고: TVerDownloader의 self_update.py)
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable, Iterable, Iterator
from urllib.parse import urljoin, urlsplit

from . import config
from .updater import DOWNLOAD_PREFIX, UpdateAsset

APP_EXE_NAME = config.APP_EXE_NAME
INTERNAL_DIR_NAME = config.TOOLS_DIR_NAME          # PyInstaller 내용물 폴더 (spec의 contents_directory)
# bin 바로 아래에 있어도 앱 업데이트가 옮기거나 덮어쓰지 않는 파일 (ffmpeg 도구와 받아 둔 새 버전)
PRESERVED_NAMES = frozenset({"ffmpeg.exe", "ffprobe.exe", "ffmpeg.exe.new", "ffprobe.exe.new",
                             "ffmpeg.exe.part", "ffprobe.exe.part"})
WORK_DIR_NAME = "update-workspace"
NEW_DIR_NAME = "new"
BACKUP_DIR_NAME = "backup"
RESULT_NAME = "result.json"
PACKAGE_NAME = "package.zip"

CHUNK = 256 * 1024
DOWNLOAD_TIMEOUT = 30
MAX_REDIRECTS = 5
ALLOWED_ASSET_HOSTS = frozenset({"github.com", "objects.githubusercontent.com",
                                 "release-assets.githubusercontent.com"})
_DRIVE_PREFIX_RE = re.compile(r"^[A-Za-z]:")


class VerificationError(ValueError):
    """받은 파일이 릴리즈가 가리키는 파일이 아니거나, 풀 수 없는 구조일 때."""


class DownloadCancelled(Exception):
    pass


# --- 위치 ---

def supported() -> bool:
    """자동 교체를 쓸 수 있는지. 소스로 실행 중이면 끕니다 — 개발 폴더를 릴리즈로 덮으면 작업이 날아갑니다."""
    return bool(getattr(sys, "frozen", False)) and os.name == "nt"


def app_dir() -> Path | None:
    return Path(sys.executable).resolve().parent if supported() else None


def work_dir() -> Path | None:
    base = app_dir()
    return None if base is None else base / WORK_DIR_NAME


def is_writable(folder: Path) -> bool:
    probe = folder / ".write-test"
    try:
        probe.write_bytes(b"")
        probe.unlink()
        return True
    except OSError:
        return False


def prepare_workspace() -> Path | None:
    """작업 폴더를 비우고 new/, backup/을 만듭니다. 앱 폴더에 쓸 수 없으면 None입니다."""
    base, work = app_dir(), work_dir()
    if base is None or work is None or not is_writable(base):
        return None
    shutil.rmtree(work, ignore_errors=True)
    try:
        (work / NEW_DIR_NAME).mkdir(parents=True, exist_ok=False)
        (work / BACKUP_DIR_NAME).mkdir(parents=True, exist_ok=True)
    except OSError:
        return None
    return work


def cleanup_workspace() -> None:
    work = work_dir()
    if work is not None and work.exists():
        shutil.rmtree(work, ignore_errors=True)


def read_result() -> dict | None:
    """직전 업데이트 적용 결과(result.json)를 읽습니다."""
    work = work_dir()
    if work is None:
        return None
    try:
        data = json.loads((work / RESULT_NAME).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


# --- 다운로드 ---

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """리다이렉트를 자동으로 따라가지 않습니다. 목적지 호스트를 한 단계씩 확인하기 위해서입니다."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def allowed_download_url(url: str, *, first_hop: bool) -> bool:
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        return False
    if parts.scheme != "https" or parts.username or parts.password or port:
        return False
    if first_hop:
        return url.startswith(DOWNLOAD_PREFIX) and parts.hostname == "github.com"
    return parts.hostname in ALLOWED_ASSET_HOSTS


def download_asset(asset: UpdateAsset, dest: Path, progress: Callable[[int, int], None] | None = None,
                   cancel: threading.Event | None = None) -> None:
    """ZIP을 받으면서 크기와 SHA-256을 확인합니다. 어긋나거나 실패하면 받던 파일을 지우고 예외를 냅니다."""
    opener = urllib.request.build_opener(_NoRedirect)
    headers = {"User-Agent": config.USER_AGENT, "Accept": "application/octet-stream"}
    url = asset.url
    digest = hashlib.sha256()
    received = 0
    try:
        with open(dest, "wb") as out:
            for hop in range(MAX_REDIRECTS + 1):
                if not allowed_download_url(url, first_hop=hop == 0):
                    raise VerificationError(f"unexpected download destination: {url}")
                try:
                    resp = opener.open(urllib.request.Request(url, headers=headers), timeout=DOWNLOAD_TIMEOUT)
                except urllib.error.HTTPError as exc:
                    location = exc.headers.get("Location") if exc.code in (301, 302, 303, 307, 308) else None
                    if not location:
                        raise
                    url = urljoin(url, location)
                    continue
                with resp:
                    while True:
                        if cancel is not None and cancel.is_set():
                            raise DownloadCancelled()
                        chunk = resp.read(CHUNK)
                        if not chunk:
                            break
                        received += len(chunk)
                        if received > asset.size:
                            raise VerificationError("download is larger than the release asset")
                        out.write(chunk)
                        digest.update(chunk)
                        if progress:
                            progress(received, asset.size)
                break
            else:
                raise VerificationError("too many redirects")
        if received != asset.size:
            raise VerificationError(f"size mismatch: {received} != {asset.size}")
        if digest.hexdigest() != asset.sha256:
            raise VerificationError("SHA-256 mismatch")
    except BaseException:
        dest.unlink(missing_ok=True)
        raise


# --- ZIP 검증과 압축 해제 ---

def is_preserved(relative: str | Path) -> bool:
    """bin 바로 아래의 ffmpeg 도구 파일인지. (앱 업데이트가 건드리지 않는 파일)"""
    parts = Path(relative).as_posix().lower().split("/")
    return len(parts) == 2 and parts[0] == INTERNAL_DIR_NAME.lower() and parts[1] in PRESERVED_NAMES


def escapes_destination(name: str) -> bool:
    """압축 항목이 풀 폴더 밖(절대 경로, 드라이브 지정, ..)을 가리키는지 확인합니다."""
    path = name.replace("\\", "/")
    if path.startswith("/") or _DRIVE_PREFIX_RE.match(path):
        return True
    return any(part == ".." for part in path.split("/"))


def find_payload_root(names: Iterable[str]) -> str | None:
    """ZIP 안에서 exe와 bin/이 함께 있는 위치(접두사)를 찾습니다. 감싼 폴더가 없어도 받습니다."""
    entries = [n.replace("\\", "/") for n in names]
    lowered = [e.lower() for e in entries]
    candidates = {""} | {e.split("/", 1)[0] + "/" for e in entries if "/" in e}
    exe, internal = APP_EXE_NAME.lower(), INTERNAL_DIR_NAME.lower() + "/"
    for root in sorted(candidates, key=len):
        prefix = root.lower()
        if prefix + exe in lowered and any(e.startswith(prefix + internal) for e in lowered):
            return root
    return None


def payload_members(names: Iterable[str], root: str) -> Iterator[tuple[str, str]]:
    """root 아래에서 교체 대상(exe, bin/)만 (원래 이름, 상대 경로)로 내줍니다. ffmpeg 도구는 빼고 내줍니다."""
    exe, internal = APP_EXE_NAME.lower(), INTERNAL_DIR_NAME.lower() + "/"
    for name in names:
        normalized = name.replace("\\", "/")
        if not normalized.lower().startswith(root.lower()):
            continue
        relative = normalized[len(root):]
        low = relative.lower()
        if relative and (low == exe or low.startswith(internal)) and not is_preserved(relative):
            yield name, relative


def verify_package(zip_path: Path) -> str:
    """받은 ZIP을 검사하고 내용물 접두사(예: 'ApexGIFMaker/')를 반환합니다.

    CRC(testzip), 폴더 밖을 가리키는 항목, exe와 bin/의 존재를 모두 확인합니다.
    """
    if not zip_path.is_file() or zip_path.stat().st_size == 0:
        raise VerificationError("package is empty")
    try:
        with zipfile.ZipFile(zip_path) as archive:
            broken = archive.testzip()
            if broken is not None:
                raise VerificationError(f"corrupted entry: {broken}")
            names = archive.namelist()
    except (zipfile.BadZipFile, OSError) as exc:
        raise VerificationError(f"unreadable package: {exc}") from None
    unsafe = next((n for n in names if escapes_destination(n)), None)
    if unsafe is not None:
        raise VerificationError(f"unsafe path in package: {unsafe}")
    root = find_payload_root(names)
    if root is None:
        raise VerificationError(f"package has no {APP_EXE_NAME} and {INTERNAL_DIR_NAME}/")
    unsafe = next((n for n, rel in payload_members(names, root) if escapes_destination(rel)), None)
    if unsafe is not None:
        raise VerificationError(f"unsafe path in package: {unsafe}")
    return root


def extract_payload(zip_path: Path, root: str, destination: Path,
                    on_progress: Callable[[int, int], None] | None = None) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as archive:
        infos = {info.filename: info for info in archive.infolist()}
        picked = [(infos[name], rel) for name, rel in payload_members(infos, root)
                  if not escapes_destination(rel)]
        total = len(picked) or 1
        for index, (info, relative) in enumerate(picked, 1):
            target = destination / relative
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as src, open(target, "wb") as out:
                    shutil.copyfileobj(src, out, 1024 * 1024)
            if on_progress:
                on_progress(index, total)


def staged_payload_ok(work: Path) -> bool:
    """풀어 둔 새 버전이 교체를 시작해도 될 만큼 온전한지 마지막으로 확인합니다."""
    new_dir = work / NEW_DIR_NAME
    exe = new_dir / APP_EXE_NAME
    internal = new_dir / INTERNAL_DIR_NAME
    return exe.is_file() and exe.stat().st_size > 0 and internal.is_dir() and any(internal.iterdir())


def launch_apply_mode(work: Path, pid: int, from_version: str) -> bool:
    """풀어 둔 새 exe를 적용 모드로 띄웁니다. 성공하면 호출한 쪽은 곧바로 종료해야 합니다."""
    base = app_dir()
    if base is None:
        return False
    exe = work / NEW_DIR_NAME / APP_EXE_NAME
    command = [str(exe), "--apply-update", "--pid", str(pid), "--app-dir", str(base),
               "--work-dir", str(work), "--from-version", from_version]
    try:
        subprocess.Popen(command, cwd=str(exe.parent), close_fds=True,
                         creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))
        return True
    except OSError:
        return False
