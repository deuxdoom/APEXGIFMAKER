# timeline_panel.py
from pathlib import Path
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPixmap                  # ✅ 누락됐던 import
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QLabel, QSizePolicy
)
from rangeslider import RangeSlider

THUMB_H = 72          # 썸네일 고정 높이(잘림 방지)
THUMB_PAD_V = 6       # 위아래 여백
CELL_W_MIN = 110      # 화면 폭 대비 가시 셀 계산용

class TimelinePanel(QWidget):
    """
    상단 RangeSlider(양쪽 핸들) + 하단 썸네일 스트립(스크롤).
    - .range : RangeSlider 인스턴스
    - visible_cells() -> int : 화면에 들어갈 썸네일 수 추정
    - add_thumb_files(list[Path]) : 썸네일 채우기
    - clear_thumbs()
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("TimelinePanel")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        # Range slider
        self.range = RangeSlider(self)
        root.addWidget(self.range)

        # Scroll thumbnails
        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setFrameShape(QScrollArea.NoFrame)

        self.inner = QWidget()
        self.inner_lay = QHBoxLayout(self.inner)
        self.inner_lay.setContentsMargins(8, THUMB_PAD_V, 8, THUMB_PAD_V)
        self.inner_lay.setSpacing(8)
        self.inner.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        self.scroll.setWidget(self.inner)
        # 썸네일 높이가 항상 전부 보이도록 스크롤 영역 높이 고정
        self.scroll.setFixedHeight(THUMB_H + THUMB_PAD_V*2 + 24)  # +24는 수평 스크롤바 높이
        root.addWidget(self.scroll)

    # 화면 폭 기준 가시 셀 수 추정(슬라이더 폭과 맞추기)
    def visible_cells(self) -> int:
        w = max(1, self.width() - 16)  # 좌우 패딩 고려
        return max(8, w // CELL_W_MIN)

    def clear_thumbs(self):
        while self.inner_lay.count():
            item = self.inner_lay.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)

    def add_thumb_files(self, files: list[Path]):
        self.clear_thumbs()
        if not files:
            return
        for fp in files:
            lb = QLabel()
            lb.setAlignment(Qt.AlignCenter)
            lb.setStyleSheet("background:#000;border-radius:6px;")
            pm = QPixmap(str(fp))
            if not pm.isNull():
                # 높이에 맞춰 비율 유지 스케일 → 하단 잘림 방지
                pm = pm.scaledToHeight(THUMB_H, Qt.SmoothTransformation)
                lb.setPixmap(pm)
            lb.setFixedHeight(THUMB_H)
            lb.setMinimumWidth(CELL_W_MIN - 10)
            self.inner_lay.addWidget(lb)
        self.inner_lay.addStretch(1)

    def sizeHint(self) -> QSize:
        return QSize(800, THUMB_H + THUMB_PAD_V*2 + 48)
