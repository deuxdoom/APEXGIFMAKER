# timeline_panel.py
"""타임라인 카드: 제목·조작 안내·구간 재생·확대 버튼, 타임라인, 시작·길이·끝 입력칸과 예상 프레임 수."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QWidget

from ...core.config import RECO_MAX_SEC, TRIM_MAX_SEC, TRIM_MIN_SEC
from ...core.gif import estimate_frames
from ...core.timecode import format_time, parse_time
from ...core.trim import Selection
from ...i18n import tr
from .common import Card, Chip, ElidedLabel, TimeField, make_button, make_icon_button
from .timeline import TimelineWidget


class TimelinePanel(Card):
    playRequested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(tr("timeline.title"), parent)
        self.hint = ElidedLabel(tr("timeline.hint"), "Hint")
        self.header.addSpacing(6)
        self.header.addWidget(self.hint, 1)
        self.play_button = make_button(tr("top.play"), "play", tooltip=tr("top.play.tip"))
        self.header.addWidget(self.play_button)
        separator = QFrame()
        separator.setObjectName("Separator")
        separator.setFixedHeight(20)
        self.header.addSpacing(4)
        self.header.addWidget(separator)
        self.header.addSpacing(4)
        self.zoom_out_button = make_icon_button("zoom_out", tr("timeline.zoom_out"))
        self.zoom_fit_button = make_icon_button("zoom_fit", tr("timeline.zoom_fit"))
        self.zoom_sel_button = make_icon_button("zoom_selection", tr("timeline.zoom_sel"))
        self.zoom_in_button = make_icon_button("zoom_in", tr("timeline.zoom_in"))
        for button in (self.zoom_out_button, self.zoom_fit_button, self.zoom_sel_button, self.zoom_in_button):
            self.header.addWidget(button)

        self.timeline = TimelineWidget()
        self.body.addWidget(self.timeline)

        fields = QHBoxLayout()
        fields.setSpacing(14)
        self.start_field = TimeField(tr("field.start"), format_time, parse_time)
        self.length_field = TimeField(tr("field.length"), lambda v: f"{v:.2f}", parse_time, width=70)
        self.end_field = TimeField(tr("field.end"), format_time, parse_time)
        limits = tr("timeline.limits", min=f"{TRIM_MIN_SEC:g}", max=f"{TRIM_MAX_SEC:g}")
        self.length_field.setToolTip(limits)
        for field in (self.start_field, self.length_field, self.end_field):
            fields.addWidget(field)
        fields.addSpacing(6)
        self.frames_chip = Chip()
        self.reco_chip = Chip(tr("timeline.over_reco", sec=f"{RECO_MAX_SEC:g}"), "warning")
        self.reco_chip.setVisible(False)
        fields.addWidget(self.frames_chip, 0, Qt.AlignmentFlag.AlignBottom)
        fields.addWidget(self.reco_chip, 0, Qt.AlignmentFlag.AlignBottom)
        fields.addStretch(1)
        self.body.addLayout(fields)

        self._fps = 12
        self._dedupe = False
        self.play_button.clicked.connect(self.playRequested.emit)
        self.zoom_out_button.clicked.connect(self.timeline.zoom_out)
        self.zoom_fit_button.clicked.connect(self.timeline.zoom_fit)
        self.zoom_sel_button.clicked.connect(self.timeline.zoom_to_selection)
        self.zoom_in_button.clicked.connect(self.timeline.zoom_in)
        self.timeline.selectionChanged.connect(self._sync_fields)
        self.timeline.viewChanged.connect(self._sync_zoom_buttons)
        self.start_field.edited.connect(lambda v: self._edit("start", v))
        self.length_field.edited.connect(lambda v: self._edit("length", v))
        self.end_field.edited.connect(lambda v: self._edit("end", v))
        self.start_field.nudged.connect(lambda d: self._nudge("start", d))
        self.length_field.nudged.connect(lambda d: self._nudge("length", d))
        self.end_field.nudged.connect(lambda d: self._nudge("end", d))
        self.set_video_loaded(False)

    def set_video_loaded(self, loaded: bool) -> None:
        for widget in (self.play_button, self.zoom_out_button, self.zoom_fit_button, self.zoom_sel_button,
                       self.zoom_in_button, self.start_field, self.length_field, self.end_field):
            widget.setEnabled(loaded)
        if not loaded:
            for field in (self.start_field, self.length_field, self.end_field):
                field.clear()
            self.frames_chip.setText("")
            self.frames_chip.setVisible(False)
            self.reco_chip.setVisible(False)
            self.timeline.clear()

    def set_frame_settings(self, fps: int, dedupe: bool) -> None:
        self._fps, self._dedupe = fps, dedupe
        sel = self.timeline.selection()
        self._sync_fields(sel.start, sel.end)

    def _sync_fields(self, start: float, end: float) -> None:
        if not self.timeline.has_video():
            return
        length = end - start
        self.start_field.set_value(start)
        self.length_field.set_value(length)
        self.end_field.set_value(end)
        frames = estimate_frames(length, self._fps)
        self.frames_chip.setText(tr("timeline.frames_max" if self._dedupe else "timeline.frames", frames=frames))
        self.frames_chip.setVisible(True)
        self.reco_chip.setVisible(length > RECO_MAX_SEC + 1e-6)

    def _sync_zoom_buttons(self) -> None:
        timeline = self.timeline
        self.zoom_in_button.setEnabled(timeline.can_zoom_in())
        self.zoom_out_button.setEnabled(timeline.is_zoomed())
        self.zoom_fit_button.setEnabled(timeline.is_zoomed())

    def _edit(self, kind: str, value: float) -> None:
        rules, sel = self.timeline.rules(), self.timeline.selection()
        if rules is None:
            return
        new = {"start": rules.set_start, "end": rules.set_end, "length": rules.set_length}[kind](sel, value)
        self.timeline.set_selection(new)
        # 값이 그대로여도(규칙에 막힌 입력 등) 입력칸을 정리된 표기로 되돌립니다.
        self.start_field.force_value(new.start)
        self.length_field.force_value(new.length)
        self.end_field.force_value(new.end)

    def _nudge(self, kind: str, delta: float) -> None:
        rules, sel = self.timeline.rules(), self.timeline.selection()
        if rules is None:
            return
        if kind == "start":
            new = rules.drag_start(sel, sel.start + delta)
        elif kind == "end":
            new = rules.drag_end(sel, sel.end + delta)
        else:
            new = rules.set_length(sel, sel.length + delta)
        self.timeline.set_selection(new)

    def selection(self) -> Selection:
        return self.timeline.selection()
