# fonts.py
"""번들 폰트 3종을 등록하고 앱 기본 폰트를 정합니다.

- PretendardVariable: 라틴·한글, 모든 굵기 (본문)
- PretendardJP-Regular: 일본어 가나·한자 (본문 대체)
- JetBrainsMono-Regular: 로그용 고정폭

힌팅은 끕니다(PreferNoHinting). QSS에 font 속성이 있으면 Qt가 QFont를 새로 만들어 힌팅 설정이
빠지므로, FontRenderingGuard가 위젯마다 다시 입힙니다. (참고: TVerDownloader의 app_setup.py)
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, QObject
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication, QWidget

from ..core import config

UI_FONT_FILES = ("PretendardVariable.ttf", "PretendardJP-Regular.ttf")
MONO_FONT_FILE = "JetBrainsMono-Regular.ttf"
MONO_FALLBACKS = ("Cascadia Mono", "Consolas")

HINTING = QFont.HintingPreference.PreferNoHinting
STRATEGY = QFont.StyleStrategy.PreferAntialias | QFont.StyleStrategy.PreferQuality

# 한자 글리프는 언어마다 모양이 달라서, 중국어에서는 Pretendard JP(일본식 한자)보다 중국어 글꼴을 앞에 둡니다.
_CJK_BY_LANGUAGE: dict[str, tuple[str, ...]] = {
    "ja": ("Yu Gothic UI", "Meiryo UI"),
    "zh-Hans": ("Microsoft YaHei UI", "Microsoft YaHei"),
    "zh-Hant": ("Microsoft JhengHei UI", "Microsoft JhengHei"),
}
_SYSTEM_FALLBACKS = ("Malgun Gothic", "Yu Gothic UI", "Segoe UI")

_families: dict[str, str] = {}
_guard: "FontRenderingGuard | None" = None


def _register(file_name: str) -> str:
    if file_name in _families:
        return _families[file_name]
    path = config.asset_path(f"fonts/{file_name}")
    font_id = QFontDatabase.addApplicationFont(str(path)) if path.is_file() else -1
    names = QFontDatabase.applicationFontFamilies(font_id) if font_id != -1 else []
    _families[file_name] = names[0] if names else ""
    return _families[file_name]


def ui_families(language: str) -> list[str]:
    """언어에 맞춘 본문 폰트 순서. 번들 등록에 실패한 폰트는 빠지고 시스템 폰트가 이어받습니다."""
    main = _register(UI_FONT_FILES[0])
    japanese = _register(UI_FONT_FILES[1])
    cjk = _CJK_BY_LANGUAGE.get(language, ())
    ordered = [main, *cjk, japanese] if language.startswith("zh") else [main, japanese, *cjk]
    result: list[str] = []
    for name in (*ordered, *_SYSTEM_FALLBACKS):
        if name and name not in result:
            result.append(name)
    return result


def mono_family() -> str:
    return _register(MONO_FONT_FILE) or MONO_FALLBACKS[0]


def css_stack(families: list[str]) -> str:
    return ", ".join(f'"{name}"' for name in families)


def apply_rendering(font: QFont) -> QFont:
    font.setHintingPreference(HINTING)
    font.setStyleStrategy(STRATEGY)
    return font


class FontRenderingGuard(QObject):
    """스타일시트가 새로 만든 폰트에 힌팅·안티앨리어싱 설정을 다시 입힙니다."""

    WATCHED = (QEvent.Type.Polish, QEvent.Type.FontChange, QEvent.Type.StyleChange)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() in self.WATCHED and isinstance(watched, QWidget):
            font = watched.font()
            if font.hintingPreference() != HINTING or font.styleStrategy() != STRATEGY:
                watched.setFont(apply_rendering(font))
        return super().eventFilter(watched, event)


def setup_fonts(app: QApplication, language: str) -> list[str]:
    """번들 폰트를 등록하고 앱 기본 폰트를 지정합니다. QSS에 쓸 폰트 순서를 반환합니다."""
    global _guard
    families = ui_families(language)
    mono_family()
    font = QFont()
    font.setFamilies(families)
    font.setPointSizeF(10.0)
    app.setFont(apply_rendering(font))
    if _guard is None:
        _guard = FontRenderingGuard(app)
        app.installEventFilter(_guard)
    return families
