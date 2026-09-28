# timeline.py
"""구간 선택 타임라인. 필름스트립 위에 선택 구간 프레임과 양쪽 핸들을 그립니다.

v2.x 슬라이더의 문제를 이렇게 고쳤습니다.
- 핸들을 끌면 그 끝점만 움직입니다(최소 1초·최대 30초에서 멈춤). 예전에는 구간 전체가 따라 움직였습니다.
- 가운데를 끌면 길이를 유지한 채 구간이 이동하고, 빈 곳을 누르면 구간이 그 자리로 옮겨 갑니다.
- 휠로 확대/축소, Shift+휠로 좌우 이동, 더블클릭으로 선택 구간 확대/전체 보기를 합니다.
  긴 영상에서도 0.1초 단위로 고를 수 있습니다. 확대 중에는 아래 개요 바가 전체 위치를 보여 줍니다.
- 썸네일은 보이는 칸만 추출하며, 칸이 실제 시각에 정렬되어 슬라이더 위치와 어긋나지 않습니다.
"""
from __future__ import annotations

import math

from PySide6.QtCore import QEvent, QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (QColor, QFocusEvent, QFont, QImage, QKeyEvent, QMouseEvent, QPainter, QPainterPath,
                           QPaintEvent, QPen, QPixmap, QWheelEvent)
from PySide6.QtWidgets import QSizePolicy, QWidget

from ...core.trim import Selection, TrimRules
from ...i18n import tr
from .. import theme
from .timeline_math import ThumbCache, format_tick, minor_step, ruler_step, tile_span

RULER_H = 22
STRIP_H = 58
OVERVIEW_GAP = 7
OVERVIEW_H = 6
HANDLE_W = 12
PAD_X = HANDLE_W + 2
RADIUS = 7
INITIAL_VIEW_MAX = 120.0     # 긴 영상은 처음부터 2분 폭으로 보여 줍니다(개요 바로 전체 위치 표시).
MIN_VIEW = 2.0
ZOOM_STEP = 1.25


class TimelineWidget(QWidget):
    selectionChanged = Signal(float, float)
    interactionFinished = Signal()
    thumbnailsNeeded = Signal(list)
    viewChanged = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(RULER_H + STRIP_H + OVERVIEW_GAP + OVERVIEW_H + 3)
        self._rules: TrimRules | None = None
        self._sel = Selection(0.0, 0.0)
        self._view0 = 0.0
        self._view1 = 0.0
        self._aspect = 16 / 9
        self._frame_step = 1 / 30
        self._thumbs = ThumbCache()
        self._drag: str | None = None
        self._grab = 0.0
        self._hover: QPointF | None = None
        self._hover_hit: str | None = None
        self._last_pos = QPointF()
        self._requested: frozenset[int] = frozenset()
        self._wanted: list[float] = []
        self._thumb_timer = QTimer(self)
        self._thumb_timer.setSingleShot(True)
        self._thumb_timer.setInterval(90)
        self._thumb_timer.timeout.connect(lambda: self.thumbnailsNeeded.emit(list(self._wanted)))
        self._autopan = QTimer(self)
        self._autopan.setInterval(16)
        self._autopan.timeout.connect(self._autopan_tick)
        theme.manager().changed.connect(self.update)

    # ------------------------------------------------------------------ 공개 API
    def sizeHint(self) -> QSize:
        return QSize(800, self.height())

    def has_video(self) -> bool:
        return self._rules is not None

    def rules(self) -> TrimRules | None:
        return self._rules

    def selection(self) -> Selection:
        return self._sel

    def thumb_height(self) -> int:
        return int(STRIP_H * max(1.0, self.devicePixelRatioF()) + 0.5)

    def set_video(self, duration: float, aspect: float, frame_step: float,
                  selection: Selection | None = None) -> None:
        self._rules = TrimRules(duration)
        self._aspect = min(max(aspect, 0.5), 2.5)
        self._frame_step = frame_step
        self._thumbs.clear()
        self._requested = frozenset()
        self._sel = self._rules.normalize(selection) if selection else self._rules.initial()
        span = min(duration, max(INITIAL_VIEW_MAX, self._sel.length * 4))
        self._view0, self._view1 = 0.0, span
        self.update()
        self.viewChanged.emit()
        self.selectionChanged.emit(self._sel.start, self._sel.end)

    def clear(self) -> None:
        self._rules = None
        self._thumbs.clear()
        self._drag = None
        self.update()
        self.viewChanged.emit()

    def set_selection(self, sel: Selection, *, emit: bool = True, reveal: bool = True) -> None:
        if self._rules is None:
            return
        sel = self._rules.normalize(sel)
        changed = sel != self._sel
        self._sel = sel
        if reveal:
            self._reveal(sel)
        self.update()
        if changed and emit:
            self.selectionChanged.emit(sel.start, sel.end)

    def add_thumbnail(self, t: float, image: QImage) -> None:
        self._thumbs.put(round(t * 1000), QPixmap.fromImage(image))
        self.update()

    # ------------------------------------------------------------------ 확대/축소
    def _span(self) -> float:
        return max(1e-6, self._view1 - self._view0)

    def _min_span(self) -> float:
        return min(self._rules.duration, MIN_VIEW) if self._rules else MIN_VIEW

    def is_zoomed(self) -> bool:
        return self._rules is not None and self._span() < self._rules.duration - 1e-6

    def can_zoom_in(self) -> bool:
        return self._rules is not None and self._span() > self._min_span() + 1e-6

    def _set_view(self, start: float, span: float) -> None:
        if self._rules is None:
            return
        duration = self._rules.duration
        span = min(max(span, self._min_span()), duration)
        start = min(max(start, 0.0), duration - span)
        if (start, start + span) != (self._view0, self._view1):
            self._view0, self._view1 = start, start + span
            self.update()
            self.viewChanged.emit()

    def zoom(self, factor: float, anchor: float | None = None) -> None:
        span = self._span()
        anchor = (self._view0 + self._view1) / 2 if anchor is None else anchor
        new_span = span / factor
        self._set_view(anchor - (anchor - self._view0) * new_span / span, new_span)

    def zoom_in(self) -> None:
        self.zoom(ZOOM_STEP ** 2, (self._sel.start + self._sel.end) / 2)

    def zoom_out(self) -> None:
        self.zoom(1 / ZOOM_STEP ** 2, (self._sel.start + self._sel.end) / 2)

    def zoom_fit(self) -> None:
        if self._rules is not None:
            self._set_view(0.0, self._rules.duration)

    def zoom_to_selection(self) -> None:
        span = self._sel.length / 0.6
        self._set_view((self._sel.start + self._sel.end) / 2 - span / 2, span)

    def _reveal(self, sel: Selection) -> None:
        span = self._span()
        if sel.start >= self._view0 and sel.end <= self._view1:
            return
        if sel.length > span * 0.9:
            self._set_view((sel.start + sel.end) / 2 - sel.length / 1.4, sel.length / 0.7)
        elif sel.start < self._view0:
            self._set_view(sel.start - span * 0.1, span)
        else:
            self._set_view(sel.end - span * 0.9, span)

    # ------------------------------------------------------------------ 좌표 변환
    def _track(self) -> QRectF:
        return QRectF(PAD_X, RULER_H, max(10.0, self.width() - 2 * PAD_X), STRIP_H)

    def _overview(self) -> QRectF:
        return QRectF(PAD_X, RULER_H + STRIP_H + OVERVIEW_GAP, max(10.0, self.width() - 2 * PAD_X), OVERVIEW_H)

    def _x(self, t: float) -> float:
        track = self._track()
        return track.left() + (t - self._view0) / self._span() * track.width()

    def _t(self, x: float) -> float:
        track = self._track()
        return self._view0 + (x - track.left()) / track.width() * self._span()

    # ------------------------------------------------------------------ 그리기
    def paintEvent(self, e: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pal = theme.current()
        track = self._track()
        if self._rules is None:
            painter.setPen(QPen(QColor(pal.border_strong), 1, Qt.PenStyle.DashLine))
            painter.setBrush(QColor(pal.surface_alt))
            painter.drawRoundedRect(track, RADIUS, RADIUS)
            painter.setPen(QColor(pal.text_faint))
            painter.drawText(track, Qt.AlignmentFlag.AlignCenter, tr("timeline.placeholder"))
            return
        self._paint_ruler(painter, track, pal)
        clip = QPainterPath()
        clip.addRoundedRect(track, RADIUS, RADIUS)
        painter.save()
        painter.setClipPath(clip)
        painter.fillRect(track, QColor(pal.media_bg))
        self._paint_tiles(painter, track)
        x0, x1 = self._x(self._sel.start), self._x(self._sel.end)
        dim = QColor(pal.media_bg)
        dim.setAlpha(170)
        painter.fillRect(QRectF(track.left(), track.top(), max(0.0, x0 - track.left()), track.height()), dim)
        painter.fillRect(QRectF(x1, track.top(), max(0.0, track.right() - x1), track.height()), dim)
        self._paint_hover(painter, track)
        painter.restore()
        self._paint_selection(painter, track, x0, x1, pal)
        self._paint_overview(painter, pal)
        if self.hasFocus():
            painter.setPen(QPen(QColor(pal.accent), 1.2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(track.adjusted(-1.5, -1.5, 1.5, 1.5), RADIUS + 1, RADIUS + 1)

    def _paint_ruler(self, painter: QPainter, track: QRectF, pal: theme.Palette) -> None:
        pps = track.width() / self._span()
        step = ruler_step(pps)
        minor = minor_step(step, pps)
        long_video = self._rules is not None and self._rules.duration >= 3600
        font = QFont(self.font())
        font.setPointSizeF(8.0)
        painter.setFont(font)
        base = RULER_H - 2
        if minor:
            painter.setPen(QPen(QColor(pal.border_strong), 1))
            t = math.floor(self._view0 / minor) * minor
            while t <= self._view1:
                x = self._x(t)
                if track.left() - 1 <= x <= track.right() + 1:
                    painter.drawLine(QPointF(x, base - 3), QPointF(x, base))
                t += minor
        t = math.floor(self._view0 / step) * step
        while t <= self._view1 + 1e-9:
            x = self._x(t)
            if track.left() - 1 <= x <= track.right() + 1:
                painter.setPen(QPen(QColor(pal.text_faint), 1))
                painter.drawLine(QPointF(x, base - 7), QPointF(x, base))
                label = format_tick(t, step, long_video)
                if x + 3 + painter.fontMetrics().horizontalAdvance(label) <= self.width() - 2:
                    painter.setPen(QColor(pal.text_muted))
                    painter.drawText(QRectF(x + 3, 0, 80, base - 3),
                                     Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom, label)
            t += step

    def _paint_tiles(self, painter: QPainter, track: QRectF) -> None:
        assert self._rules is not None
        duration = self._rules.duration
        pps = track.width() / self._span()
        span = tile_span(STRIP_H * self._aspect / pps, self._frame_step)
        first = math.floor(self._view0 / span)
        wanted: list[float] = []
        separator = QColor(0, 0, 0, 90)
        index = first
        while True:
            t0 = index * span
            if t0 >= min(duration, self._view1):
                break
            index += 1
            t1 = min(duration, t0 + span)
            rect = QRectF(self._x(t0), track.top(), self._x(t1) - self._x(t0), track.height())
            sample = min(t0 + span / 2, max(0.0, duration - self._frame_step))
            key = round(sample * 1000)
            pixmap = self._thumbs.get(key)
            if pixmap is None:
                wanted.append(sample)
                pixmap = self._thumbs.nearest(key, span * 2000)
            if pixmap is not None:
                self._draw_cover(painter, pixmap, rect)
            painter.fillRect(QRectF(rect.left(), rect.top(), 1, rect.height()), separator)
        self._want(wanted)

    @staticmethod
    def _draw_cover(painter: QPainter, pixmap: QPixmap, rect: QRectF) -> None:
        sw, sh = pixmap.width(), pixmap.height()
        if sw <= 0 or sh <= 0 or rect.width() <= 0:
            return
        target = rect.width() / rect.height()
        if sw / sh > target:
            crop = sh * target
            source = QRectF((sw - crop) / 2, 0, crop, sh)
        else:
            crop = sw / target
            source = QRectF(0, (sh - crop) / 2, sw, crop)
        painter.drawPixmap(rect, pixmap, source)

    def _want(self, times: list[float]) -> None:
        keys = frozenset(round(t * 1000) for t in times)
        if not keys or keys == self._requested:
            return
        self._requested = keys
        self._wanted = times
        self._thumb_timer.start()

    def _paint_hover(self, painter: QPainter, track: QRectF) -> None:
        if self._hover is None or self._drag is not None or self._hover_hit not in ("track", "body"):
            return
        x = self._hover.x()
        if not track.left() <= x <= track.right():
            return
        painter.setPen(QPen(QColor(255, 255, 255, 170), 1))
        painter.drawLine(QPointF(x, track.top()), QPointF(x, track.bottom()))

    def _paint_selection(self, painter: QPainter, track: QRectF, x0: float, x1: float, pal: theme.Palette) -> None:
        color = QColor(pal.select)
        top, bottom, height = track.top(), track.bottom(), track.height()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawRect(QRectF(x0, top, max(0.0, x1 - x0), 3))
        painter.drawRect(QRectF(x0, bottom - 3, max(0.0, x1 - x0), 3))
        for which, left in (("start", x0 - HANDLE_W), ("end", x1)):
            active = self._drag == which or (self._drag is None and self._hover_hit == which)
            painter.setBrush(color.lighter(112) if active else color)
            handle = QRectF(left, top, HANDLE_W, height)
            painter.drawRoundedRect(handle, 5, 5)
            inner = QRectF(left + (HANDLE_W - 5 if which == "start" else 0), top, 5, height)
            painter.drawRect(inner)
            painter.setPen(QPen(QColor(pal.select_text), 1.4))
            mid = left + HANDLE_W / 2
            for dx in (-1.6, 1.6):
                painter.drawLine(QPointF(mid + dx, top + height / 2 - 7), QPointF(mid + dx, top + height / 2 + 7))
            painter.setPen(Qt.PenStyle.NoPen)
        self._paint_label(painter, track, (x0 + x1) / 2, tr("unit.seconds", value=f"{self._sel.length:.2f}"),
                          color, QColor(pal.select_text))
        if self._hover is not None and self._drag is None and self._hover_hit in ("track", "body"):
            text = format_tick(self._t(self._hover.x()), 0.1, False)
            self._paint_label(painter, track, self._hover.x(), text, QColor(pal.surface), QColor(pal.text),
                              QColor(pal.border_strong))

    def _paint_label(self, painter: QPainter, track: QRectF, center: float, text: str,
                     fill: QColor, ink: QColor, border: QColor | None = None) -> None:
        font = QFont(self.font())
        font.setPointSizeF(8.0)
        font.setBold(True)
        painter.setFont(font)
        width = painter.fontMetrics().horizontalAdvance(text) + 14
        left = min(max(center - width / 2, track.left() - HANDLE_W), track.right() + HANDLE_W - width)
        rect = QRectF(left, 1, width, RULER_H - 5)
        painter.setPen(QPen(border, 1) if border is not None else Qt.PenStyle.NoPen)
        painter.setBrush(fill)
        painter.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)
        painter.setPen(ink)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)

    def _paint_overview(self, painter: QPainter, pal: theme.Palette) -> None:
        if self._rules is None:
            return
        rect = self._overview()
        duration = self._rules.duration
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(pal.surface_hover))
        painter.drawRoundedRect(rect, OVERVIEW_H / 2, OVERVIEW_H / 2)
        if self.is_zoomed():
            view = QRectF(rect.left() + self._view0 / duration * rect.width(), rect.top(),
                          max(6.0, self._span() / duration * rect.width()), rect.height())
            painter.setBrush(QColor(pal.border_strong))
            painter.drawRoundedRect(view, OVERVIEW_H / 2, OVERVIEW_H / 2)
        mark = QRectF(rect.left() + self._sel.start / duration * rect.width(), rect.top() - 1,
                      max(3.0, self._sel.length / duration * rect.width()), rect.height() + 2)
        painter.setBrush(QColor(pal.select))
        painter.drawRoundedRect(mark, 2, 2)

    # ------------------------------------------------------------------ 마우스
    def _hit(self, pos: QPointF) -> str | None:
        if self._rules is None:
            return None
        track = self._track()
        if self.is_zoomed() and self._overview().adjusted(0, -4, 0, 4).contains(pos):
            return "overview"
        if pos.y() > track.bottom() + 3:
            return None
        x0, x1, x = self._x(self._sel.start), self._x(self._sel.end), pos.x()
        in_start = x0 - HANDLE_W - 3 <= x <= x0 + 3
        in_end = x1 - 3 <= x <= x1 + HANDLE_W + 3
        if in_start and in_end:
            return "start" if abs(x - (x0 - HANDLE_W / 2)) <= abs(x - (x1 + HANDLE_W / 2)) else "end"
        if in_start:
            return "start"
        if in_end:
            return "end"
        if x0 < x < x1:
            return "body"
        if track.left() - HANDLE_W <= x <= track.right() + HANDLE_W:
            return "track"
        return None

    def _update_cursor(self, hit: str | None) -> None:
        shapes = {"start": Qt.CursorShape.SizeHorCursor, "end": Qt.CursorShape.SizeHorCursor,
                  "body": Qt.CursorShape.OpenHandCursor, "track": Qt.CursorShape.PointingHandCursor,
                  "overview": Qt.CursorShape.PointingHandCursor}
        if self._drag == "move":
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        elif hit in shapes:
            self.setCursor(shapes[hit])
        else:
            self.unsetCursor()

    def mousePressEvent(self, e: QMouseEvent) -> None:
        if e.button() != Qt.MouseButton.LeftButton or self._rules is None:
            return super().mousePressEvent(e)
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        pos = e.position()
        hit = self._hit(pos)
        if hit == "start":
            self._grab = pos.x() - self._x(self._sel.start)
        elif hit == "end":
            self._grab = pos.x() - self._x(self._sel.end)
        elif hit == "body":
            self._grab = self._t(pos.x()) - self._sel.start
            hit = "move"
        elif hit == "track":
            self.set_selection(self._rules.move(self._sel, self._t(pos.x()) - self._sel.length / 2), reveal=False)
            self._grab = self._sel.length / 2
            hit = "move"
        self._drag = hit
        self._last_pos = pos
        if hit == "overview":
            self._pan_to_overview(pos.x())
        self._update_cursor(hit)
        self.update()

    def mouseMoveEvent(self, e: QMouseEvent) -> None:
        pos = e.position()
        self._last_pos = pos
        if self._drag is None:
            self._hover = pos
            hit = self._hit(pos)
            if hit != self._hover_hit or hit in ("track", "body"):
                self._hover_hit = hit
                self.update()
            self._update_cursor(hit)
            return
        if self._drag == "overview":
            self._pan_to_overview(pos.x())
            return
        self._apply_drag(pos)
        track = self._track()
        outside = pos.x() < track.left() or pos.x() > track.right()
        if outside and self.is_zoomed():
            if not self._autopan.isActive():
                self._autopan.start()
        else:
            self._autopan.stop()

    def _apply_drag(self, pos: QPointF) -> None:
        if self._rules is None:
            return
        if self._drag == "start":
            sel = self._rules.drag_start(self._sel, self._t(pos.x() - self._grab))
        elif self._drag == "end":
            sel = self._rules.drag_end(self._sel, self._t(pos.x() - self._grab))
        elif self._drag == "move":
            sel = self._rules.move(self._sel, self._t(pos.x()) - self._grab)
        else:
            return
        self.set_selection(sel, reveal=False)

    def _autopan_tick(self) -> None:
        track = self._track()
        x = self._last_pos.x()
        distance = x - track.right() if x > track.right() else x - track.left() if x < track.left() else 0.0
        if self._drag not in ("start", "end", "move") or distance == 0.0:
            self._autopan.stop()
            return
        speed = max(-4.0, min(4.0, distance / 30)) * self._span() * 0.006
        self._set_view(self._view0 + speed, self._span())
        self._apply_drag(self._last_pos)

    def _pan_to_overview(self, x: float) -> None:
        if self._rules is None:
            return
        rect = self._overview()
        center = (x - rect.left()) / rect.width() * self._rules.duration
        self._set_view(center - self._span() / 2, self._span())

    def mouseReleaseEvent(self, e: QMouseEvent) -> None:
        if self._drag is None:
            return super().mouseReleaseEvent(e)
        self._drag = None
        self._autopan.stop()
        self._update_cursor(self._hit(e.position()))
        self.update()
        self.interactionFinished.emit()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if self._rules is None or event.button() != Qt.MouseButton.LeftButton:
            return
        if self._hit(event.position()) in ("body", "start", "end") and self._span() > self._sel.length / 0.55:
            self.zoom_to_selection()
        else:
            self.zoom_fit()

    def leaveEvent(self, leaveEvent: QEvent) -> None:
        self._hover = None
        self._hover_hit = None
        self.update()

    def wheelEvent(self, arg__1: QWheelEvent) -> None:
        if self._rules is None:
            return
        delta = arg__1.angleDelta()
        horizontal = abs(delta.x()) > abs(delta.y())
        steps = (delta.x() if horizontal else delta.y()) / 120
        if horizontal or arg__1.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            self._set_view(self._view0 - steps * self._span() * 0.12, self._span())
        else:
            self.zoom(ZOOM_STEP ** steps, self._t(arg__1.position().x()))
        arg__1.accept()

    # ------------------------------------------------------------------ 키보드
    def keyPressEvent(self, e: QKeyEvent) -> None:
        if self._rules is None:
            return super().keyPressEvent(e)
        key, mods = e.key(), e.modifiers()
        step = 1.0 if mods & Qt.KeyboardModifier.ShiftModifier else 0.1
        if mods & Qt.KeyboardModifier.AltModifier:
            step = self._frame_step
        rules, sel = self._rules, self._sel
        if key in (Qt.Key.Key_Left, Qt.Key.Key_Right):
            direction = -1 if key == Qt.Key.Key_Left else 1
            if mods & Qt.KeyboardModifier.ControlModifier:
                self.set_selection(rules.drag_end(sel, sel.end + direction * step))
            else:
                self.set_selection(rules.move(sel, sel.start + direction * step))
        elif key == Qt.Key.Key_Home:
            self.set_selection(rules.move(sel, 0.0))
        elif key == Qt.Key.Key_End:
            self.set_selection(rules.move(sel, rules.duration))
        elif key in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
            self.zoom_in()
        elif key == Qt.Key.Key_Minus:
            self.zoom_out()
        elif key == Qt.Key.Key_0:
            self.zoom_fit()
        else:
            return super().keyPressEvent(e)

    def keyReleaseEvent(self, e: QKeyEvent) -> None:
        if not e.isAutoRepeat() and e.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Home, Qt.Key.Key_End):
            self.interactionFinished.emit()
        super().keyReleaseEvent(e)

    def focusInEvent(self, e: QFocusEvent) -> None:
        super().focusInEvent(e)
        self.update()

    def focusOutEvent(self, e: QFocusEvent) -> None:
        super().focusOutEvent(e)
        self.update()
