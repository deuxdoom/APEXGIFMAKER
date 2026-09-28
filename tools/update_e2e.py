# update_e2e.py
"""자동 업데이트 종단 검증. `python tools/build.py`로 만든 dist의 ZIP으로 실제 교체 과정을 끝까지 돌려 봅니다.

    python tools/update_e2e.py

임시 폴더(F:/temp/APEXGIFMAKER/e2e)에 '설치된 옛 버전'을 만들고(bin에 ffmpeg와 받아 둔 새 ffmpeg 포함),
ZIP 검증·압축 해제 → 새 exe를 --apply-update로 실행 → 교체·ffmpeg 보존·result.json·재실행·받아 둔 ffmpeg 적용·
작업 폴더 정리까지 확인합니다. 화면은 오프스크린으로 띄우고, 재실행된 앱은 확인 뒤 종료합니다.
빌드 뒤, 릴리즈 전에 실행합니다. (창을 띄우는 exe를 실행하므로 check.py 테스트에는 넣지 않았습니다)
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time

import _bootstrap

ROOT = _bootstrap.setup()

from versioninfo import APP_VERSION  # noqa: E402

from src.core import self_update  # noqa: E402
from src.core.updater import asset_name  # noqa: E402

BASE = _bootstrap.TEMP_ROOT / "e2e"
APP = BASE / "ApexGIFMaker"
ZIP = ROOT / "dist" / asset_name(APP_VERSION)
TOOLS = ROOT / "bin"


def check(results: list[tuple[str, bool]], name: str, ok: bool) -> None:
    results.append((name, ok))
    print(f"[{' OK ' if ok else 'FAIL'}] {name}")


def main() -> int:
    if not ZIP.is_file() or not (ROOT / "dist" / "ApexGIFMaker").is_dir():
        print(f"{ZIP.name}가 없습니다. 먼저 python tools/build.py를 실행하세요.")
        return 1
    if not all((TOOLS / name).is_file() for name in ("ffmpeg.exe", "ffprobe.exe")):
        print("프로젝트 bin 폴더에 ffmpeg.exe/ffprobe.exe가 필요합니다. 소스로 한 번 실행해 받아 두세요.")
        return 1

    shutil.rmtree(BASE, ignore_errors=True)
    shutil.copytree(ROOT / "dist" / "ApexGIFMaker", APP)
    for name in ("ffmpeg.exe", "ffprobe.exe"):
        shutil.copy2(TOOLS / name, APP / "bin" / name)                 # 사용자 ffmpeg (보존돼야 함)
        shutil.copy2(TOOLS / name, APP / "bin" / (name + ".new"))      # 받아 둔 새 버전 (재실행 때 적용돼야 함)
    (APP / "ApexGIFMaker.exe").write_bytes(b"MZ-old-exe-marker")
    (APP / "bin" / "old-only.txt").write_text("old")
    (APP / "settings.json").write_text(json.dumps({"theme": "light", "confirm_exit": False,
                                                   "auto_update_tools": False}), encoding="utf-8")
    ffmpeg_size = (APP / "bin" / "ffmpeg.exe").stat().st_size

    work = APP / self_update.WORK_DIR_NAME
    (work / self_update.NEW_DIR_NAME).mkdir(parents=True)
    (work / self_update.BACKUP_DIR_NAME).mkdir()
    root = self_update.verify_package(ZIP)
    self_update.extract_payload(ZIP, root, work / self_update.NEW_DIR_NAME)
    results: list[tuple[str, bool]] = []
    check(results, "ZIP 검증·압축 해제", self_update.staged_payload_ok(work))

    finished = subprocess.Popen(["cmd", "/c", "exit"])            # 이미 끝난 '옛 프로세스' 흉내
    finished.wait()
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    new_exe = work / self_update.NEW_DIR_NAME / "ApexGIFMaker.exe"
    started = time.monotonic()
    apply = subprocess.Popen([str(new_exe), "--apply-update", "--pid", str(finished.pid), "--app-dir", str(APP),
                              "--work-dir", str(work), "--from-version", "0.0.1"], cwd=new_exe.parent, env=env)
    result_path, result = work / self_update.RESULT_NAME, None
    while time.monotonic() - started < 90 and result is None:
        try:
            result = json.loads(result_path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            time.sleep(0.2)
    apply.wait(timeout=30)
    print(f"       적용 모드 {time.monotonic() - started:.1f}s, 결과 {result}")
    check(results, "적용 결과 ok", bool(result and result.get("ok")))
    check(results, "exe 교체", (APP / "ApexGIFMaker.exe").stat().st_size > 1000)
    check(results, "새 bin 설치", (APP / "bin" / "base_library.zip").is_file())
    check(results, "옛 버전 전용 파일 정리", not (APP / "bin" / "old-only.txt").exists())
    check(results, "bin의 ffmpeg 보존", (APP / "bin" / "ffmpeg.exe").stat().st_size == ffmpeg_size)
    check(results, "설정 보존", json.loads((APP / "settings.json").read_text(encoding="utf-8")).get("theme") == "light")

    time.sleep(9)   # 재실행된 앱: 받아 둔 ffmpeg 적용 → 결과 안내 → 5초 뒤 작업 폴더 정리
    check(results, "재실행 앱이 받아 둔 ffmpeg 적용", not (APP / "bin" / "ffmpeg.exe.new").exists())
    check(results, "작업 폴더 정리", not work.exists())
    script = ("Get-Process ApexGIFMaker -ErrorAction SilentlyContinue | Where-Object { $_.Path -like '"
              + str(BASE) + "*' } | ForEach-Object { $_.Id; Stop-Process -Id $_.Id -Force }")
    stopped = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True)
    check(results, "재실행된 앱 확인", bool(stopped.stdout.split()))
    shutil.rmtree(BASE, ignore_errors=True)

    failed = [name for name, ok in results if not ok]
    print("\n" + ("모든 항목을 통과했습니다." if not failed else f"실패: {', '.join(failed)}"))
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
