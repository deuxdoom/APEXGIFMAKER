# build.py
"""릴리즈 빌드: 검사 → PyInstaller → 스모크 테스트 → ZIP → 구조 검증 → SHA-256.

    python tools/build.py                 전체 (tools/check.py 포함)
    python tools/build.py --skip-check    검사를 이미 돌렸을 때
    python tools/build.py --with-ffmpeg   프로젝트 bin 폴더의 ffmpeg·ffprobe를 함께 넣습니다. (기본은 넣지 않음:
                                          첫 실행 때 앱이 SHA-256을 확인한 뒤 자동으로 받습니다. 자동 업데이트 용량도 줄어듭니다.)

결과: dist/ApexGIFMaker/ (exe + bin 폴더), dist/ApexGIFMaker_v300.zip (+ .sha256)
RELEASE.md에 ZIP 이름과 SHA-256 코드 블록이 있으면 해시를 새 값으로 바꿉니다. (RELEASE.md는 커밋하지 않고 지우지도 않음)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

import _bootstrap

ROOT = _bootstrap.setup()

from versioninfo import APP_VERSION  # noqa: E402

from src.core import self_update  # noqa: E402
from src.core.updater import asset_name  # noqa: E402

APP_NAME = "ApexGIFMaker"
DIST = ROOT / "dist"
APP_FOLDER = DIST / APP_NAME
WORK = _bootstrap.TEMP_ROOT / "pyinstaller"
HEX64 = re.compile(r"(?<![0-9a-fA-F])[0-9a-fA-F]{64}(?![0-9a-fA-F])")


def banner(text: str) -> None:
    print(f"\n=== {text}")


def run(command: list[str], **kwargs) -> None:
    print("> " + " ".join(command))
    subprocess.run(command, cwd=ROOT, check=True, **kwargs)


def folder_size(folder: Path) -> int:
    return sum(p.stat().st_size for p in folder.rglob("*") if p.is_file())


def mb(size: int) -> str:
    return f"{size / 1024 / 1024:.1f} MB"


def smoke_test() -> None:
    exe = APP_FOLDER / f"{APP_NAME}.exe"
    report_path = _bootstrap.TEMP_ROOT / "smoke-report.json"
    report_path.unlink(missing_ok=True)
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", APEX_SMOKE_REPORT=str(report_path))
    started = time.monotonic()
    proc = subprocess.run([str(exe), "--smoke-test"], cwd=APP_FOLDER, env=env, timeout=180)
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise SystemExit(f"스모크 테스트 보고서가 없습니다 (종료 코드 {proc.returncode})") from None
    print(f"종료 코드 {proc.returncode}, {time.monotonic() - started:.1f}s, 글꼴 {report.get('fonts')}")
    if proc.returncode != 0 or not report.get("ok"):
        for problem in report.get("problems", []):
            print(f"  ✗ {problem}")
        raise SystemExit("스모크 테스트 실패")
    for leftover in ("settings.json", self_update.WORK_DIR_NAME):
        path = APP_FOLDER / leftover
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()


def make_zip(target: Path) -> None:
    """ZIP 안에 ApexGIFMaker/ 폴더가 통째로 들어가게 만듭니다. (기존 릴리즈와 같은 구조)"""
    target.unlink(missing_ok=True)
    files = sorted(p for p in APP_FOLDER.rglob("*") if p.is_file())
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            archive.write(path, f"{APP_NAME}/{path.relative_to(APP_FOLDER).as_posix()}")


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def update_release_notes(zip_name: str, sha: str) -> None:
    notes = ROOT / "RELEASE.md"
    if not notes.is_file():
        print("RELEASE.md가 없어 해시를 적지 않았습니다. (릴리즈 노트를 쓴 뒤 다시 빌드하거나 직접 적어 주세요)")
        return
    lines = notes.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        if zip_name in line:
            for offset in range(index, min(index + 5, len(lines))):
                if HEX64.search(lines[offset]) or "SHA256_PLACEHOLDER" in lines[offset]:
                    lines[offset] = HEX64.sub(sha.upper(), lines[offset]).replace("SHA256_PLACEHOLDER", sha.upper())
                    notes.write_text("\n".join(lines) + "\n", encoding="utf-8")
                    print(f"RELEASE.md의 SHA-256을 갱신했습니다. ({zip_name})")
                    return
    print(f"RELEASE.md에서 {zip_name}의 SHA-256 자리를 찾지 못했습니다.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--skip-check", action="store_true", help="tools/check.py를 건너뜁니다")
    parser.add_argument("--with-ffmpeg", action="store_true", help="ffmpeg·ffprobe를 ZIP의 bin 폴더에 넣습니다")
    args = parser.parse_args()
    started = time.monotonic()
    python = sys.executable

    if not args.skip_check:
        banner("검사 (tools/check.py)")
        if subprocess.run([python, str(ROOT / "tools" / "check.py")], cwd=ROOT).returncode != 0:
            print("검사를 통과하지 못해 빌드를 멈춥니다.")
            return 1

    banner(f"PyInstaller — {APP_NAME} v{APP_VERSION}")
    shutil.rmtree(APP_FOLDER, ignore_errors=True)
    run([python, "-m", "PyInstaller", "apexgifmaker.spec", "--noconfirm", "--clean",
         "--workpath", str(WORK), "--distpath", str(DIST)])

    if args.with_ffmpeg:
        banner("ffmpeg 포함 (bin 폴더)")
        source = ROOT / "bin"
        tools = ("ffmpeg.exe", "ffprobe.exe")
        if not all((source / name).is_file() for name in tools):
            print("프로젝트 bin 폴더에 ffmpeg.exe/ffprobe.exe가 없습니다. 소스로 한 번 실행해 받아 두거나 직접 넣어 주세요.")
            return 1
        for name in tools:
            shutil.copy2(source / name, APP_FOLDER / "bin" / name)

    banner("스모크 테스트 (빌드된 exe)")
    smoke_test()

    banner("ZIP")
    zip_path = DIST / asset_name(APP_VERSION)
    make_zip(zip_path)
    root = self_update.verify_package(zip_path)
    if root != f"{APP_NAME}/":
        print(f"ZIP 구조가 예상과 다릅니다: 접두사 '{root}'")
        return 1
    sha = sha256_of(zip_path)
    (DIST / f"{zip_path.name}.sha256").write_text(f"{sha}  {zip_path.name}\n", encoding="utf-8")
    update_release_notes(zip_path.name, sha)
    shutil.rmtree(WORK, ignore_errors=True)

    banner("완료")
    print(f"폴더   {APP_FOLDER}  ({mb(folder_size(APP_FOLDER))})")
    print(f"ZIP    {zip_path}  ({mb(zip_path.stat().st_size)})")
    print(f"SHA-256  {sha.upper()}")
    print(f"소요 시간 {time.monotonic() - started:.0f}s")
    print("릴리즈 페이지에 ZIP을 올리고 본문에 RELEASE.md를 붙여 넣으면 됩니다. GitHub가 계산한 자산 digest와 "
          "위 SHA-256이 같아야 자동 업데이트가 동작합니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
