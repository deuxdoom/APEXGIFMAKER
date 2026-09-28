# app_icon.py
"""앱 로고(assets/applogo.svg)를 여러 크기로 담은 QIcon입니다. SVG를 못 읽으면 PNG를 씁니다."""
from __future__ import annotations

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from ..core import config

SIZES = (16, 20, 24, 32, 40, 48, 64, 96, 128, 256)
_cached: QIcon | None = None


def _render_svg(renderer: QSvgRenderer, size: int) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()
    return pixmap


def app_icon() -> QIcon:
    global _cached
    if _cached is not None:
        return _cached
    _cached = QIcon()
    try:
        data = config.asset_path("applogo.svg").read_bytes()
    except OSError:
        data = b""
    renderer = QSvgRenderer(QByteArray(data)) if data else None
    if renderer is not None and renderer.isValid():
        for size in SIZES:
            _cached.addPixmap(_render_svg(renderer, size))
        return _cached
    source = QPixmap(str(config.asset_path("applogo.png")))
    if not source.isNull():
        for size in SIZES:
            _cached.addPixmap(source.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio,
                                            Qt.TransformationMode.SmoothTransformation))
    return _cached
