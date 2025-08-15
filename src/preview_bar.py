# preview_bar.py
from pathlib import Path
from PySide6.QtCore import Qt, Signal, QRect, QSize
from PySide6.QtGui import QPixmap, QPainter, QColor, QPalette
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QSizePolicy
)
from .constants import BG_MAIN

class LabelLineEdit(QWidget):
    """'라벨 박스 + 입력창'을 하나의 단위로 묶은 커스텀 위젯."""
    def __init__(self, label_text: str, label_bg_color: str, parent=None):
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        # 1. 텍스트 라벨 (박스 스타일)
        self.label = QLabel(label_text)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet(f"""
            background-color: {label_bg_color}; 
            color: white; 
            border-radius: 6px; 
            padding: 6px;
        """)

        # 2. 시간 입력창
        self.time_edit = QLineEdit()
        self.time_edit.setAlignment(Qt.AlignCenter)
        self.time_edit.setFixedWidth(120)
        self._apply_transparent_style(self.time_edit)
        
        layout.addWidget(self.label)
        layout.addWidget(self.time_edit)

    def _apply_transparent_style(self, line_edit: QLineEdit):
        transparent_style = "background-color: rgba(0, 0, 0, 170); color: white; border-radius: 6px; border: 1px solid rgba(255, 255, 255, 50); padding: 5px;"
        
        line_edit.setStyleSheet(transparent_style)
        
        original_focus_in = line_edit.focusInEvent
        def focus_in(e):
            line_edit.setStyleSheet(f"background-color: {BG_MAIN}; color: black; border-radius: 6px; border: 1px solid #2563eb; padding: 5px;")
            original_focus_in(e)
        
        original_focus_out = line_edit.focusOutEvent
        def focus_out(e):
            line_edit.setStyleSheet(transparent_style)
            original_focus_out(e)
            
        line_edit.focusInEvent = focus_in
        line_edit.focusOutEvent = focus_out

    def set_time_edit_style(self, color_hex: str):
        palette = self.time_edit.palette()
        palette.setColor(QPalette.Base, QColor(color_hex))
        self.time_edit.setPalette(palette)

    def setText(self, text: str):
        self.time_edit.setText(text)

    def text(self) -> str:
        return self.time_edit.text()

class PreviewView(QWidget):
    """
    16:9 비율을 유지하는 프리뷰 이미지와 하단 오버레이 UI를 포함하는 위젯.
    """
    def __init__(self, label_text: str, label_bg_color: str, parent=None):
        super().__init__(parent)
        self.setObjectName("PreviewView")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        self._pixmap = QPixmap()

        # '라벨 + 입력창' 통합 위젯을 자식으로 생성
        self.overlay_widget = LabelLineEdit(label_text, label_bg_color, self)

    def sizeHint(self) -> QSize:
        return QSize(640, 360)

    def heightForWidth(self, width: int) -> int:
        return int(width * 9 / 16)

    def set_pixmap(self, pixmap: QPixmap):
        self._pixmap = pixmap
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#222"))
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        if self._pixmap.isNull():
            return

        widget_rect = self.rect()
        pixmap_size = self._pixmap.size()
        scaled_size = pixmap_size.scaled(widget_rect.size(), Qt.KeepAspectRatio)
        
        final_rect = QRect(0, 0, scaled_size.width(), scaled_size.height())
        final_rect.moveCenter(widget_rect.center())
        
        painter.drawPixmap(final_rect, self._pixmap)

    def resizeEvent(self, event):
        """위젯 크기 변경 시 오버레이 위젯의 위치를 다시 계산합니다."""
        super().resizeEvent(event)
        
        # 통합된 오버레이 위젯('라벨+입력창')의 현재 크기를 가져옵니다.
        overlay_width = self.overlay_widget.sizeHint().width()
        overlay_height = self.overlay_widget.sizeHint().height()

        # 오버레이 위젯을 중앙 하단에 배치하기 위한 x, y 좌표를 계산합니다.
        x = (self.width() - overlay_width) / 2
        y = self.height() - overlay_height - 10 # 하단 여백 10px
        
        self.overlay_widget.move(int(x), int(y))


class PreviewBar(QWidget):
    """
    상단 프리뷰 영역 전체를 담당하는 메인 위젯.
    """
    startEdited  = Signal()
    endEdited    = Signal()

    def __init__(self, lang: str = "ko"):
        super().__init__()
        self.lang = lang
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        # --- 좌측 프리뷰 패널 (시작 프레임) ---
        start_label_text = "시작 프레임" if self.lang == "ko" else "Start Frame"
        self.left_preview = PreviewView(start_label_text, "#ca8a04", self)
        self.left_preview.overlay_widget.setText("00:00.000")

        # --- 우측 프리뷰 패널 (끝 프레임) ---
        end_label_text = "끝 프레임" if self.lang == "ko" else "End Frame"
        self.right_preview = PreviewView(end_label_text, "#65a30d", self)
        self.right_preview.overlay_widget.setText("00:06.000")

        root.addWidget(self.left_preview, 1)
        root.addWidget(self.right_preview, 1)

        # --- 시그널 연결 ---
        self.left_preview.overlay_widget.time_edit.editingFinished.connect(self.startEdited.emit)
        self.right_preview.overlay_widget.time_edit.editingFinished.connect(self.endEdited.emit)

    def sizeHint(self) -> QSize:
        return QSize(1280, 720)

    def heightForWidth(self, width: int) -> int:
        return int(width * 9 / 16)

    def set_images(self, left_path: str, right_path: str):
        if left_path:
            self.left_preview.set_pixmap(QPixmap(left_path))
        if right_path:
            self.right_preview.set_pixmap(QPixmap(right_path))

    def set_times(self, s: str, e: str):
        self.left_preview.overlay_widget.setText(s)
        self.right_preview.overlay_widget.setText(e)

    def get_times(self) -> tuple:
        return self.left_preview.overlay_widget.text(), self.right_preview.overlay_widget.text()

    def set_time_edit_style(self, color_hex: str):
        self.left_preview.overlay_widget.set_time_edit_style(color_hex)
        self.right_preview.overlay_widget.set_time_edit_style(color_hex)