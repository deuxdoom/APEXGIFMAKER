# preview_bar.py
from pathlib import Path
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit
)

class PreviewView(QWidget):
    """센터 정렬 + 비율 유지로 Pixmap을 그리는 16:9 프리뷰 뷰."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("PreviewView")
        self._pix = QPixmap()

    def set_image(self, path: str):
        pm = QPixmap(path)
        if not pm.isNull():
            self._pix = pm
            self.update()

    def sizeHint(self) -> QSize:
        # 16:9 영역 추천 사이즈
        w = max(640, self.parent().width() // 2 if self.parent() else 640)
        return QSize(w, int(w * 9 / 16))

    def minimumSizeHint(self) -> QSize:
        return QSize(320, int(320 * 9 / 16))

    def paintEvent(self, e):
        from PySide6.QtGui import QPainter
        p = QPainter(self)
        p.fillRect(self.rect(), self.palette().window())
        if self._pix.isNull():
            return
        # 16:9 안쪽으로 컨텐츠 배치(레터박스)
        area = self.rect()
        target_h = int(area.width() * 9 / 16)
        if target_h > area.height():
            # 높이가 더 작으면, 높이에 맞추고 좌우 레터박스
            w = int(area.height() * 16 / 9)
            x = area.x() + (area.width() - w) // 2
            y = area.y()
            target = area.adjusted(0, 0, 0, 0)
            target.setX(x); target.setY(y); target.setWidth(w); target.setHeight(area.height())
        else:
            # 너비에 맞추고 상하 레터박스
            h = target_h
            x = area.x()
            y = area.y() + (area.height() - h) // 2
            target = area.adjusted(0, 0, 0, 0)
            target.setX(x); target.setY(y); target.setWidth(area.width()); target.setHeight(h)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)
        p.drawPixmap(target, self._pix)

class PreviewBar(QWidget):
    """
    상단 프리뷰 바(좌/우 16:9) + 배지 + 시작/끝 시간 입력 + 구간 재생 버튼.
    Signals:
      - playRequested()
      - startEdited(), endEdited()  (editingFinished 타이밍)
    Methods:
      - set_images(left_path, right_path)
      - set_times(start_str, end_str)
      - get_times() -> (start_str, end_str)
      - set_badge(text); set_badge_color(fg, bg)
    """
    playRequested = Signal()
    startEdited  = Signal()
    endEdited    = Signal()

    def __init__(self, lang: str = "ko"):
        super().__init__()
        self.lang = lang

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        # ── 상단 16:9 프리뷰 2분할 ───────────────────────────────
        split = QHBoxLayout()
        split.setContentsMargins(0, 0, 0, 0)
        split.setSpacing(8)

        self.left = PreviewView(self)
        self.right = PreviewView(self)
        split.addWidget(self.left, 1)
        split.addWidget(self.right, 1)
        root.addLayout(split)

        # ── 배지 + 시작/끝 입력 + 재생 ──────────────────────────
        bar = QHBoxLayout()
        bar.setContentsMargins(0, 0, 0, 0)
        bar.setSpacing(8)

        self.lbl_badge = QLabel("권장 3~6초" if self.lang == "ko" else "Recommend 3–6s")
        self.lbl_badge.setObjectName("DurationBadge")

        self.ed_start = QLineEdit("00:00.000")
        self.ed_end   = QLineEdit("00:03.000")
        for ed in (self.ed_start, self.ed_end):
            ed.setFixedWidth(120)

        lbl_s = QLabel("시작:" if self.lang == "ko" else "Start:")
        lbl_e = QLabel("끝:" if self.lang == "ko" else "End:")

        self.btn_play = QPushButton("구간 재생" if self.lang == "ko" else "Play Range")
        self.btn_play.setObjectName("PlayButton")

        bar.addWidget(self.lbl_badge)
        bar.addStretch(1)
        bar.addWidget(lbl_s); bar.addWidget(self.ed_start)
        bar.addWidget(lbl_e); bar.addWidget(self.ed_end)
        bar.addStretch(1)
        bar.addWidget(self.btn_play)
        root.addLayout(bar)

        # 시그널
        self.ed_start.editingFinished.connect(self.startEdited.emit)
        self.ed_end.editingFinished.connect(self.endEdited.emit)
        self.btn_play.clicked.connect(self.playRequested.emit)

    # API
    def set_images(self, left_path: str, right_path: str):
        if left_path:  self.left.set_image(left_path)
        if right_path: self.right.set_image(right_path)

    def set_times(self, s: str, e: str):
        self.ed_start.setText(s)
        self.ed_end.setText(e)

    def get_times(self):
        return self.ed_start.text(), self.ed_end.text()

    def set_badge(self, text: str):
        self.lbl_badge.setText(text)

    def set_badge_color(self, fg: str, bg: str):
        # fg(글자색)만 바꾸면 일관성이 좋아서 배경은 라이트 테마 기본 유지
        self.lbl_badge.setStyleSheet(
            f"QLabel#DurationBadge{{ color:{fg}; border-color:#94a3b8; }}"
        )
