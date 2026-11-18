# log_panel.py
"""접을 수 있는 로그 패널. 접혀 있어도 마지막 메시지와 ffmpeg 상태가 한 줄로 보입니다."""
from __future__ import annotations

import time

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QPlainTextEdit, QVBoxLayout, QWidget

from ...i18n import tr
from .. import icons
from .common import Chip, ElidedLabel, make_button, make_icon_button

MAX_LINES = 3000


class LogPanel(QWidget):
    toggled = Signal(bool)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        header = QHBoxLayout()
        header.setSpacing(8)
        self.toggle_button = make_button(tr("log.title"), "chevron_right")
        self.toggle_button.setFlat(True)
        self.last_line = ElidedLabel("", "Hint")
        self.ffmpeg_chip = Chip("")
        self.clear_button = make_icon_button("delete", tr("log.clear"), role="muted", size=16)
        header.addWidget(self.toggle_button)
        header.addWidget(self.last_line, 1)
        header.addWidget(self.ffmpeg_chip)
        header.addWidget(self.clear_button)
        layout.addLayout(header)
        self.text = QPlainTextEdit()
        self.text.setObjectName("Log")
        self.text.setReadOnly(True)
        self.text.setMaximumBlockCount(MAX_LINES)
        self.text.setFixedHeight(150)
        self.text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        layout.addWidget(self.text)
        self._expanded = True
        self.set_expanded(False)
        self.toggle_button.clicked.connect(lambda: self.set_expanded(not self._expanded))
        self.clear_button.clicked.connect(self.clear)

    def expanded(self) -> bool:
        return self._expanded

    def set_expanded(self, expanded: bool) -> None:
        if expanded == self._expanded:
            return
        self._expanded = expanded
        self.text.setVisible(expanded)
        icons.set_icon(self.toggle_button, "chevron_down" if expanded else "chevron_right", "muted", 16)
        self.toggled.emit(expanded)

    def append(self, line: str) -> None:
        stamp = time.strftime("%H:%M:%S")
        for part in str(line).splitlines() or [""]:
            self.text.appendPlainText(f"[{stamp}] {part}")
        last = str(line).strip().splitlines()
        if last:
            self.last_line.setText(last[-1])
        bar = self.text.verticalScrollBar()
        bar.setValue(bar.maximum())

    def clear(self) -> None:
        self.text.clear()
        self.last_line.setText("")

    def set_ffmpeg_status(self, text: str, tone: str) -> None:
        self.ffmpeg_chip.setText(text)
        self.ffmpeg_chip.set_tone(tone)
