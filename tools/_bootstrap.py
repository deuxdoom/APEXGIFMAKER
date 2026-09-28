# _bootstrap.py
"""tools/ 스크립트(검사·테스트·빌드)가 함께 쓰는 준비.

- 어디서 실행하든 프로젝트 루트를 import 경로와 작업 디렉터리로 씁니다.
- 임시 파일은 C: 드라이브가 아니라 `<프로젝트 상위>/temp/<프로젝트 이름>`(= F:/temp/APEXGIFMAKER)에 씁니다.
  (TVerDownloader의 tests/_bootstrap.py와 같은 규칙)
- 표준 출력을 UTF-8로 돌려서 cp949 콘솔에서도 한글·일본어·중국어 출력이 깨지지 않게 합니다.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMP_ROOT = ROOT.parent / "temp" / ROOT.name
TEST_LANGUAGE = "ko"


def use_temp_root() -> Path:
    """이 프로세스와 자식 프로세스의 임시 폴더를 TEMP_ROOT/tmp로 돌립니다."""
    temp = TEMP_ROOT / "tmp"
    temp.mkdir(parents=True, exist_ok=True)
    os.environ["TEMP"] = os.environ["TMP"] = str(temp)
    tempfile.tempdir = str(temp)
    return temp


def setup() -> Path:
    root = str(ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
    os.chdir(ROOT)
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")
    use_temp_root()
    from src import i18n
    i18n.set_language(TEST_LANGUAGE)
    return ROOT


def sources() -> list[Path]:
    """검사 대상 파이썬 소스 전체 (앱 + 도구)."""
    return [ROOT / "apexgifmaker.py", ROOT / "versioninfo.py",
            *sorted((ROOT / "src").rglob("*.py")), *sorted((ROOT / "tools").rglob("*.py"))]
