# apply_update.py
"""새 exe가 `--apply-update` 모드로 실행되어 기존 앱 파일을 교체합니다. (참고: TVerDownloader)

1. 이전 프로세스가 끝나기를 기다립니다. (최대 60초)
2. 기존 exe와 bin/(ffmpeg 도구 제외)을 파일 단위로 backup/에 옮깁니다.
3. 새 파일을 앱 폴더에 복사합니다.
4. 새 버전을 실행합니다.
어느 단계에서든 실패하면 옮긴 파일을 되돌리고 이전 버전을 다시 실행합니다. 결과는 result.json에 남깁니다.
화면은 진행 콜백(on_progress)으로만 상태를 받습니다.
"""
from __future__ import annotations

import ctypes
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Sequence

from versioninfo import APP_VERSION

from .self_update import (APP_EXE_NAME, BACKUP_DIR_NAME, INTERNAL_DIR_NAME, NEW_DIR_NAME,
                          RESULT_NAME, WORK_DIR_NAME, is_preserved)

WAIT_LIMIT_SECONDS = 60
WAIT_POLL_MS = 200
SETTLE_SECONDS = 1.5      # 이전 프로세스가 끝난 뒤 백신 검사 등이 파일을 놓아줄 시간
MOVE_RETRIES = 8
MOVE_RETRY_WAIT = 1.5     # 백신이 갓 풀린 파일을 잡고 있으면 'Access is denied'가 나므로 다시 시도합니다.

_SYNCHRONIZE = 0x00100000
_WAIT_OBJECT_0 = 0
_WAIT_TIMEOUT = 258
_ERROR_INVALID_PARAMETER = 87

ProgressFn = Callable[[int, str, dict], None]   # (0~100, 단계, 세부 정보)


@dataclass(frozen=True)
class ApplyOptions:
    pid: int
    app_dir: Path
    work_dir: Path
    from_version: str


def parse_arguments(argv: Sequence[str]) -> ApplyOptions | None:
    """`--apply-update --pid N --app-dir D --work-dir W --from-version V`를 읽습니다."""
    if not argv or argv[0] != "--apply-update" or len(argv[1:]) % 2:
        return None
    allowed = {"--pid", "--app-dir", "--work-dir", "--from-version"}
    values: dict[str, str] = {}
    for key, value in zip(argv[1::2], argv[2::2]):
        if key not in allowed or key in values or not value:
            return None
        values[key] = value
    if values.keys() != allowed:
        return None
    try:
        pid = int(values["--pid"])
    except ValueError:
        return None
    if pid <= 0:
        return None
    return ApplyOptions(pid, Path(values["--app-dir"]), Path(values["--work-dir"]), values["--from-version"])


def validate_arguments(options: ApplyOptions, current_exe: Path) -> bool:
    """인자로 받은 경로가 정해진 구조(앱 폴더/update-workspace/new/exe)와 맞는지 확인합니다."""
    try:
        app = options.app_dir.resolve()
        work = options.work_dir.resolve()
        exe = current_exe.resolve()
    except OSError:
        return False
    new = work / NEW_DIR_NAME
    return (work == app / WORK_DIR_NAME
            and exe.name.lower() == APP_EXE_NAME.lower()
            and exe.is_relative_to(new)
            and (app / APP_EXE_NAME).is_file()
            and (app / INTERNAL_DIR_NAME).is_dir()
            and (new / APP_EXE_NAME).is_file()
            and (new / INTERNAL_DIR_NAME).is_dir())


def payload_files(root: Path) -> list[Path]:
    """교체 대상 파일 목록(상대 경로). 파일 단위로 옮겨야 일부만 처리됐을 때도 되돌릴 수 있습니다.
    bin 안의 ffmpeg 도구(is_preserved)는 목록에서 빠지므로 옮기지도, 덮어쓰지도 않습니다."""
    internal = root / INTERNAL_DIR_NAME
    files = [Path(APP_EXE_NAME)] if (root / APP_EXE_NAME).is_file() else []
    if internal.is_dir():
        files.extend(sorted(rel for rel in (p.relative_to(root) for p in internal.rglob("*") if p.is_file())
                            if not is_preserved(rel)))
    return files


def make_result(options: ApplyOptions, stage: str, error: str = "") -> dict:
    return {"ok": stage == "done", "from_version": options.from_version, "to_version": APP_VERSION,
            "stage": stage, "error": error, "finished_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}


def write_result(options: ApplyOptions, result: dict) -> None:
    temporary = options.work_dir / "result.tmp"
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, options.work_dir / RESULT_NAME)


def wait_for_pid(pid: int, cancelled: Callable[[], bool], limit_seconds: float = WAIT_LIMIT_SECONDS) -> bool | None:
    """프로세스 핸들로 종료를 기다립니다. True=종료됨, False=시간 초과, None=취소."""
    if os.name != "nt":
        return True
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    handle = kernel.OpenProcess(_SYNCHRONIZE, False, pid)
    if not handle:
        if ctypes.get_last_error() == _ERROR_INVALID_PARAMETER:   # 이미 끝난 프로세스
            return True
        raise OSError(ctypes.get_last_error(), "OpenProcess")
    try:
        deadline = time.monotonic() + limit_seconds
        while True:
            if cancelled():
                return None
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            status = kernel.WaitForSingleObject(handle, min(WAIT_POLL_MS, max(1, int(remaining * 1000))))
            if status == _WAIT_OBJECT_0:
                return True
            if status != _WAIT_TIMEOUT:
                raise OSError(ctypes.get_last_error(), "WaitForSingleObject")
    finally:
        kernel.CloseHandle(handle)


def launch_application(exe: Path) -> None:
    subprocess.Popen([str(exe)], cwd=str(exe.parent), close_fds=True)


def apply_update(options: ApplyOptions, on_progress: ProgressFn, *,
                 current_exe: Path | None = None,
                 wait: Callable[[int, Callable[[], bool]], bool | None] | None = None,
                 sleep: Callable[[float], None] | None = None,
                 move: Callable[[Path, Path], object] | None = None,
                 copy: Callable[[Path, Path], object] | None = None,
                 launch: Callable[[Path], None] | None = None,
                 cancelled: Callable[[], bool] | None = None) -> dict | None:
    """교체를 실행하고 결과 사전을 반환합니다. 취소되면 None입니다. (의존성은 검사용으로 바꿔 끼울 수 있음)"""
    exe_path = Path(sys.executable) if current_exe is None else Path(current_exe)
    wait_fn = wait or wait_for_pid
    sleep_fn = sleep or time.sleep
    move_fn = move or os.replace
    copy_fn = copy or shutil.copy2
    launch_fn = launch or launch_application
    is_cancelled = cancelled or (lambda: False)

    def report(percent: int, stage: str, **detail) -> None:
        on_progress(percent, stage, detail)

    def save(stage: str, error: str = "") -> dict:
        result = make_result(options, stage, error)
        write_result(options, result)
        return result

    def retry(operation: Callable[[], object]) -> None:
        for attempt in range(MOVE_RETRIES):
            try:
                operation()
                return
            except OSError:
                if attempt + 1 == MOVE_RETRIES:
                    raise
                sleep_fn(MOVE_RETRY_WAIT)

    app, work = options.app_dir, options.work_dir
    new, backup = work / NEW_DIR_NAME, work / BACKUP_DIR_NAME
    if not validate_arguments(options, exe_path):
        result = make_result(options, "bad_arguments", "invalid update paths")
        report(0, "bad_arguments", error=result["error"])
        return result

    report(0, "waiting")
    try:
        exited = wait_fn(options.pid, is_cancelled)
    except OSError as exc:
        result = save("failed", str(exc))
        report(0, "failed", error=result["error"])
        return result
    if exited is None or is_cancelled():
        return None
    if not exited:
        result = save("wait_timeout", "previous process did not exit")
        report(10, "wait_timeout", error=result["error"])
        return result
    sleep_fn(SETTLE_SECONDS)

    moved: list[Path] = []
    copied: list[Path] = []
    percent = 10
    try:
        old_files, new_files = payload_files(app), payload_files(new)
        if not old_files or not any(p.parts[0] == INTERNAL_DIR_NAME for p in new_files):
            raise OSError("incomplete update files")
        backup.mkdir(parents=True, exist_ok=True)
        if any(backup.iterdir()):
            raise OSError("backup folder is not empty")

        report(percent, "backing_up", done=0, total=len(old_files))
        for index, relative in enumerate(old_files, 1):
            target = backup / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            retry(lambda src=app / relative, dst=target: move_fn(src, dst))
            moved.append(relative)
            percent = 10 + 15 * index // len(old_files)
            report(percent, "backing_up", done=index, total=len(old_files))

        report(25, "installing", done=0, total=len(new_files))
        for index, relative in enumerate(new_files, 1):
            target = app / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            copied.append(relative)
            retry(lambda src=new / relative, dst=target: copy_fn(src, dst))
            percent = 25 + 70 * index // len(new_files)
            report(percent, "installing", done=index, total=len(new_files))

        result = save("done")
        report(96, "launching")
        launch_fn(app / APP_EXE_NAME)
        report(100, "done", from_version=options.from_version, to_version=APP_VERSION)
        return result
    except OSError as exc:
        cause = str(exc)
        report(percent, "rolling_back", error=cause)
        try:
            for relative in reversed(copied):
                target = app / relative
                if target.exists():
                    retry(target.unlink)
            for relative in reversed(moved):
                target = app / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                retry(lambda src=backup / relative, dst=target: move_fn(src, dst))
            result = save("rolled_back", cause)
            launch_fn(app / APP_EXE_NAME)
            report(percent, "rolled_back", error=cause)
            return result
        except OSError as rollback_error:
            result = make_result(options, "failed", f"{cause}; rollback: {rollback_error}")
            try:
                write_result(options, result)
            except OSError:
                pass
            report(percent, "failed", error=result["error"], path=str(backup))
            return result
