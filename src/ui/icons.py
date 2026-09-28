# icons.py
"""Fluent UI System Icons(MIT, assets/icons)를 테마 색으로 칠해서 QIcon·QPixmap으로 만듭니다.

원본 SVG는 모두 단색(#212121)이라 색 문자열만 바꿔 다시 그립니다.
버튼에는 set_icon()으로 아이콘 이름과 색 역할을 속성으로 남겨 두고, 테마가 바뀌면
refresh_all()이 그 속성을 보고 다시 칠합니다.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QByteArray, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QAbstractButton, QApplication, QLabel

from ..core import config
from . import theme

SOURCE_COLOR = "#212121"
ROLES = ("text", "muted", "faint", "accent", "on_accent", "success", "warning", "danger", "select")

_svg_cache: dict[str, str] = {}
_pixmap_cache: dict[tuple[str, str, int, float], QPixmap] = {}


def role_color(role: str) -> str:
    p = theme.current()
    return {
        "text": p.text, "muted": p.text_muted, "faint": p.text_faint, "accent": p.accent,
        "on_accent": p.accent_text, "success": p.success, "warning": p.warning, "danger": p.danger,
        "select": p.select,
    }.get(role, p.text)


def _svg(name: str) -> str:
    if name not in _svg_cache:
        path = config.asset_path(f"icons/{name}.svg")
        try:
            _svg_cache[name] = path.read_text(encoding="utf-8")
        except OSError:
            _svg_cache[name] = ""
    return _svg_cache[name]


def pixmap(name: str, color: str, size: int, dpr: float = 1.0) -> QPixmap:
    """아이콘 하나를 size(논리 픽셀) 크기로 그립니다. 없는 아이콘은 투명한 그림입니다."""
    key = (name, color, size, dpr)
    cached = _pixmap_cache.get(key)
    if cached is not None:
        return cached
    physical = max(1, round(size * dpr))
    image = QPixmap(physical, physical)
    image.fill(Qt.GlobalColor.transparent)
    source = _svg(name)
    if source:
        renderer = QSvgRenderer(QByteArray(source.replace(SOURCE_COLOR, QColor(color).name()).encode("utf-8")))
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        renderer.render(painter, QRectF(0, 0, physical, physical))
        painter.end()
    image.setDevicePixelRatio(dpr)
    _pixmap_cache[key] = image
    return image


def icon(name: str, color: str | None = None, size: int = 18) -> QIcon:
    """보통 상태와 비활성 상태 그림을 1배·2배 해상도로 담은 아이콘입니다."""
    normal = color or role_color("text")
    faint = role_color("faint")
    result = QIcon()
    for dpr in (1.0, 2.0):
        result.addPixmap(pixmap(name, normal, size, dpr), QIcon.Mode.Normal)
        result.addPixmap(pixmap(name, faint, size, dpr), QIcon.Mode.Disabled)
    return result


def set_icon(widget: QAbstractButton | QLabel, name: str, role: str = "text", size: int = 18) -> None:
    """위젯에 아이콘을 달고, 테마가 바뀌면 다시 칠할 수 있도록 이름·역할을 속성으로 남깁니다."""
    widget.setProperty("iconName", name)
    widget.setProperty("iconRole", role)
    widget.setProperty("iconSize", size)
    _apply(widget)


def _apply(widget: QAbstractButton | QLabel) -> None:
    name, role, size = widget.property("iconName"), widget.property("iconRole"), widget.property("iconSize")
    if not isinstance(name, str) or not name:
        return
    size = size if isinstance(size, int) else 18
    color = role_color(role if isinstance(role, str) else "text")
    if isinstance(widget, QAbstractButton):
        widget.setIcon(icon(name, color, size))
        widget.setIconSize(QSize(size, size))
    else:
        widget.setPixmap(pixmap(name, color, size, widget.devicePixelRatioF() or 1.0))


def refresh_all() -> None:
    _pixmap_cache.clear()
    app = QApplication.instance()
    if not isinstance(app, QApplication):
        return
    for widget in app.allWidgets():
        if isinstance(widget, (QAbstractButton, QLabel)) and widget.property("iconName"):
            _apply(widget)


def icon_file(name: str, color: str, size: int) -> str:
    """QSS의 image: url()에 쓸 PNG를 임시 폴더에 만들고 경로(슬래시 구분)를 반환합니다."""
    folder = config.temp_dir() / "icons"
    folder.mkdir(parents=True, exist_ok=True)
    target: Path = folder / f"{name}-{QColor(color).name().lstrip('#')}-{size}.png"
    if not target.is_file():
        pixmap(name, color, size, 2.0).save(str(target), "PNG")
    return target.as_posix()
