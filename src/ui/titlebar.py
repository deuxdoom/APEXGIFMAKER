# titlebar.py
"""메인 창의 제목 표시줄: 앱 이름, 동영상 열기와 현재 파일 정보, 설정·정보, 창 단추."""
from __future__ import annotations

from PySide6.QtCore import QEvent, Signal
from PySide6.QtGui import QEnterEvent
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QMenu, QToolButton, QWidget

from ..core import config
from ..i18n import tr
from . import icons, theme
from .frame import DragBar, app_icon_pixmap, make_tool_button
from .widgets.common import Chip, ElidedLabel, make_button, make_label

TITLE_HEIGHT = 50


class _CloseButton(QToolButton):
    """마우스를 올리면 빨간 배경 위에서 보이도록 아이콘을 흰색으로 바꿉니다."""

    def enterEvent(self, arg__1: QEnterEvent) -> None:
        icons.set_icon(self, "dismiss", "on_accent", 16)
        super().enterEvent(arg__1)

    def leaveEvent(self, leaveEvent: QEvent) -> None:
        icons.set_icon(self, "dismiss", "text", 16)
        super().leaveEvent(leaveEvent)


class TitleBar(DragBar):
    openRequested = Signal()
    aboutRequested = Signal()
    minimizeRequested = Signal()
    maximizeRequested = Signal()
    closeRequested = Signal()

    def __init__(self, settings_menu: QMenu, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("TitleBar")
        self.setFixedHeight(TITLE_HEIGHT)
        row = QHBoxLayout(self)
        row.setContentsMargins(16, 0, 8, 0)
        row.setSpacing(8)

        logo = QLabel()
        logo.setPixmap(app_icon_pixmap(22))
        row.addWidget(logo)
        self.title_label = make_label("", "AppTitle")
        row.addWidget(self.title_label)
        row.addWidget(Chip(f"v{config.APP_VERSION}"))
        row.addSpacing(10)
        separator = QFrame()
        separator.setObjectName("Separator")
        separator.setFixedHeight(22)
        row.addWidget(separator)
        row.addSpacing(6)

        self.open_button = make_button(tr("top.open"), "folder_open", tooltip=tr("top.open.tip"))
        row.addWidget(self.open_button)
        row.addSpacing(4)
        self.video_name = ElidedLabel(tr("top.no_video"), "Muted")
        self.video_meta = make_label("", "VideoMeta")
        row.addWidget(self.video_name, 1)
        row.addWidget(self.video_meta)
        row.addSpacing(8)

        self.menu_button = make_tool_button("settings", tr("top.menu.tip"))
        self.menu_button.setMenu(settings_menu)
        self.menu_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.about_button = make_tool_button("info", tr("menu.about"))
        row.addWidget(self.menu_button)
        row.addWidget(self.about_button)
        row.addSpacing(6)

        self.min_button = make_tool_button("minimize", tr("win.minimize"), size=16, object_name="WinButton")
        self.max_button = make_tool_button("maximize", tr("win.maximize"), size=16, object_name="WinButton")
        self.close_button = _CloseButton()
        self.close_button.setObjectName("WinClose")
        self.close_button.setToolTip(tr("win.close"))
        icons.set_icon(self.close_button, "dismiss", "text", 16)
        for button in (self.min_button, self.max_button, self.close_button):
            row.addWidget(button)

        self._paint_title()
        theme.manager().changed.connect(self._paint_title)
        self.open_button.clicked.connect(self.openRequested.emit)
        self.about_button.clicked.connect(self.aboutRequested.emit)
        self.min_button.clicked.connect(self.minimizeRequested.emit)
        self.max_button.clicked.connect(self.maximizeRequested.emit)
        self.close_button.clicked.connect(self.closeRequested.emit)

    def _paint_title(self) -> None:
        """앱 이름의 'APEX'를 로고와 같은 파란색으로 표시합니다."""
        first, _, rest = config.APP_NAME.partition(" ")
        self.title_label.setText(f"<span style='color:{theme.current().accent}'>{first}</span> {rest}")

    def set_video(self, name: str, meta: str) -> None:
        self.video_name.setObjectName("VideoName")
        self.video_name.setText(name)
        self.video_meta.setText(meta)
        self._repolish(self.video_name)

    def clear_video(self) -> None:
        self.video_name.setObjectName("Muted")
        self.video_name.setText(tr("top.no_video"))
        self.video_meta.setText("")
        self._repolish(self.video_name)

    def set_maximized(self, maximized: bool) -> None:
        icons.set_icon(self.max_button, "restore" if maximized else "maximize", "text", 16)
        self.max_button.setToolTip(tr("win.restore" if maximized else "win.maximize"))

    @staticmethod
    def _repolish(widget: QWidget) -> None:
        style = widget.style()
        style.unpolish(widget)
        style.polish(widget)
