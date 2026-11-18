# preview.py
"""시작·끝 프레임 프리뷰와, 동영상이 없을 때의 끌어다 놓기 안내 화면입니다.

- 프레임은 원본 비율을 유지해서 그립니다. (v2.x는 1280×720으로 늘려 세로 영상이 찌그러졌습니다.)
- '꽉 채우기' 모드에서는 GIF에 담길 영역을 점선으로 표시하고 나머지를 어둡게 합니다.
"""
from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath, QPaintEvent, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QStackedWidget, QVBoxLayout, QWidget

from ...i18n import tr
from .. import theme
from ..frame import app_icon_pixmap
from .common import make_button, make_label, set_state

RADIUS = 10


class FramePane(QWidget):
    def __init__(self, caption: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(220, 124)
        self._caption = caption
        self._time = ""
        self._image = QImage()
        self._guide: float | None = None
        self._loading = False
        self._error = False
        self._angle = 0
        self._spinner = QTimer(self)
        self._spinner.setInterval(60)
        self._spinner.timeout.connect(self._spin)
        self._delay = QTimer(self)
        self._delay.setSingleShot(True)
        self._delay.setInterval(250)
        self._delay.timeout.connect(self._spinner.start)
        theme.manager().changed.connect(self.update)

    def sizeHint(self) -> QSize:
        return QSize(560, 315)

    def set_time(self, text: str) -> None:
        self._time = text
        self.update()

    def set_image(self, image: QImage) -> None:
        self._image = image
        self._error = False
        self.set_loading(False)

    def set_error(self) -> None:
        self._error = True
        self.set_loading(False)

    def set_loading(self, loading: bool) -> None:
        self._loading = loading
        if loading:
            if not self._spinner.isActive() and not self._delay.isActive():
                self._delay.start()
        else:
            self._delay.stop()
            self._spinner.stop()
        self.update()

    def set_guide(self, aspect: float | None) -> None:
        self._guide = aspect
        self.update()

    def clear(self) -> None:
        self._image = QImage()
        self._time = ""
        self._error = False
        self.set_loading(False)

    def _spin(self) -> None:
        self._angle = (self._angle + 30) % 360
        self.update()

    def image_rect(self) -> QRectF:
        if self._image.isNull():
            return QRectF()
        area = QRectF(self.rect())
        scale = min(area.width() / self._image.width(), area.height() / self._image.height())
        width, height = self._image.width() * scale, self._image.height() * scale
        return QRectF(area.center().x() - width / 2, area.center().y() - height / 2, width, height)

    def paintEvent(self, e: QPaintEvent) -> None:
        pal = theme.current()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        bounds = QRectF(self.rect())
        clip = QPainterPath()
        clip.addRoundedRect(bounds, RADIUS, RADIUS)
        painter.setClipPath(clip)
        painter.fillRect(bounds, QColor(pal.media_bg))
        target = self.image_rect()
        if not target.isNull():
            painter.drawImage(target, self._image)
            if self._guide:
                self._paint_guide(painter, target, self._guide)
        if self._error:
            painter.setPen(QColor("#9aa1ad"))
            painter.drawText(bounds, Qt.AlignmentFlag.AlignCenter, tr("preview.error"))
        self._paint_caption(painter, pal)
        if self._loading and self._spinner.isActive():
            self._paint_spinner(painter, bounds, pal)

    def _paint_guide(self, painter: QPainter, image: QRectF, aspect: float) -> None:
        if image.width() / image.height() > aspect:
            width = image.height() * aspect
            crop = QRectF(image.center().x() - width / 2, image.top(), width, image.height())
        else:
            height = image.width() / aspect
            crop = QRectF(image.left(), image.center().y() - height / 2, image.width(), height)
        shade = QColor(0, 0, 0, 120)
        outside = QPainterPath()
        outside.addRect(image)
        inside = QPainterPath()
        inside.addRect(crop)
        painter.fillPath(outside.subtracted(inside), shade)
        pen = QPen(QColor(255, 255, 255, 200), 1.2, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(crop.adjusted(0.5, 0.5, -0.5, -0.5))

    def _paint_caption(self, painter: QPainter, pal: theme.Palette) -> None:
        font = QFont(self.font())
        font.setPointSizeF(9.0)
        font.setBold(True)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        caption_w = metrics.horizontalAdvance(self._caption)
        time_w = metrics.horizontalAdvance(self._time) if self._time else 0
        width = 20 + caption_w + (10 + time_w if self._time else 0)
        pill = QRectF(10, 10, width, 24)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 150))
        painter.drawRoundedRect(pill, 12, 12)
        painter.setPen(QColor(pal.select))
        painter.drawText(QRectF(pill.left() + 10, pill.top(), caption_w, pill.height()),
                         Qt.AlignmentFlag.AlignVCenter, self._caption)
        if self._time:
            painter.setPen(QColor("#ffffff"))
            painter.drawText(QRectF(pill.left() + 20 + caption_w, pill.top(), time_w, pill.height()),
                             Qt.AlignmentFlag.AlignVCenter, self._time)

    def _paint_spinner(self, painter: QPainter, bounds: QRectF, pal: theme.Palette) -> None:
        box = QRectF(bounds.right() - 30, bounds.top() + 12, 16, 16)
        painter.setPen(QPen(QColor(255, 255, 255, 60), 2.2))
        painter.drawEllipse(box)
        pen = QPen(QColor(pal.select), 2.2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawArc(box, -self._angle * 16, 100 * 16)


class DropZone(QFrame):
    openRequested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("DropZone")
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.addStretch(1)
        self.icon = QLabel()
        self.icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon.setPixmap(app_icon_pixmap(104))
        layout.addWidget(self.icon)
        title = make_label(tr("preview.empty.title"), "DropTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        body = make_label(tr("preview.empty.body"), "Muted")
        body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(body)
        row = QHBoxLayout()
        row.addStretch(1)
        self.button = make_button(tr("top.open"), "folder_open", variant="primary", size="large")
        self.button.clicked.connect(self.openRequested.emit)
        row.addWidget(self.button)
        row.addStretch(1)
        layout.addSpacing(6)
        layout.addLayout(row)
        layout.addStretch(1)

    def set_active(self, active: bool) -> None:
        set_state(self, "active", active)


class PreviewArea(QStackedWidget):
    """동영상이 없으면 안내 화면, 있으면 시작·끝 프레임 두 칸을 보여 줍니다."""

    openRequested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.drop_zone = DropZone()
        self.drop_zone.openRequested.connect(self.openRequested.emit)
        self.addWidget(self.drop_zone)
        frames = QWidget()
        row = QHBoxLayout(frames)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        self.start_pane = FramePane(tr("preview.start"))
        self.end_pane = FramePane(tr("preview.end"))
        row.addWidget(self.start_pane, 1)
        row.addWidget(self.end_pane, 1)
        self.addWidget(frames)

    def pane(self, slot: str) -> FramePane:
        return self.start_pane if slot == "start" else self.end_pane

    def show_frames(self, visible: bool) -> None:
        self.setCurrentIndex(1 if visible else 0)
        if not visible:
            self.start_pane.clear()
            self.end_pane.clear()

    def set_guide(self, aspect: float | None) -> None:
        self.start_pane.set_guide(aspect)
        self.end_pane.set_guide(aspect)
        tip = tr("preview.crop_hint") if aspect else ""
        self.start_pane.setToolTip(tip)
        self.end_pane.setToolTip(tip)

    def set_drop_active(self, active: bool) -> None:
        self.drop_zone.set_active(active)
