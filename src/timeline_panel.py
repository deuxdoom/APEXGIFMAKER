# timeline_panel.py
from pathlib import Path
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QLabel, QSizePolicy
)
from .rangeslider import RangeSlider

# 썸네일 UI 관련 상수
THUMB_H = 72          # 썸네일 이미지의 고정 높이
THUMB_PAD_V = 6       # 썸네일 스트립의 상하 여백
CELL_W_MIN = 110      # 썸네일 셀 하나의 최소 너비

class TimelinePanel(QWidget):
    """
    상단의 구간 선택 슬라이더(RangeSlider)와 하단의 비디오 썸네일 스트립을
    포함하는 복합 위젯입니다.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("TimelinePanel")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        # 1. 상단 구간 선택 슬라이더
        self.range = RangeSlider(self)
        root.addWidget(self.range)

        # 2. 하단 썸네일 스크롤 영역
        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setFrameShape(QScrollArea.NoFrame)

        # 스크롤 영역 내부에 실제 썸네일들이 담길 위젯
        self.inner = QWidget()
        self.inner_lay = QHBoxLayout(self.inner)
        self.inner_lay.setContentsMargins(8, THUMB_PAD_V, 8, THUMB_PAD_V)
        self.inner_lay.setSpacing(8)
        self.inner.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        self.scroll.setWidget(self.inner)
        # 썸네일이 잘리지 않도록 스크롤 영역의 높이를 상수로 고정
        self.scroll.setFixedHeight(THUMB_H + THUMB_PAD_V*2 + 24)
        root.addWidget(self.scroll)

    def visible_cells(self) -> int:
        """현재 위젯 너비를 기준으로 화면에 보여질 썸네일 개수를 추정합니다."""
        w = max(1, self.width() - 16)
        return max(8, w // CELL_W_MIN)

    def clear_thumbs(self):
        """현재 표시된 모든 썸네일 이미지를 제거합니다."""
        while self.inner_lay.count():
            item = self.inner_lay.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)

    def add_thumb_files(self, files: list[Path]):
        """주어진 이미지 파일 목록으로 썸네일 스트립을 채웁니다."""
        self.clear_thumbs()
        if not files:
            return
            
        for fp in files:
            lb = QLabel()
            lb.setAlignment(Qt.AlignCenter)
            lb.setStyleSheet("background:#000; border-radius:6px;")
            
            pm = QPixmap(str(fp))
            if not pm.isNull():
                # 이미지를 고정 높이에 맞춰 부드럽게 스케일링
                pm = pm.scaledToHeight(THUMB_H, Qt.SmoothTransformation)
                lb.setPixmap(pm)
                
            lb.setFixedHeight(THUMB_H)
            lb.setMinimumWidth(CELL_W_MIN - 10)
            self.inner_lay.addWidget(lb)
            
        self.inner_lay.addStretch(1)

    def sizeHint(self) -> QSize:
        return QSize(800, THUMB_H + THUMB_PAD_V*2 + 48)