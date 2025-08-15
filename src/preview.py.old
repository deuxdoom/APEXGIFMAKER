# preview.py
from PySide6.QtCore import Qt, QRect, QSize
from PySide6.QtGui import QPixmap, QPainter, QColor, QPalette
from PySide6.QtWidgets import QWidget, QSizePolicy

class PreviewView(QWidget):
    """
    프리뷰 위젯 (중앙 정렬 + 비율 제어)
    - fit_mode:
        - "cover"   : 여백 없이 꽉 채우기(중앙 크롭)  ← 기본
        - "contain" : 전체 보이기(여백 허용)
        - "stretch" : 강제 늘리기(왜곡)
    - 항상 contentsRect() 기준으로 직접 페인팅 → 패딩/프레임/HiDPI 문제 없음
    """
    def __init__(self, fit_mode: str = "cover"):
        super().__init__()
        self._px: QPixmap | None = None
        self._fit_mode = fit_mode  # cover | contain | stretch

        self.setObjectName("PreviewView")
        self.setMinimumHeight(420)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)

        pal = self.palette()
        pal.setColor(QPalette.Window, QColor("#f1f5f9"))  # 밝은 배경
        self.setAutoFillBackground(True)
        self.setPalette(pal)

    # ----- 외부 API ----------------------------------------------------------
    def set_fit_mode(self, mode: str):
        if mode in ("cover", "contain", "stretch"):
            self._fit_mode = mode
            self.update()

    def fit_mode(self) -> str:
        return self._fit_mode

    def set_image_path(self, path: str):
        px = QPixmap(path)
        self._px = px if (px and not px.isNull()) else None
        self.update()

    def set_pixmap(self, px: QPixmap):
        self._px = px if (px and not px.isNull()) else None
        self.update()

    # ----- QWidget 구현 ------------------------------------------------------
    def sizeHint(self) -> QSize:
        return QSize(640, 420)

    def paintEvent(self, e):
        painter = QPainter(self)
        rect = self.contentsRect()
        painter.fillRect(rect, self.palette().window())

        if not self._px or self._px.isNull():
            return

        src_w = self._px.width()
        src_h = self._px.height()
        if src_w <= 0 or src_h <= 0:
            return

        if self._fit_mode == "stretch":
            # 왜곡 허용: 대상 영역을 꽉 채워 그림
            dst = QRect(rect.x(), rect.y(), rect.width(), rect.height())
            painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
            painter.drawPixmap(dst, self._px)
            return

        # contain/cover : 비율 유지
        ratio_w = rect.width()  / src_w
        ratio_h = rect.height() / src_h

        if self._fit_mode == "contain":
            scale = min(ratio_w, ratio_h)  # 여백 허용, 전체 보이기
        else:  # cover
            scale = max(ratio_w, ratio_h)  # 여백 없이 꽉 채우기(크롭)

        # 대상 크기(정수 보정)
        dst_w = max(1, int(src_w * scale))
        dst_h = max(1, int(src_h * scale))

        # 중앙 정렬 위치
        dst_x = rect.x() + (rect.width()  - dst_w) // 2
        dst_y = rect.y() + (rect.height() - dst_h) // 2
        dst = QRect(dst_x, dst_y, dst_w, dst_h)

        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        if self._fit_mode == "contain":
            # 영역 안에 완전히 들어오므로 그대로 그림
            painter.drawPixmap(dst, self._px)
        else:
            # cover: 박스를 넘는 부분은 잘라낸다(클리핑)
            painter.save()
            painter.setClipRect(rect)
            painter.drawPixmap(dst, self._px)
            painter.restore()
