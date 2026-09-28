# result_dialog.py
"""GIF를 만든 뒤 결과를 바로 재생해서 보여 주는 창입니다. (용량·해상도·프레임 수·재생 시간 표시)"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QMovie
from PySide6.QtWidgets import QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ..core.encoder import EncodeResult
from ..i18n import tr
from .frame import apply_dialog_frame
from .widgets.common import ElidedLabel, make_button, make_label

PREVIEW_MAX = QSize(480, 270)


def format_size(size: int) -> str:
    if size >= 1024 * 1024:
        return f"{size / 1024 / 1024:.2f} MB"
    return f"{size / 1024:.1f} KB"


def open_in_explorer(path: str) -> None:
    """탐색기에서 파일을 선택한 상태로 폴더를 엽니다. (Windows가 아니면 폴더만 엽니다)"""
    import os
    import subprocess
    if os.name == "nt":
        subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
    else:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).parent)))


class ResultDialog(QDialog):
    def __init__(self, parent: QWidget | None, result: EncodeResult):
        super().__init__(parent)
        self.setWindowTitle(tr("result.title"))
        self.setModal(True)
        self.setMinimumWidth(560)
        self.path = result.path
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 14, 20, 16)
        root.setSpacing(14)

        stage = QFrame()
        stage.setObjectName("Card")
        stage_layout = QVBoxLayout(stage)
        stage_layout.setContentsMargins(12, 12, 12, 12)
        self.movie_label = QLabel()
        self.movie_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.movie_label.setMinimumHeight(120)
        stage_layout.addWidget(self.movie_label)
        root.addWidget(stage)
        self.movie = QMovie(result.path)
        info = result.info
        if info is not None and info.width > 0 and info.height > 0:
            factor = max(1, min(PREVIEW_MAX.width() // info.width, PREVIEW_MAX.height() // info.height))
            self.movie.setScaledSize(QSize(info.width * factor, info.height * factor))
        self.movie_label.setMovie(self.movie)
        self.movie.start()

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(6)
        size = Path(result.path).stat().st_size if Path(result.path).exists() else 0
        rows = [(tr("result.file"), ElidedLabel(Path(result.path).name)),
                (tr("result.size"), QLabel(format_size(size)))]
        if info is not None:
            rows += [(tr("result.dimensions"), QLabel(f"{info.width} × {info.height}")),
                     (tr("result.frames"), QLabel(str(info.frames))),
                     (tr("result.duration"), QLabel(tr("unit.seconds", value=f"{info.duration_ms / 1000:.2f}")))]
        rows.append((tr("result.elapsed"), QLabel(tr("unit.seconds", value=f"{result.elapsed:.1f}"))))
        for index, (caption, value) in enumerate(rows):
            grid.addWidget(make_label(caption, "FieldLabel"), index // 2, (index % 2) * 2)
            grid.addWidget(value, index // 2, (index % 2) * 2 + 1)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)
        root.addLayout(grid)

        buttons = QHBoxLayout()
        folder = make_button(tr("result.open_folder"), "folder_open")
        folder.clicked.connect(lambda: open_in_explorer(self.path))
        open_file = make_button(tr("result.open_file"), "open_external")
        open_file.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(self.path)))
        close = make_button(tr("dlg.close"), variant="primary")
        close.clicked.connect(self.accept)
        close.setDefault(True)
        buttons.addWidget(folder)
        buttons.addWidget(open_file)
        buttons.addStretch(1)
        buttons.addWidget(close)
        root.addLayout(buttons)
        apply_dialog_frame(self, title=tr("result.title"))

    def done(self, arg__1: int) -> None:
        self.movie.stop()
        super().done(arg__1)
