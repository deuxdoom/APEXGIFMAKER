# check.py
"""빌드 전 검사. 이 스크립트 하나로 문법·정적 분석·타입 검사·프로젝트 규칙·테스트를 모두 실행합니다.

    python tools/check.py              전체 검사
    python tools/check.py --quick      테스트는 코어 단위 테스트만 (GUI·ffmpeg 테스트 제외)
    python tools/check.py --no-pyright pyright 단계 건너뛰기

종료 코드: 0 = 통과, 1 = 실패. 경고는 실패로 치지 않습니다.
"""
from __future__ import annotations

import argparse
import ast
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable

import _bootstrap

ROOT = _bootstrap.setup()

WARN_LINES = 800
FAIL_LINES = 1000
MIN_PYTHON = (3, 10)
PYTHON = sys.executable


class Result:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.warnings: list[str] = []

    def fail(self, message: str) -> None:
        self.failures.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)


def step(title: str, results: list[tuple[str, Result, float]], func: Callable[[Result], None]) -> None:
    result = Result()
    started = time.monotonic()
    try:
        func(result)
    except Exception as exc:  # 검사 도구 자체의 오류도 실패로 보여 줍니다.
        result.fail(f"{type(exc).__name__}: {exc}")
    elapsed = time.monotonic() - started
    mark = "FAIL" if result.failures else "WARN" if result.warnings else " OK "
    print(f"[{mark}] {title}  ({elapsed:.1f}s)")
    for message in result.failures:
        print(f"       ✗ {message}")
    for message in result.warnings:
        print(f"       ! {message}")
    results.append((title, result, elapsed))


# ---------------------------------------------------------------------- 검사 단계
def check_environment(r: Result) -> None:
    if sys.version_info < MIN_PYTHON:
        r.fail(f"Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]} 이상이 필요합니다: {sys.version.split()[0]}")
    try:
        import PySide6
        print(f"       Python {sys.version.split()[0]} · PySide6 {PySide6.__version__}")
    except ImportError:
        r.fail("PySide6가 설치되어 있지 않습니다. (pip install -r requirements-dev.txt)")


def check_syntax(r: Result) -> None:
    for path in _bootstrap.sources():
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:
            r.fail(f"{path.relative_to(ROOT)}:{exc.lineno}: {exc.msg}")


def check_pyflakes(r: Result) -> None:
    try:
        from pyflakes import api, reporter
    except ImportError:
        r.warn("pyflakes가 없어 건너뜁니다. (pip install pyflakes)")
        return

    class Collector(reporter.Reporter):
        def __init__(self) -> None:
            super().__init__(sys.stdout, sys.stderr)

        def unexpectedError(self, filename, msg):
            r.fail(f"{filename}: {msg}")

        def syntaxError(self, filename, msg, lineno, offset, text):
            r.fail(f"{filename}:{lineno}: {msg}")

        def flake(self, message):
            r.fail(str(message).replace(str(ROOT) + os.sep, ""))

    collector = Collector()
    for path in _bootstrap.sources():
        api.checkPath(str(path), collector)


def _pyright_command() -> list[str] | None:
    local = Path(PYTHON).parent / ("pyright.exe" if os.name == "nt" else "pyright")
    if local.is_file():
        return [str(local)]
    found = shutil.which("pyright")
    return [found] if found else None


def check_pyright(r: Result) -> None:
    command = _pyright_command()
    if command is None:
        r.warn("pyright가 없어 건너뜁니다. (pip install pyright)")
        return
    env = dict(os.environ)
    # pyright가 받아 두는 node 패키지도 C:가 아닌 임시 폴더에 둡니다.
    env.setdefault("PYRIGHT_PYTHON_CACHE_DIR", str(_bootstrap.TEMP_ROOT / "pyright-cache"))
    env.setdefault("npm_config_cache", str(_bootstrap.TEMP_ROOT / "npm-cache"))
    proc = subprocess.run([*command, "--outputjson"], cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=env, timeout=600)
    import json
    try:
        report = json.loads(proc.stdout)
    except ValueError:
        r.fail(f"pyright 출력을 읽지 못했습니다: {proc.stdout[-300:]}{proc.stderr[-300:]}")
        return
    for diag in report.get("generalDiagnostics", []):
        where = f"{Path(diag.get('file', '')).relative_to(ROOT)}:{diag['range']['start']['line'] + 1}"
        text = f"{where}: {diag.get('message', '').splitlines()[0]} ({diag.get('rule', '')})"
        if diag.get("severity") == "error":
            r.fail(text)
        elif diag.get("severity") == "warning":
            r.warn(text)
    summary = report.get("summary", {})
    print(f"       pyright {report.get('version', '?')}: 파일 {summary.get('filesAnalyzed', '?')}개, "
          f"오류 {summary.get('errorCount', '?')}, 경고 {summary.get('warningCount', '?')} (standard)")


def check_line_counts(r: Result) -> None:
    for path in _bootstrap.sources():
        lines = len(path.read_text(encoding="utf-8").splitlines())
        name = path.relative_to(ROOT)
        if lines > FAIL_LINES:
            r.fail(f"{name}: {lines}줄 (최대 {FAIL_LINES}) — 모듈을 나눠 주세요")
        elif lines > WARN_LINES:
            r.warn(f"{name}: {lines}줄 ({WARN_LINES}줄 초과)")


_TR_CALL = re.compile(r"""\btr\(\s*(f?)(["'])([^"']+)\2""")


def _dynamic_keys() -> set[str]:
    """f-문자열로 조합하는 키 목록. 새로 조합하는 키가 생기면 여기에도 추가합니다."""
    from src.core.gif import DITHER_MODES, FRAME_MODES, SCALE_MODES
    from src.ui.apply_window import STEPS
    keys = {f"dlg.{name}" for name in ("ok", "cancel", "yes", "no")}
    for prefix, values in (("options.scale", SCALE_MODES), ("options.dither", DITHER_MODES),
                           ("options.frames", FRAME_MODES)):
        keys |= {f"{prefix}.{v}" for v in values} | {f"{prefix}.{v}.tip" for v in values}
    keys |= {f"apply.step.{s}" for s in STEPS}
    keys |= {"apply.rolled_back", "apply.timeout", "apply.bad_arguments", "apply.failed"}
    keys |= {f"menu.theme.{mode}" for mode in ("dark", "light", "system")}
    keys |= {"timeline.frames", "win.restore"}      # 조건식(a if … else b)의 뒤쪽 키
    return keys


def check_i18n(r: Result) -> None:
    from src import i18n
    for problem in i18n.validate():
        r.fail(problem)
    known = i18n.keys()
    used: set[str] = set()
    for path in sorted((ROOT / "src").rglob("*.py")):
        for is_f, _quote, key in _TR_CALL.findall(path.read_text(encoding="utf-8")):
            if is_f or "{" in key:
                continue
            used.add(key)
            if key not in known:
                r.fail(f"{path.relative_to(ROOT)}: 사전에 없는 키 '{key}'")
    dynamic = _dynamic_keys()
    for key in sorted(dynamic - known):
        r.fail(f"조합 키가 사전에 없습니다: '{key}'")
    unused = sorted(known - used - dynamic)
    if unused:
        r.warn(f"쓰이지 않는 키 {len(unused)}개: {', '.join(unused[:12])}{' …' if len(unused) > 12 else ''}")


def check_project(r: Result) -> None:
    from versioninfo import APP_VERSION
    if not re.fullmatch(r"\d+\.\d+\.\d+", APP_VERSION):
        r.fail(f"versioninfo.APP_VERSION이 세 자리 버전이 아닙니다: {APP_VERSION}")
    changelog = ROOT / "CHANGELOG.md"
    if not changelog.is_file():
        r.fail("CHANGELOG.md가 없습니다")
    elif f"## [{APP_VERSION}]" not in changelog.read_text(encoding="utf-8"):
        r.fail(f"CHANGELOG.md에 '## [{APP_VERSION}]' 항목이 없습니다")
    for name in ("applogo.svg", "applogo.png", "appicon.ico", "fonts/PretendardVariable.ttf",
                 "fonts/PretendardJP-Regular.ttf", "fonts/JetBrainsMono-Regular.ttf", "fonts/Pretendard-OFL.txt",
                 "fonts/JetBrainsMono-OFL.txt", "icons/LICENSE.txt"):
        if not (ROOT / "assets" / name).is_file():
            r.fail(f"assets/{name}이(가) 없습니다")
    spec = ROOT / "apexgifmaker.spec"
    if not spec.is_file():
        r.fail("apexgifmaker.spec이 없습니다")
    else:
        text = spec.read_text(encoding="utf-8")
        for needle in ("apexgifmaker.py", "versioninfo.py", "assets/appicon.ico", "assets", 'contents_directory="bin"'):
            if needle not in text:
                r.fail(f"apexgifmaker.spec에 '{needle}' 참조가 없습니다")
    check_icons(r)


_ZIP_NAME = re.compile(r"ApexGIFMaker_v\d+\.zip")
_FULL_VERSION = re.compile(r"(?<![\w.])v(\d+\.\d+\.\d+)(?![\w.])")
_PAGE_VERSION = re.compile(r"(?<![\w.])(\d+\.\d+)(?:\.\d+)?(?=\s*(?:개발|기준|버전|프리뷰|부터|은|는|을|를)|\s*$)")


def check_docs(r: Result) -> None:
    """커밋 전에 문서와 그림이 현재 버전·화면과 맞는지 봅니다. (사용자 지시: 바뀌면 그때그때 갱신)"""
    from versioninfo import APP_VERSION
    from src.core.updater import asset_name
    zip_name, major_minor = asset_name(APP_VERSION), ".".join(APP_VERSION.split(".")[:2])
    for rel in ("README.md", "README.txt", "RELEASE.md", "docs/index.html"):
        path = ROOT / rel
        if not path.is_file():
            if rel != "RELEASE.md":
                r.fail(f"{rel}이(가) 없습니다")
            continue
        text = path.read_text(encoding="utf-8")
        for found in sorted(set(_ZIP_NAME.findall(text)) - {zip_name}):
            r.fail(f"{rel}: 다운로드 파일 이름이 현재 버전과 다릅니다 ({found} → {zip_name})")
        for found in sorted(set(_FULL_VERSION.findall(text)) - {APP_VERSION}):
            if rel != "README.md" or not found.startswith("2."):
                r.fail(f"{rel}: 버전 표기 v{found}가 현재 버전 v{APP_VERSION}과 다릅니다")
        if rel == "docs/index.html":
            for found in sorted({m.group(1) for m in _PAGE_VERSION.finditer(text)} - {major_minor}):
                r.fail(f"{rel}: 버전 표기 {found}가 현재 버전 {major_minor}과(와) 다릅니다")
        if rel == "RELEASE.md" and APP_VERSION not in text.splitlines()[0]:
            r.fail(f"RELEASE.md 첫 줄에 현재 버전 {APP_VERSION}이 없습니다")
    ui_sources = [*(ROOT / "src" / "ui").rglob("*.py"), *(ROOT / "src" / "i18n").glob("*.py"), ROOT / "versioninfo.py"]
    newest = max(path.stat().st_mtime for path in ui_sources)
    for rel in ("docs/images/main.png", "docs/images/app-preview.webp"):
        path = ROOT / rel
        if not path.is_file():
            r.fail(f"{rel}이(가) 없습니다 (python tools/capture.py --docs)")
        elif path.stat().st_mtime + 1 < newest:
            r.warn(f"{rel}이(가) 화면 코드보다 오래되었습니다. UI가 바뀌었다면 python tools/capture.py --docs로 새로 만드세요")


_ICON_CALL = re.compile(r"""(?:set_icon\([^,()]+,\s*|make_icon_button\(\s*|make_tool_button\(\s*|icons\.icon\(\s*|"""
                        r"""icons\.pixmap\(\s*|icon_file\(\s*|make_button\([^,()]+,\s*)"([a-z_]+)\"""")
_ICON_TUPLE = re.compile(r"""\(\s*(?:tr\([^)]*\)|"[^"]*")\s*,\s*"([a-z_]+)"\s*,""")
_ICON_TERNARY = re.compile(r"""set_icon\([^,()]+,\s*"([a-z_]+)"\s+if\s+[^"]+\s+else\s+"([a-z_]+)\"""")


def check_icons(r: Result) -> None:
    available = {p.stem for p in (ROOT / "assets" / "icons").glob("*.svg")}
    used: set[str] = set()
    for path in sorted((ROOT / "src" / "ui").rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        found = set(_ICON_CALL.findall(text)) | {n for n in _ICON_TUPLE.findall(text) if n in available}
        for pair in _ICON_TERNARY.findall(text):
            found |= set(pair)
        for name in sorted(found - available):
            r.fail(f"{path.relative_to(ROOT)}: assets/icons/{name}.svg가 없습니다")
        used |= found
    # 표·사전으로 이름을 넘기는 곳(메뉴, 메시지 종류, QSS 이미지)은 위 패턴으로 찾지 못해 따로 적습니다.
    indirect = {"theme", "sun", "moon", "language", "info", "warning", "error_circle", "help", "check_circle",
                "chevron_down", "checkmark"}
    unused = sorted(available - used - indirect)
    if unused:
        r.warn(f"쓰이지 않는 아이콘: {', '.join(unused)}")


def run_tests(r: Result, quick: bool) -> None:
    patterns = ["test_core.py"] if quick else ["test_*.py"]
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", PYTHONWARNINGS="default")
    for pattern in patterns:
        proc = subprocess.run([PYTHON, "-m", "unittest", "discover", "-s", "tools", "-t", "tools", "-p", pattern],
                              cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                              env=env, timeout=900)
        summary = [line for line in proc.stderr.splitlines() if line.startswith(("Ran ", "OK", "FAILED"))]
        print("       " + " · ".join(summary))
        if proc.returncode != 0:
            failed = [line for line in proc.stderr.splitlines() if line.startswith(("FAIL:", "ERROR:"))]
            for line in failed or proc.stderr.splitlines()[-15:]:
                r.fail(line)
        skipped = re.search(r"skipped=(\d+)", proc.stderr)
        if skipped:
            r.warn(f"건너뛴 테스트 {skipped.group(1)}건 (ffmpeg가 없으면 종단 테스트를 건너뜁니다)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--quick", action="store_true", help="코어 단위 테스트만 실행")
    parser.add_argument("--no-pyright", action="store_true", help="pyright 단계 건너뛰기")
    args = parser.parse_args()

    print(f"APEX GIF MAKER 검사 — {ROOT}")
    results: list[tuple[str, Result, float]] = []
    step("환경", results, check_environment)
    step("문법", results, check_syntax)
    step("pyflakes", results, check_pyflakes)
    if not args.no_pyright:
        step("pyright (standard)", results, check_pyright)
    step(f"파일 길이 (경고 {WARN_LINES} / 실패 {FAIL_LINES}줄)", results, check_line_counts)
    step("다국어 사전", results, check_i18n)
    step("프로젝트 구성 (버전·CHANGELOG·assets·spec·아이콘)", results, check_project)
    step("문서 (README·RELEASE·소개 페이지 버전, 문서 그림)", results, check_docs)
    step("테스트" + (" (빠른 검사)" if args.quick else ""), results, lambda r: run_tests(r, args.quick))

    failed = [title for title, result, _ in results if result.failures]
    warned = sum(len(result.warnings) for _, result, _ in results)
    total = sum(elapsed for *_, elapsed in results)
    print()
    if failed:
        print(f"실패: {', '.join(failed)}  (경고 {warned}건, {total:.1f}s)")
        return 1
    print(f"모든 검사를 통과했습니다. (경고 {warned}건, {total:.1f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
