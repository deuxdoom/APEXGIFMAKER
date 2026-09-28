# apply_window.py
"""`--apply-update` 모드의 창. 새 exe가 기존 파일을 교체하는 과정을 단계별로 보여 줍니다."""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QVBoxLayout, QWidget

from ..core.apply_update import ApplyOptions
from ..i18n import tr
from versioninfo import APP_VERSION
from . import icons
from .frame import DialogTitleBar, ShadowShell, center_on_screen, make_frameless
from .widgets.common import make_button, make_label
from .workers import ApplyUpdateJob

STEPS = ("wait", "backup", "install", "launch")
_STAGE_TO_STEP = {"waiting": 0, "backing_up": 1, "installing": 2, "launching": 3, "done": 4}


class ApplyWindow(QWidget):
    def __init__(self, options: ApplyOptions):
        super().__init__()
        make_frameless(self)
        self.setWindowTitle(tr("apply.title"))
        self.setFixedWidth(460)
        self.options = options
        shell = ShadowShell(resizable=False)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(shell)
        surface = QVBoxLayout(shell.surface)
        surface.setContentsMargins(0, 0, 0, 0)
        surface.setSpacing(0)
        self.bar = DialogTitleBar(self.close, tr("apply.title"), closable=False)
        surface.addWidget(self.bar)
        body = QWidget()
        body.setObjectName("DialogBody")
        root = QVBoxLayout(body)
        root.setContentsMargins(22, 12, 22, 18)
        root.setSpacing(10)
        root.addWidget(make_label(tr("apply.heading", from_version=options.from_version, to_version=APP_VERSION),
                                  "Heading"))
        self._step_icons: list[QLabel] = []
        for step in STEPS:
            row = QHBoxLayout()
            row.setSpacing(10)
            glyph = QLabel()
            icons.set_icon(glyph, "chevron_right", "faint", 16)
            row.addWidget(glyph)
            row.addWidget(QLabel(tr(f"apply.step.{step}")), 1)
            root.addLayout(row)
            self._step_icons.append(glyph)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setRange(0, 100)
        root.addWidget(self.progress)
        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        root.addWidget(self.message)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.close_button = make_button(tr("dlg.close"), variant="primary")
        self.close_button.setEnabled(False)
        self.close_button.clicked.connect(self.close)
        buttons.addWidget(self.close_button)
        root.addLayout(buttons)
        surface.addWidget(body)
        self.job = ApplyUpdateJob(options, self)
        self.job.progressChanged.connect(self._on_progress)
        self.job.completed.connect(self._on_completed)

    def start(self) -> None:
        self.adjustSize()
        center_on_screen(self)
        self.show()
        self.job.start()

    def _on_progress(self, percent: int, stage: str, detail: dict) -> None:
        self.progress.setValue(percent)
        current = _STAGE_TO_STEP.get(stage)
        if current is None:
            return
        for index, glyph in enumerate(self._step_icons):
            if index < current:
                icons.set_icon(glyph, "check_circle", "success", 16)
            elif index == current:
                icons.set_icon(glyph, "chevron_right", "accent", 16)

    def _on_completed(self, result: object) -> None:
        self.close_button.setEnabled(True)
        if not isinstance(result, dict):
            self.close()
            return
        stage = str(result.get("stage", ""))
        error = str(result.get("error", ""))
        if stage == "done":
            self.progress.setValue(100)
            self.message.setText(tr("apply.done"))
            QTimer.singleShot(1500, self.close)
            return
        for glyph in self._step_icons:
            if glyph.property("iconRole") == "accent":
                icons.set_icon(glyph, "error_circle", "danger", 16)
        key = {"rolled_back": "apply.rolled_back", "wait_timeout": "apply.timeout",
               "bad_arguments": "apply.bad_arguments"}.get(stage, "apply.failed")
        self.message.setText(tr(key, error=error, path=str(self.options.work_dir / "backup")))
