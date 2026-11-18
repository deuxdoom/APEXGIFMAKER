# output_panel.py
"""출력 카드: 저장 폴더, 파일 이름(자동 제안), GIF 생성/취소 버튼과 진행률."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLineEdit, QProgressBar, QWidget

from ...i18n import tr
from .. import icons
from .common import Card, ElidedLabel, make_button, make_icon_button, make_label, set_state

INVALID_FILENAME_CHARS = '<>:"/\\|?*'


class OutputPanel(Card):
    generateRequested = Signal()
    cancelRequested = Signal()
    chooseFolderRequested = Signal()
    openFolderRequested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(tr("output.title"), parent)
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)

        self.folder_edit = QLineEdit()
        self.folder_edit.setPlaceholderText(tr("output.folder.placeholder"))
        self.choose_button = make_icon_button("folder", tr("output.folder.choose"), framed=True, size=16)
        self.open_button = make_icon_button("open_external", tr("output.folder.open"), framed=True, size=16)
        folder_row = QHBoxLayout()
        folder_row.setSpacing(6)
        folder_row.addWidget(self.folder_edit, 1)
        folder_row.addWidget(self.choose_button)
        folder_row.addWidget(self.open_button)

        self.name_edit = QLineEdit()
        self.auto_button = make_icon_button("sparkle", tr("output.filename.auto"), framed=True, size=16,
                                            role="accent")
        self.auto_button.setVisible(False)
        name_row = QHBoxLayout()
        name_row.setSpacing(6)
        name_row.addWidget(self.name_edit, 1)
        name_row.addWidget(self.auto_button)

        grid.addWidget(make_label(tr("output.folder"), "FieldLabel"), 0, 0)
        grid.addLayout(folder_row, 0, 1)
        grid.addWidget(make_label(tr("output.filename"), "FieldLabel"), 1, 0)
        grid.addLayout(name_row, 1, 1)
        grid.setColumnStretch(1, 1)
        self.body.addLayout(grid)

        self.generate_button = make_button(tr("output.generate"), "gif", variant="primary", size="large",
                                           tooltip=tr("output.generate.tip"))
        self.body.addWidget(self.generate_button)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.stage_label = ElidedLabel("", "Hint")
        progress_row = QHBoxLayout()
        progress_row.setSpacing(8)
        progress_row.addWidget(self.progress, 1)
        progress_row.addWidget(self.stage_label, 1)
        self.body.addLayout(progress_row)
        self.body.addStretch(1)
        self.progress.setVisible(False)
        self.stage_label.setVisible(False)

        self._auto_name = ""
        self._user_named = False
        self._busy = False
        self.generate_button.clicked.connect(self._on_button)
        self.choose_button.clicked.connect(self.chooseFolderRequested.emit)
        self.open_button.clicked.connect(self.openFolderRequested.emit)
        self.auto_button.clicked.connect(self.use_auto_name)
        self.name_edit.textEdited.connect(self._name_edited)

    # --- 폴더와 파일 이름 ---
    def folder(self) -> str:
        return self.folder_edit.text().strip()

    def set_folder(self, path: str) -> None:
        self.folder_edit.setText(path)

    def filename(self) -> str:
        name = self.name_edit.text().strip()
        if name and not name.lower().endswith(".gif"):
            name += ".gif"
        return name

    def invalid_chars(self) -> str:
        return "".join(sorted({c for c in self.filename() if c in INVALID_FILENAME_CHARS}))

    def set_auto_name(self, name: str) -> None:
        """자동 이름을 갱신합니다. 사용자가 직접 고친 이름은 덮어쓰지 않습니다."""
        self._auto_name = name
        if not self._user_named:
            self.name_edit.setText(name)

    def use_auto_name(self) -> None:
        self._set_user_named(False)
        self.name_edit.setText(self._auto_name)

    def reset_name(self, name: str) -> None:
        """새 동영상을 열면 사용자 이름 지정을 풀고 자동 이름으로 돌아갑니다."""
        self._set_user_named(False)
        self.set_auto_name(name)

    def _name_edited(self, text: str) -> None:
        self._set_user_named(bool(self._auto_name) and bool(text.strip()) and text.strip() != self._auto_name)

    def _set_user_named(self, value: bool) -> None:
        self._user_named = value
        self.auto_button.setVisible(value)

    # --- 생성 상태 ---
    def is_busy(self) -> bool:
        return self._busy

    def _on_button(self) -> None:
        (self.cancelRequested if self._busy else self.generateRequested).emit()

    def set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.generate_button.setText(tr("output.cancel") if busy else tr("output.generate"))
        set_state(self.generate_button, "variant", "danger" if busy else "primary")
        icons.set_icon(self.generate_button, "dismiss" if busy else "gif", "on_accent", 18)
        for widget in (self.folder_edit, self.choose_button, self.name_edit, self.auto_button):
            widget.setEnabled(not busy)
        self.progress.setVisible(busy)
        self.stage_label.setVisible(busy)
        if busy:
            self.set_stage("", None)

    def set_stage(self, text: str, fraction: float | None) -> None:
        """fraction이 None이면 진행 막대를 움직이는(끝을 모르는) 상태로 둡니다."""
        self.stage_label.setText(text)
        if fraction is None:
            self.progress.setRange(0, 0)
        else:
            self.progress.setRange(0, 1000)
            self.progress.setValue(int(fraction * 1000))

    def set_ready(self, ready: bool) -> None:
        if not self._busy:
            self.generate_button.setEnabled(ready)
