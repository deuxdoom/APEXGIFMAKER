# common.py
"""여러 화면에서 함께 쓰는 작은 위젯과 도우미입니다."""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton,
                               QSizePolicy, QToolButton, QVBoxLayout, QWidget)

from ...i18n import tr
from .. import icons


def repolish(widget: QWidget) -> None:
    """동적 속성을 바꾼 뒤 QSS를 다시 적용합니다."""
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()


def set_state(widget: QWidget, name: str, value: str | bool) -> None:
    text = ("true" if value else "false") if isinstance(value, bool) else value
    if widget.property(name) != text:
        widget.setProperty(name, text)
        repolish(widget)


def make_button(text: str, icon_name: str = "", *, variant: str = "", size: str = "",
                tooltip: str = "", parent: QWidget | None = None) -> QPushButton:
    button = QPushButton(text, parent)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    if variant:
        button.setProperty("variant", variant)
    if size:
        button.setProperty("size", size)
    if tooltip:
        button.setToolTip(tooltip)
    if icon_name:
        role = "on_accent" if variant in ("primary", "danger") else "text"
        icons.set_icon(button, icon_name, role, 18 if size == "large" else 16)
    return button


def make_icon_button(icon_name: str, tooltip: str = "", *, role: str = "text", size: int = 18,
                     framed: bool = False, parent: QWidget | None = None) -> QToolButton:
    button = QToolButton(parent)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setToolTip(tooltip)
    button.setFocusPolicy(Qt.FocusPolicy.TabFocus)
    if framed:
        button.setProperty("framed", "true")
    icons.set_icon(button, icon_name, role, size)
    return button


def make_label(text: str = "", object_name: str = "", parent: QWidget | None = None) -> QLabel:
    label = QLabel(text, parent)
    if object_name:
        label.setObjectName(object_name)
    return label


class Chip(QLabel):
    """작은 알약 모양 라벨. tone: neutral | accent | success | warning | danger"""

    def __init__(self, text: str = "", tone: str = "neutral", parent: QWidget | None = None):
        super().__init__(text, parent)
        self.setObjectName("Chip")
        self.setProperty("tone", tone)
        # 줄 높이만큼 늘어나지 않고 글자 크기에 맞는 알약 모양을 유지합니다.
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def set_tone(self, tone: str) -> None:
        set_state(self, "tone", tone)


class ElidedLabel(QLabel):
    """폭이 모자라면 말줄임표로 줄이고, 전체 문장은 툴팁으로 보여 줍니다."""

    def __init__(self, text: str = "", object_name: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        if object_name:
            self.setObjectName(object_name)
        self._full = text
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setMinimumWidth(40)
        self._refresh()

    def setText(self, text: str) -> None:
        self._full = text
        self._refresh()

    def full_text(self) -> str:
        return self._full

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._refresh()

    def _refresh(self) -> None:
        width = max(10, self.width())
        elided = self.fontMetrics().elidedText(self._full, Qt.TextElideMode.ElideMiddle, width)
        super().setText(elided)
        self.setToolTip(self._full if elided != self._full else "")


class Card(QFrame):
    """둥근 테두리 상자. header에 제목과 오른쪽 부품을 두고, body에 내용을 담습니다."""

    def __init__(self, title: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Card")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 10, 14, 12)
        outer.setSpacing(8)
        self.header = QHBoxLayout()
        self.header.setSpacing(6)
        self.title_label = make_label(title, "CardTitle")
        self.header.addWidget(self.title_label)
        outer.addLayout(self.header)
        self.body = QVBoxLayout()
        self.body.setSpacing(8)
        outer.addLayout(self.body, 1)
        self.title_label.setVisible(bool(title))


class TimeField(QWidget):
    """라벨 + [◀ 입력칸 ▶]. Enter나 포커스 이동 때 값을 읽고, ◀▶는 0.1초(Shift: 1초)씩 움직입니다."""

    edited = Signal(float)
    nudged = Signal(float)

    def __init__(self, caption: str, formatter: Callable[[float], str], parser: Callable[[str], float],
                 width: int = 104, parent: QWidget | None = None):
        super().__init__(parent)
        self._format = formatter
        self._parse = parser
        self._shown = ""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        layout.addWidget(make_label(caption, "FieldLabel"))
        self.box = QFrame()
        self.box.setObjectName("TimeField")
        row = QHBoxLayout(self.box)
        row.setContentsMargins(2, 1, 2, 1)
        row.setSpacing(0)
        self.back = make_icon_button("chevron_left", tr("field.back"), role="muted", size=14)
        self.forward = make_icon_button("chevron_right", tr("field.forward"), role="muted", size=14)
        self.edit = QLineEdit()
        self.edit.setObjectName("TimeInput")
        self.edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.edit.setFixedWidth(width)
        row.addWidget(self.back)
        row.addWidget(self.edit)
        row.addWidget(self.forward)
        layout.addWidget(self.box)
        self.back.clicked.connect(lambda: self._nudge(-1))
        self.forward.clicked.connect(lambda: self._nudge(1))
        self.edit.editingFinished.connect(self._commit)
        self._flash = QTimer(self)
        self._flash.setSingleShot(True)
        self._flash.setInterval(1600)
        self._flash.timeout.connect(lambda: set_state(self.box, "invalid", False))

    def set_value(self, seconds: float) -> None:
        self._shown = self._format(seconds)
        if not self.edit.hasFocus() or self.edit.text() == self._shown:
            self.edit.setText(self._shown)

    def force_value(self, seconds: float) -> None:
        self._shown = self._format(seconds)
        self.edit.setText(self._shown)

    def _commit(self) -> None:
        text = self.edit.text()
        if text == self._shown:
            return
        try:
            value = self._parse(text)
        except ValueError:
            self.edit.setText(self._shown)
            set_state(self.box, "invalid", True)
            self.box.setToolTip(tr("field.invalid"))
            self._flash.start()
            return
        set_state(self.box, "invalid", False)
        self.edited.emit(value)

    def _nudge(self, direction: int) -> None:
        shift = QApplication.keyboardModifiers() & Qt.KeyboardModifier.ShiftModifier
        self.nudged.emit(direction * (1.0 if shift else 0.1))

    def clear(self) -> None:
        self.edit.clear()
        self._shown = ""
