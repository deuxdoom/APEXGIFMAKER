# rangeslider.py
from PySide6.QtCore import QRect, Signal, Qt
from PySide6.QtGui import QPainter, QColor
from PySide6.QtWidgets import QWidget

class RangeSlider(QWidget):
    """양끝 핸들 슬라이더 (0..1), active 핸들 노출"""
    changed = Signal(float, float)  # lower, upper (0..1)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(36)
        self._lower = 0.0
        self._upper = 0.1
        self._active = None  # 'l'|'u'|None

    def lower(self): return self._lower
    def upper(self): return self._upper
    def active_handle(self): return self._active

    def setRange(self, lower: float, upper: float, emit_signal=True):
        lower = max(0.0, min(1.0, lower))
        upper = max(0.0, min(1.0, upper))
        if upper < lower:
            upper = lower
        self._lower, self._upper = lower, upper
        self.update()
        if emit_signal:
            self.changed.emit(self._lower, self._upper)

    def paintEvent(self, e):
        p = QPainter(self)
        w, h = self.width(), self.height()
        bar = QRect(10, h//2 - 4, w-20, 8)
        p.setPen(Qt.NoPen); p.setBrush(QColor("#e5e7eb")); p.drawRect(bar)
        lpx = bar.x() + int(bar.width()*self._lower)
        upx = bar.x() + int(bar.width()*self._upper)
        sel = QRect(lpx, bar.y(), upx - lpx, bar.height())
        p.setBrush(QColor(37, 99, 235)); p.drawRect(sel)
        handle_w, handle_h = 10, 24
        p.setBrush(QColor("#ffffff")); p.setPen(QColor("#94a3b8"))
        p.drawRoundedRect(QRect(lpx- handle_w//2, bar.center().y()-handle_h//2, handle_w, handle_h), 6, 6)
        p.drawRoundedRect(QRect(upx- handle_w//2, bar.center().y()-handle_h//2, handle_w, handle_h), 6, 6)

    def mousePressEvent(self, e):
        bar_w = self.width()-20
        x = e.position().x()
        lpx = 10 + int(bar_w*self._lower)
        upx = 10 + int(bar_w*self._upper)
        self._active = 'l' if abs(x-lpx) < abs(x-upx) else 'u'
        self.mouseMoveEvent(e)

    def mouseMoveEvent(self, e):
        if not self._active:
            return
        val = (e.position().x()-10)/max(1,(self.width()-20))
        val = max(0.0, min(1.0, val))
        if self._active == 'l':
            self._lower = min(val, self._upper)
        else:
            self._upper = max(val, self._lower)
        self.update()
        self.changed.emit(self._lower, self._upper)

    def mouseReleaseEvent(self, e):
        self._active = None
