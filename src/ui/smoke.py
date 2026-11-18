# smoke.py
"""`--smoke-test`: 빌드된 exe가 필요한 것을 모두 갖췄는지 창을 띄우지 않고 확인합니다.

PyInstaller는 개발 환경에서 멀쩡하던 것을 빠뜨릴 수 있습니다(데이터 파일, Qt 플러그인, 숨은 import).
tools/build.py가 빌드 직후 이 모드로 exe를 실행해 종료 코드로 판정합니다.
결과는 표준 출력과, APEX_SMOKE_REPORT 환경 변수가 가리키는 파일(JSON)에 남깁니다. (창 모드 exe는 콘솔이 없음)
"""
from __future__ import annotations

import json
import os
from dataclasses import replace

from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QImageReader
from PySide6.QtWidgets import QApplication

from .. import i18n
from ..core import config
from ..core.settings import Settings
from . import fonts, icons, theme


def run_smoke_test(app: QApplication, settings: Settings) -> int:
    problems: list[str] = []
    for name in ("applogo.svg", "appicon.ico", "fonts/PretendardVariable.ttf", "fonts/PretendardJP-Regular.ttf",
                 "fonts/JetBrainsMono-Regular.ttf", "icons/gif.svg"):
        if not config.asset_path(name).is_file():
            problems.append(f"missing asset: {name}")
    families = fonts.ui_families(i18n.language())
    if not families or "Pretendard" not in families[0]:
        problems.append(f"bundled font not registered: {families[:1]}")
    if icons.pixmap("gif", "#ffffff", 16).isNull():
        problems.append("icon rendering failed")
    formats = {bytes(f.data()).decode() for f in QImageReader.supportedImageFormats()}
    for needed in ("gif", "jpeg", "png"):
        if needed not in formats:
            problems.append(f"missing Qt image plugin: {needed}")
    try:  # 업데이트 확인과 ffmpeg 다운로드가 쓰는 HTTPS(파이썬 ssl + OpenSSL DLL)
        import ssl
        ssl.create_default_context()
    except Exception as exc:
        problems.append(f"ssl unavailable: {exc!r}")
    from . import app as app_module
    if app_module.QT_TRANSLATIONS.get(i18n.language()) and app_module._translator is None:
        problems.append(f"Qt translation not loaded for {i18n.language()}")

    from .main_window import MainWindow
    try:
        window = MainWindow(replace(settings, confirm_exit=False), background=False, persist=False)
        window.show()
        QCoreApplication.processEvents()
        for mode in ("light", "dark"):
            theme.manager().apply(mode)
            window.grab()
        window.close()
    except Exception as exc:  # 스모크 테스트는 어떤 실패든 보고해야 합니다.
        problems.append(f"main window failed: {exc!r}")

    report = {"ok": not problems, "version": config.APP_VERSION, "problems": problems,
              "language": i18n.language(), "fonts": families[:2]}
    print(json.dumps(report, ensure_ascii=False))
    target = os.environ.get("APEX_SMOKE_REPORT")
    if target:
        try:
            with open(target, "w", encoding="utf-8") as out:
                json.dump(report, out, ensure_ascii=False, indent=2)
        except OSError:
            pass
    return 0 if not problems else 1
