# theme.py
"""라이트/다크 테마의 색 토큰과 QSS를 한곳에서 만듭니다.

직접 그리는 위젯(타임라인, 프리뷰)도 current()로 같은 색을 씁니다.
테마가 바뀌면 manager().changed 신호가 나가고, 아이콘은 icons.refresh_all()로 다시 칠합니다.
"""
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication, QPalette
from PySide6.QtWidgets import QApplication

from . import fonts


# 색 방향: Flydigi Space Station처럼 검정에 가까운 짙은 남색 바탕에, 앱 로고(assets/applogo.svg)의
# 파란색 #398FE1 / #0867C4 / #044586을 강조색으로 씁니다. 기본 테마는 다크(남색)입니다.
@dataclass(frozen=True)
class Palette:
    name: str
    window_top: str      # 창 배경 그라데이션 위쪽
    window: str          # 창 배경 그라데이션 아래쪽
    surface: str
    surface_alt: str
    surface_hover: str
    border: str
    border_strong: str
    text: str
    text_muted: str
    text_faint: str
    accent: str
    accent_hover: str
    accent_pressed: str
    accent_text: str
    accent_soft: str
    select: str          # 타임라인 선택 구간 테두리·핸들
    select_text: str
    success: str
    warning: str
    danger: str
    danger_soft: str
    media_bg: str        # 프리뷰·필름스트립 배경 (테마와 관계없이 어둡게)

    @property
    def is_dark(self) -> bool:
        return self.name == "dark"


DARK = Palette(
    name="dark", window_top="#0b1527", window="#060b16", surface="#0d1729", surface_alt="#122038",
    surface_hover="#19294a", border="#1b2b47", border_strong="#29406a", text="#e7eef9", text_muted="#95a6c4",
    text_faint="#5a6b8c", accent="#398fe1", accent_hover="#5aa7f0", accent_pressed="#0867c4",
    accent_text="#ffffff", accent_soft="rgba(57, 143, 225, 0.18)", select="#4cb4ff", select_text="#03152b",
    success="#34d399", warning="#fbbf24", danger="#f87171", danger_soft="rgba(248, 113, 113, 0.14)",
    media_bg="#03070e",
)
LIGHT = Palette(
    name="light", window_top="#f4f7fd", window="#e8eef8", surface="#ffffff", surface_alt="#f3f7fd",
    surface_hover="#e3ebf7", border="#d5e0ef", border_strong="#b7c8e1", text="#0b1730", text_muted="#4d5f7e",
    text_faint="#8d9bb5", accent="#0867c4", accent_hover="#1a78d4", accent_pressed="#044586",
    accent_text="#ffffff", accent_soft="rgba(8, 103, 196, 0.12)", select="#0a84ff", select_text="#ffffff",
    success="#15803d", warning="#b45309", danger="#dc2626", danger_soft="rgba(220, 38, 38, 0.09)",
    media_bg="#0a1222",
)


def system_prefers_dark() -> bool:
    hints = QGuiApplication.styleHints()
    return hints is not None and hints.colorScheme() == Qt.ColorScheme.Dark


def resolve(mode: str) -> Palette:
    if mode == "dark":
        return DARK
    if mode == "light":
        return LIGHT
    return DARK if system_prefers_dark() else LIGHT


def qpalette(p: Palette) -> QPalette:
    """QSS가 닿지 않는 곳(체크 표시, 포커스 표시, 기본 대화상자 등)에 쓰일 팔레트입니다."""
    pal = QPalette()
    role, group = QPalette.ColorRole, QPalette.ColorGroup
    pairs = {
        role.Window: p.window, role.WindowText: p.text, role.Base: p.surface_alt,
        role.AlternateBase: p.surface, role.Text: p.text, role.Button: p.surface_alt,
        role.ButtonText: p.text, role.BrightText: p.danger, role.Highlight: p.accent,
        role.HighlightedText: p.accent_text, role.ToolTipBase: p.surface, role.ToolTipText: p.text,
        role.PlaceholderText: p.text_faint, role.Link: p.accent, role.LinkVisited: p.accent,
        role.Light: p.surface_hover, role.Midlight: p.border, role.Mid: p.border_strong,
        role.Dark: p.border_strong, role.Shadow: "#000000",
    }
    for color_role, value in pairs.items():
        pal.setColor(color_role, QColor(value))
    for color_role in (role.Text, role.WindowText, role.ButtonText):
        pal.setColor(group.Disabled, color_role, QColor(p.text_faint))
    return pal


def build_qss(p: Palette, families: list[str]) -> str:
    from . import icons  # icons가 current()를 쓰므로 순환 import를 피합니다.

    arrow = icons.icon_file("chevron_down", p.text_muted, 16)
    check = icons.icon_file("checkmark", p.accent_text, 14)
    stack = fonts.css_stack(families)
    mono = fonts.css_stack([fonts.mono_family(), *fonts.MONO_FALLBACKS])
    return f"""
QWidget {{ color: {p.text}; font-family: {stack}; font-size: 10pt; }}
QWidget#WindowSurface {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {p.window_top}, stop:1 {p.window});
    border: 1px solid {p.border_strong}; border-radius: 10px; }}
QWidget#WindowSurface[fullBleed="true"] {{ border: none; border-radius: 0px; }}
QWidget#TitleBar, QWidget#DialogTitleBar, QWidget#DialogBody, QWidget#Content {{ background: transparent; }}
QLabel {{ background: transparent; }}
QLabel#AppTitle {{ font-size: 10.5pt; font-weight: 800; letter-spacing: 0.4px; }}
QLabel#DialogTitle {{ font-weight: 700; }}
QLabel#Heading {{ font-size: 12.5pt; font-weight: 800; }}
QLabel#VideoName {{ font-weight: 700; }}
QLabel#Muted, QLabel#VideoMeta, QLabel#Hint, QLabel#FieldLabel {{ color: {p.text_muted}; }}
QLabel#Hint, QLabel#FieldLabel {{ font-size: 9pt; }}
QLabel#CardTitle {{ font-weight: 800; }}
QLabel#Chip {{ color: {p.text_muted}; background: {p.surface_alt}; border: 1px solid {p.border};
    border-radius: 9px; padding: 1px 8px; font-size: 8.5pt; }}
QLabel#Chip[tone="accent"] {{ color: {p.accent}; }}
QLabel#Chip[tone="success"] {{ color: {p.success}; }}
QLabel#Chip[tone="warning"] {{ color: {p.warning}; border-color: {p.warning}; }}
QLabel#Chip[tone="danger"] {{ color: {p.danger}; border-color: {p.danger}; }}
QFrame#Card {{ background: {p.surface}; border: 1px solid {p.border}; border-radius: 12px; }}
QFrame#Separator {{ background: {p.border}; border: none; max-width: 1px; min-width: 1px; }}

QPushButton {{ background: {p.surface_alt}; border: 1px solid {p.border}; border-radius: 8px;
    padding: 6px 14px; font-weight: 600; }}
QPushButton:hover {{ background: {p.surface_hover}; border-color: {p.border_strong}; }}
QPushButton:pressed {{ background: {p.border}; }}
QPushButton:disabled {{ color: {p.text_faint}; background: {p.surface_alt}; border-color: {p.border}; }}
QPushButton[variant="primary"] {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {p.accent_hover}, stop:1 {p.accent});
    color: {p.accent_text}; border-color: {p.accent}; }}
QPushButton[variant="primary"]:hover {{ background: {p.accent_hover}; border-color: {p.accent_hover}; }}
QPushButton[variant="primary"]:pressed {{ background: {p.accent_pressed}; }}
QPushButton[variant="primary"]:disabled {{ background: {p.surface_hover}; color: {p.text_faint}; border-color: {p.border}; }}
QPushButton[variant="danger"] {{ background: {p.danger}; color: #ffffff; border-color: {p.danger}; }}
QPushButton[size="large"] {{ padding: 10px 18px; font-size: 11pt; font-weight: 800; border-radius: 10px; }}
QToolButton {{ background: transparent; border: 1px solid transparent; border-radius: 7px; padding: 4px; }}
QToolButton:hover {{ background: {p.surface_hover}; }}
QToolButton:pressed, QToolButton:checked {{ background: {p.border}; }}
QToolButton::menu-indicator {{ image: none; width: 0px; }}
QToolButton[framed="true"] {{ background: {p.surface_alt}; border-color: {p.border}; }}
QToolButton[framed="true"]:hover {{ background: {p.surface_hover}; border-color: {p.border_strong}; }}
QToolButton#WinButton {{ border-radius: 6px; padding: 6px; }}
QToolButton#WinClose:hover {{ background: {p.danger}; border-color: {p.danger}; }}

QLineEdit, QAbstractSpinBox, QComboBox {{ background: {p.surface_alt}; border: 1px solid {p.border};
    border-radius: 7px; padding: 5px 8px; selection-background-color: {p.accent}; selection-color: {p.accent_text}; }}
QLineEdit:hover, QAbstractSpinBox:hover, QComboBox:hover {{ border-color: {p.border_strong}; }}
QLineEdit:focus, QAbstractSpinBox:focus, QComboBox:focus {{ border-color: {p.accent}; }}
QLineEdit:disabled, QAbstractSpinBox:disabled, QComboBox:disabled {{ color: {p.text_faint}; }}
QLineEdit[invalid="true"] {{ border-color: {p.danger}; background: {p.danger_soft}; }}
QLineEdit#TimeInput {{ font-family: {mono}; font-size: 10pt; }}
QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {{ width: 0px; border: none; }}
QComboBox {{ padding-right: 26px; }}
QComboBox::drop-down {{ subcontrol-origin: padding; subcontrol-position: center right; width: 24px; border: none; }}
QComboBox::down-arrow {{ image: url("{arrow}"); width: 12px; height: 12px; }}
QComboBox QAbstractItemView {{ background: {p.surface}; border: 1px solid {p.border_strong}; padding: 4px;
    outline: 0; selection-background-color: {p.surface_hover}; selection-color: {p.text}; }}
QComboBox QAbstractItemView::item {{ min-height: 26px; padding: 2px 8px; }}

QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border: 1px solid {p.border_strong}; border-radius: 4px;
    background: {p.surface_alt}; }}
QCheckBox::indicator:checked {{ background: {p.accent}; border-color: {p.accent}; image: url("{check}"); }}

QMenu {{ background: {p.surface}; border: 1px solid {p.border_strong}; padding: 5px; }}
QMenu::item {{ padding: 6px 26px 6px 10px; border-radius: 6px; }}
QMenu::item:selected {{ background: {p.surface_hover}; }}
QMenu::item:disabled {{ color: {p.text_faint}; }}
QMenu::separator {{ height: 1px; background: {p.border}; margin: 5px 6px; }}
QMenu::icon {{ padding-left: 6px; }}

QToolTip {{ background: {p.surface}; color: {p.text}; border: 1px solid {p.border_strong}; padding: 5px 8px; }}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle {{ background: {p.border_strong}; border-radius: 3px; min-height: 24px; min-width: 24px; }}
QScrollBar::handle:hover {{ background: {p.text_faint}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0px; height: 0px; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QProgressBar {{ background: {p.surface_hover}; border: none; border-radius: 3px; min-height: 6px; max-height: 6px; }}
QProgressBar::chunk {{ background: {p.accent}; border-radius: 3px; }}

QPlainTextEdit#Log, QTextBrowser#Notes {{ background: {p.surface_alt}; border: 1px solid {p.border}; border-radius: 8px;
    padding: 6px; }}
QPlainTextEdit#Log {{ font-family: {mono}; font-size: 9pt; }}

QFrame#DropZone {{ background: {p.surface}; border: 2px dashed {p.border_strong}; border-radius: 14px; }}
QFrame#DropZone[active="true"] {{ border-color: {p.accent}; background: {p.accent_soft}; }}
QLabel#DropTitle {{ font-size: 13pt; font-weight: 800; }}
QFrame#TimeField {{ background: {p.surface_alt}; border: 1px solid {p.border}; border-radius: 8px; }}
QFrame#TimeField QLineEdit {{ background: transparent; border: none; padding: 4px 2px; }}
QFrame#TimeField[invalid="true"] {{ border-color: {p.danger}; }}
"""


class ThemeManager(QObject):
    """현재 테마를 들고 있다가, 바뀌면 changed를 보냅니다. (system 모드는 OS 설정 변경을 따라갑니다.)"""

    changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.mode = "dark"
        self.palette = DARK
        self.families: list[str] = []
        self._listening = False

    def apply(self, mode: str | None = None, families: list[str] | None = None) -> Palette:
        app = QApplication.instance()
        if mode is not None:
            self.mode = mode
        if families is not None:
            self.families = families
        self.palette = resolve(self.mode)
        if isinstance(app, QApplication):
            app.setPalette(qpalette(self.palette))
            app.setStyleSheet(build_qss(self.palette, self.families))
            self._listen()
        from . import icons
        icons.refresh_all()
        self.changed.emit()
        return self.palette

    def _listen(self) -> None:
        hints = QGuiApplication.styleHints()
        if self._listening or hints is None:
            return
        hints.colorSchemeChanged.connect(self._on_scheme_changed)
        self._listening = True

    def _on_scheme_changed(self, *_args) -> None:
        if self.mode == "system" and resolve("system") != self.palette:
            self.apply()


_manager: ThemeManager | None = None


def manager() -> ThemeManager:
    global _manager
    if _manager is None:
        _manager = ThemeManager()
    return _manager


def current() -> Palette:
    return manager().palette
