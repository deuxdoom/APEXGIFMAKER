# app.py
"""앱 시작 순서를 한곳에 둡니다.

- 일반 실행: 언어 → Qt 기본 위젯 번역 → 폰트 → 테마 → 단일 실행 확인 → 메인 창
- `--apply-update ...`: 업데이트 적용 창 (새 exe가 기존 파일을 교체)
- `--smoke-test`: 창을 띄우지 않고 번들 구성(폰트·아이콘·플러그인·메인 창 생성)을 점검 (빌드 검증용)
- 동영상 경로 인자: 그 파일을 엽니다. 이미 실행 중이면 기존 창으로 넘깁니다.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QLibraryInfo, QLocale, QTranslator
from PySide6.QtWidgets import QApplication

from .. import i18n
from ..core import config
from ..core.apply_update import parse_arguments
from ..core.settings import Settings, load_settings
from . import fonts, theme, win32
from .app_icon import app_icon

# 앱 언어 → Qt 번역 파일(qtbase_*.qm) 이름. 영어는 번역 파일이 필요 없습니다.
QT_TRANSLATIONS = {"ko": "ko", "ja": "ja", "es": "es", "zh-Hans": "zh_CN", "zh-Hant": "zh_TW"}
_translator: QTranslator | None = None


def system_language() -> str:
    """Windows 표시 언어(없으면 지역 설정)로 앱 언어를 고릅니다."""
    locale = QLocale.system()
    ui_languages = locale.uiLanguages()
    return i18n.detect_language(ui_languages[0] if ui_languages else locale.name())


def install_qt_translation(app: QApplication, language: str) -> None:
    """입력칸 오른쪽 클릭 메뉴 같은 Qt 기본 문구를 앱 언어로 맞춥니다."""
    global _translator
    code = QT_TRANSLATIONS.get(language)
    if not code:
        return
    translator = QTranslator(app)
    folders = (config.BUNDLE_DIR / "translations",
               Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)))
    for folder in folders:
        if translator.load(f"qtbase_{code}", str(folder)):
            app.installTranslator(translator)
            _translator = translator
            return


def prepare_app(app: QApplication, settings: Settings) -> str:
    language = settings.language if settings.language in i18n.LANGUAGES else system_language()
    i18n.set_language(language)
    install_qt_translation(app, language)
    app.setStyle("Fusion")
    app.setApplicationName(config.APP_NAME)
    app.setApplicationVersion(config.APP_VERSION)
    app.setWindowIcon(app_icon())
    families = fonts.setup_fonts(app, language)
    theme.manager().apply(settings.theme, families)
    return language


def file_argument(args: list[str]) -> str:
    for arg in args:
        if not arg.startswith("--") and Path(arg).is_file():
            return str(Path(arg).resolve())
    return ""


def run(argv: list[str]) -> int:
    args = argv[1:]
    win32.set_app_user_model_id(config.APP_USER_MODEL_ID)
    app = QApplication(argv)
    if args and args[0] == "--apply-update":
        return _run_apply_mode(app, args)

    settings, settings_error = load_settings()
    prepare_app(app, settings)
    if "--smoke-test" in args:
        from .smoke import run_smoke_test
        return run_smoke_test(app, settings)

    from . import dialogs
    from .main_window import MainWindow
    from .single_instance import SingleInstance, send_to_running

    file_arg = file_argument(args)
    instance = SingleInstance(app)
    if not instance.acquire():
        sent = send_to_running(f"open:{file_arg}" if file_arg else "activate")
        if not (sent and file_arg):
            dialogs.info(None, i18n.tr("app.already_running.text"), i18n.tr("app.already_running.title"))
        return 0

    window = MainWindow(settings, settings_error=settings_error, initial_file=file_arg)
    instance.activateRequested.connect(lambda: win32.bring_to_front(window))
    instance.openRequested.connect(window.open_video)
    window.show()
    try:
        return app.exec()
    finally:
        instance.release()


def _run_apply_mode(app: QApplication, args: list[str]) -> int:
    options = parse_arguments(args)
    # 적용 창은 새 버전 폴더(update-workspace/new)에서 실행되므로, 언어·테마는 앱 폴더의 설정에서 읽습니다.
    settings, _ = load_settings(options.app_dir / "settings.json") if options else (Settings(), None)
    prepare_app(app, settings)
    if options is None:
        return 2
    from .apply_window import ApplyWindow
    window = ApplyWindow(options)
    window.start()
    return app.exec()
