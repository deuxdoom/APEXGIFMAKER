# options_panel.py
"""GIF 옵션 카드: 크기, FPS, 프레임 방식, 스케일, 디더링."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QComboBox, QGridLayout, QHBoxLayout, QSpinBox, QWidget

from ...core.config import DEFAULT_HEIGHT, DEFAULT_WIDTH, FPS_MAX, FPS_MIN, SIZE_MAX, SIZE_MIN
from ...core.gif import DITHER_MODES, FRAME_MODES, SCALE_MODES, GifOptions
from ...i18n import tr
from .common import Card, make_icon_button, make_label


def _combo(prefix: str, values: tuple[str, ...]) -> QComboBox:
    combo = QComboBox()
    combo.setCursor(Qt.CursorShape.PointingHandCursor)
    for index, value in enumerate(values):
        combo.addItem(tr(f"{prefix}.{value}"), value)
        combo.setItemData(index, tr(f"{prefix}.{value}.tip"), Qt.ItemDataRole.ToolTipRole)
    return combo


def _spin(minimum: int, maximum: int, width: int = 72) -> QSpinBox:
    spin = QSpinBox()
    spin.setRange(minimum, maximum)
    spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
    spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
    spin.setFixedWidth(width)
    spin.setKeyboardTracking(False)
    return spin


class OptionsPanel(Card):
    changed = Signal()
    helpRequested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(tr("options.title"), parent)
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)

        self.width_spin = _spin(SIZE_MIN, SIZE_MAX)
        self.height_spin = _spin(SIZE_MIN, SIZE_MAX)
        self.reset_button = make_icon_button("reset", tr("options.size.reset"), role="muted", size=16)
        size_row = QHBoxLayout()
        size_row.setSpacing(6)
        size_row.addWidget(self.width_spin)
        size_row.addWidget(make_label("×", "Muted"))
        size_row.addWidget(self.height_spin)
        size_row.addWidget(self.reset_button)
        size_row.addStretch(1)

        self.fps_spin = _spin(FPS_MIN, FPS_MAX, 60)
        self.fps_spin.setToolTip(tr("options.fps.tip"))
        self.frames_combo = _combo("options.frames", FRAME_MODES)
        self.scale_combo = _combo("options.scale", SCALE_MODES)
        self.dither_combo = _combo("options.dither", DITHER_MODES)
        self.help_button = make_icon_button("help", tr("options.dither.help"), role="muted", size=16)
        dither_row = QHBoxLayout()
        dither_row.setSpacing(4)
        dither_row.addWidget(self.dither_combo, 1)
        dither_row.addWidget(self.help_button)

        grid.addWidget(make_label(tr("options.size"), "FieldLabel"), 0, 0)
        grid.addLayout(size_row, 0, 1)
        grid.addWidget(make_label(tr("options.fps"), "FieldLabel"), 0, 2)
        grid.addWidget(self.fps_spin, 0, 3, Qt.AlignmentFlag.AlignLeft)
        grid.addWidget(make_label(tr("options.scale"), "FieldLabel"), 1, 0)
        grid.addWidget(self.scale_combo, 1, 1)
        grid.addWidget(make_label(tr("options.frames"), "FieldLabel"), 1, 2)
        grid.addWidget(self.frames_combo, 1, 3)
        grid.addWidget(make_label(tr("options.dither"), "FieldLabel"), 2, 0)
        grid.addLayout(dither_row, 2, 1)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)
        self.body.addLayout(grid)
        self.body.addStretch(1)

        for spin in (self.width_spin, self.height_spin, self.fps_spin):
            spin.valueChanged.connect(lambda _value: self.changed.emit())
        for combo in (self.frames_combo, self.scale_combo, self.dither_combo):
            combo.currentIndexChanged.connect(self._combo_changed)
        self.reset_button.clicked.connect(self._reset_size)
        self.help_button.clicked.connect(self.helpRequested.emit)
        self.set_options(GifOptions())

    def _combo_changed(self) -> None:
        for combo in (self.frames_combo, self.scale_combo, self.dither_combo):
            combo.setToolTip(combo.itemData(combo.currentIndex(), Qt.ItemDataRole.ToolTipRole) or "")
        self.changed.emit()

    def _reset_size(self) -> None:
        self.width_spin.setValue(DEFAULT_WIDTH)
        self.height_spin.setValue(DEFAULT_HEIGHT)

    def options(self) -> GifOptions:
        return GifOptions(
            width=self.width_spin.value(), height=self.height_spin.value(), fps=self.fps_spin.value(),
            scale_mode=self.scale_combo.currentData(), dither=self.dither_combo.currentData(),
            frame_mode=self.frames_combo.currentData(),
        ).normalized()

    def set_options(self, opts: GifOptions) -> None:
        opts = opts.normalized()
        self.width_spin.setValue(opts.width)
        self.height_spin.setValue(opts.height)
        self.fps_spin.setValue(opts.fps)
        for combo, value in ((self.scale_combo, opts.scale_mode), (self.dither_combo, opts.dither),
                             (self.frames_combo, opts.frame_mode)):
            combo.setCurrentIndex(max(0, combo.findData(value)))
        self._combo_changed()
