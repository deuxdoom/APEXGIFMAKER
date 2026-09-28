# frame.py
"""제목 표시줄 없는 창의 껍데기입니다. (참고: TVerDownloader의 window_frame.py)

창은 투명한 ShadowShell(그림자를 그림) 안에 불투명한 WindowSurface(둥근 배경)를 담는 두 겹입니다.
- 크기 조절 띠는 표면 안쪽 가장자리에 둡니다. 완전히 투명한 픽셀은 클릭이 뒤로 통과하기 때문입니다.
- 최대화는 Qt의 showMaximized 대신 작업 영역에 맞춰 직접 넓힙니다. 프레임 없는 창을 Qt가
  최대화하면 작업 표시줄까지 덮고 상태도 FullScreen으로 잡히기 때문입니다(QTBUG-8361).
- 화면 위쪽 스냅과 Win+↑가 보내는 WM_SYSCOMMAND도 가로채서 같은 최대화로 바꿉니다.
"""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QEvent, QObject, QPoint, QRect, QSize, Qt
from PySide6.QtGui import QColor, QCursor, QGuiApplication, QMouseEvent, QPainter, QPaintEvent, QPixmap, QResizeEvent
from PySide6.QtWidgets import QDialog, QFrame, QHBoxLayout, QLabel, QToolButton, QVBoxLayout, QWidget

from ..i18n import tr
from . import icons

WINDOW_RADIUS = 10
SHADOW_BLUR = 10
SHADOW_OFFSET = 3
SHADOW_LAYER_ALPHA = 6
SHADOW_MARGINS = (SHADOW_BLUR - SHADOW_OFFSET, SHADOW_BLUR - SHADOW_OFFSET,
                  SHADOW_BLUR + SHADOW_OFFSET, SHADOW_BLUR + SHADOW_OFFSET)
GRIP_THICKNESS = 6
GRIP_CORNER = 14
DIALOG_TITLE_HEIGHT = 40
WIDGET_SIZE_MAX = 16777215

_WM_SYSCOMMAND = 0x0112
_SC_MAXIMIZE = 0xF030
_SC_RESTORE = 0xF120


def extra_size() -> tuple[int, int]:
    """그림자 여백 때문에 창이 내용보다 커지는 (가로, 세로) 크기."""
    left, top, right, bottom = SHADOW_MARGINS
    return left + right, top + bottom


def make_frameless(window: QWidget) -> None:
    """제목 표시줄을 떼고 배경을 투명하게 만듭니다. 창을 보이기 전에 부릅니다."""
    window.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
    window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)


class WindowFrame:
    """프레임 없는 창의 최대화 상태와 되돌릴 크기를 관리합니다."""

    def __init__(self, window: QWidget, on_changed: Callable[[bool], None] | None = None):
        self.window = window
        self.on_changed = on_changed
        self._normal: QRect | None = None

    def is_maximized(self) -> bool:
        return self._normal is not None

    def normal_geometry(self) -> QRect:
        """최대화 중이면 되돌아갈 크기, 아니면 지금 크기입니다. (설정 저장용)"""
        return QRect(self._normal) if self._normal is not None else self.window.geometry()

    def maximize(self) -> None:
        screen = self.window.screen()
        if self.is_maximized() or screen is None:
            return
        self._normal = self.window.geometry()
        self.window.setGeometry(screen.availableGeometry())
        self._notify()

    def restore(self) -> None:
        if self._normal is None:
            return
        geometry, self._normal = self._normal, None
        self.window.setGeometry(geometry)
        self._notify()

    def toggle(self) -> None:
        self.restore() if self.is_maximized() else self.maximize()

    def restore_under_cursor(self, cursor: QPoint, grab_y: int) -> None:
        """최대화된 창을 끌어 내릴 때, 잡고 있던 가로 위치 비율을 유지한 채 되돌립니다."""
        if not self.is_maximized():
            return
        ratio = (cursor.x() - self.window.x()) / max(1, self.window.width())
        self.restore()
        self.window.move(int(cursor.x() - ratio * self.window.width()), cursor.y() - grab_y)

    def _notify(self) -> None:
        if self.on_changed is not None:
            self.on_changed(self.is_maximized())


def handle_system_command(frame: WindowFrame | None, message: int) -> bool:
    """Windows의 최대화·복원 명령(스냅, Win+↑)을 우리 방식의 최대화로 바꿉니다. 처리했으면 True."""
    if frame is None:
        return False
    try:
        from ctypes import wintypes
        msg = wintypes.MSG.from_address(int(message))
    except (ImportError, ValueError, OSError):
        return False
    if msg.message != _WM_SYSCOMMAND:
        return False
    command = int(msg.wParam) & 0xFFF0
    if command == _SC_MAXIMIZE:
        frame.maximize()
        return True
    if command == _SC_RESTORE and frame.is_maximized():
        frame.restore()
        return True
    return False


class _EdgeGrip(QWidget):
    """누르면 Windows에 크기 조절을 맡기는 투명한 띠 (startSystemResize)."""

    def __init__(self, parent: QWidget, edges: Qt.Edge, cursor: Qt.CursorShape):
        super().__init__(parent)
        self._edges = edges
        self.setCursor(cursor)

    def mousePressEvent(self, e: QMouseEvent) -> None:
        if e.button() != Qt.MouseButton.LeftButton:
            e.ignore()
            return
        handle = self.window().windowHandle()
        if handle is not None:
            handle.startSystemResize(self._edges)


class DragBar(QFrame):
    """끌면 창이 따라오는 줄(제목 표시줄 대신). 더블클릭하면 최대화/복원합니다.

    누르자마자가 아니라 몇 픽셀 움직인 뒤에 startSystemMove를 부릅니다. 바로 부르면 Windows의
    이동 루프가 두 번째 클릭을 가져가서 더블클릭이 동작하지 않습니다.
    """

    DRAG_THRESHOLD = 5

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.frame: WindowFrame | None = None
        self._press_global: QPoint | None = None
        self._press_local = QPoint()

    def mousePressEvent(self, e: QMouseEvent) -> None:
        if e.button() != Qt.MouseButton.LeftButton:
            e.ignore()
            return
        self._press_global = e.globalPosition().toPoint()
        self._press_local = e.position().toPoint()

    def mouseMoveEvent(self, e: QMouseEvent) -> None:
        if self._press_global is None:
            return
        now = e.globalPosition().toPoint()
        if (now - self._press_global).manhattanLength() < self.DRAG_THRESHOLD:
            return
        self._press_global = None
        window = self.window()
        if self.frame is not None and self.frame.is_maximized():
            self.frame.restore_under_cursor(now, self._press_local.y() + self.mapTo(window, QPoint(0, 0)).y())
        handle = window.windowHandle()
        if handle is not None:
            handle.startSystemMove()

    def mouseReleaseEvent(self, e: QMouseEvent) -> None:
        self._press_global = None

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.frame is not None:
            self._press_global = None
            self.frame.toggle()


class ShadowShell(QWidget):
    """창의 맨 바깥. 안쪽 표면(WindowSurface)을 여백만큼 들여놓고 그 여백에 그림자를 그립니다."""

    def __init__(self, resizable: bool = True):
        super().__init__()
        self.setObjectName("WindowShell")
        self._shadow = QPixmap()
        self._maximized = False
        self.surface = QFrame()
        self.surface.setObjectName("WindowSurface")
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.addWidget(self.surface)
        self._apply_margins()
        self._grips = self._make_grips() if resizable else []

    def _make_grips(self) -> list[_EdgeGrip]:
        edge, cursor = Qt.Edge, Qt.CursorShape
        spec = (
            (edge.TopEdge, cursor.SizeVerCursor), (edge.BottomEdge, cursor.SizeVerCursor),
            (edge.LeftEdge, cursor.SizeHorCursor), (edge.RightEdge, cursor.SizeHorCursor),
            (edge.TopEdge | edge.LeftEdge, cursor.SizeFDiagCursor),
            (edge.TopEdge | edge.RightEdge, cursor.SizeBDiagCursor),
            (edge.BottomEdge | edge.LeftEdge, cursor.SizeBDiagCursor),
            (edge.BottomEdge | edge.RightEdge, cursor.SizeFDiagCursor),
        )
        return [_EdgeGrip(self, edges, shape) for edges, shape in spec]

    def _apply_margins(self) -> None:
        left, top, right, bottom = (0, 0, 0, 0) if self._maximized else SHADOW_MARGINS
        layout = self.layout()
        if layout is not None:
            layout.setContentsMargins(left, top, right, bottom)

    def set_maximized(self, maximized: bool) -> None:
        """최대화되면 그림자·여백·둥근 모서리를 걷습니다."""
        if maximized == self._maximized:
            return
        self._maximized = maximized
        self._apply_margins()
        self._shadow = QPixmap()
        # QWidget에 읽기 전용 "maximized" 속성이 이미 있어서 다른 이름을 씁니다.
        self.surface.setProperty("fullBleed", "true" if maximized else "false")
        style = self.surface.style()
        style.unpolish(self.surface)
        style.polish(self.surface)
        for grip in self._grips:
            grip.setVisible(not maximized)
        self.update()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._shadow = QPixmap()
        self._place_grips()

    def _place_grips(self) -> None:
        if self._maximized or not self._grips:
            return
        rect = self.surface.geometry()
        thick, corner = GRIP_THICKNESS, GRIP_CORNER
        inner_w, inner_h = max(0, rect.width() - 2 * corner), max(0, rect.height() - 2 * corner)
        places = (
            QRect(rect.x() + corner, rect.y(), inner_w, thick),
            QRect(rect.x() + corner, rect.bottom() - thick + 1, inner_w, thick),
            QRect(rect.x(), rect.y() + corner, thick, inner_h),
            QRect(rect.right() - thick + 1, rect.y() + corner, thick, inner_h),
            QRect(rect.x(), rect.y(), corner, corner),
            QRect(rect.right() - corner + 1, rect.y(), corner, corner),
            QRect(rect.x(), rect.bottom() - corner + 1, corner, corner),
            QRect(rect.right() - corner + 1, rect.bottom() - corner + 1, corner, corner),
        )
        for grip, place in zip(self._grips, places):
            grip.setGeometry(place)
            grip.raise_()

    def raise_grips(self) -> None:
        """내용을 채운 뒤 띠가 위젯들 아래로 깔리지 않도록 다시 올립니다."""
        for grip in self._grips:
            grip.raise_()

    def paintEvent(self, e: QPaintEvent) -> None:
        # 덮어쓰기(Source)로 그려야 다시 그릴 때마다 알파가 쌓여 그림자가 진해지지 않습니다.
        if self._maximized:
            return
        if self._shadow.isNull():
            self._shadow = self._build_shadow()
        painter = QPainter(self)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.drawPixmap(0, 0, self._shadow)

    def _build_shadow(self) -> QPixmap:
        ratio = self.devicePixelRatioF() or 1.0
        pixmap = QPixmap(max(1, int(self.width() * ratio)), max(1, int(self.height() * ratio)))
        pixmap.setDevicePixelRatio(ratio)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, SHADOW_LAYER_ALPHA))
        inner = self.surface.geometry().translated(SHADOW_OFFSET, SHADOW_OFFSET)
        for step in range(SHADOW_BLUR, 0, -1):
            painter.drawRoundedRect(inner.adjusted(-step, -step, step, step),
                                    WINDOW_RADIUS + step, WINDOW_RADIUS + step)
        painter.end()
        return pixmap


def make_tool_button(icon_name: str, tooltip: str = "", *, role: str = "text", size: int = 18,
                     object_name: str = "", parent: QWidget | None = None) -> QToolButton:
    button = QToolButton(parent)
    if object_name:
        button.setObjectName(object_name)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setToolTip(tooltip)
    button.setAutoRaise(True)
    icons.set_icon(button, icon_name, role, size)
    return button


class DialogTitleBar(DragBar):
    """대화상자 맨 위 줄: 앱 아이콘, 제목, 닫기 단추."""

    def __init__(self, on_close: Callable[[], object], title: str, closable: bool = True):
        super().__init__()
        self.setObjectName("DialogTitleBar")
        self.setFixedHeight(DIALOG_TITLE_HEIGHT)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 8, 0)
        layout.setSpacing(8)
        self.icon_label = QLabel()
        self.icon_label.setPixmap(app_icon_pixmap(16))
        layout.addWidget(self.icon_label)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("DialogTitle")
        layout.addWidget(self.title_label)
        layout.addStretch(1)
        self.close_button = make_tool_button("dismiss", tr("dlg.close"), size=16, object_name="WinClose")
        self.close_button.clicked.connect(on_close)
        self.close_button.setVisible(closable)
        layout.addWidget(self.close_button)


def app_icon_pixmap(size: int) -> QPixmap:
    from .app_icon import app_icon
    return app_icon().pixmap(QSize(size, size))


def _move_inside(window: QWidget, center: QPoint, area: QRect) -> None:
    frame = window.frameGeometry()
    frame.moveCenter(center)
    x = min(max(frame.x(), area.x()), max(area.x(), area.right() - frame.width() + 1))
    y = min(max(frame.y(), area.y()), max(area.y(), area.bottom() - frame.height() + 1))
    window.move(x, y)


def center_on_screen(window: QWidget) -> None:
    screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
    if screen is not None:
        area = screen.availableGeometry()
        _move_inside(window, area.center(), area)


def center_dialog(dialog: QWidget) -> None:
    """대화상자를 부모 창 가운데에 둡니다. 부모가 없거나 최소화되어 있으면 화면 가운데입니다."""
    parent = dialog.parentWidget()
    parent = parent.window() if parent is not None else None
    if parent is None or not parent.isVisible() or parent.isMinimized():
        center_on_screen(dialog)
        return
    screen = parent.screen() or QGuiApplication.primaryScreen()
    if screen is not None:
        _move_inside(dialog, parent.geometry().center(), screen.availableGeometry())


class _DialogPlacer(QObject):
    """처음 보일 때 한 번 부모 가운데로 옮깁니다. (프레임 없는 창은 Qt의 배치 계산이 어긋남)"""

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._placed = False

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.Show and not self._placed and isinstance(watched, QWidget):
            self._placed = True
            center_dialog(watched)
        return False


def apply_dialog_frame(dialog: QDialog, *, title: str = "", resizable: bool = False,
                       closable: bool = True) -> ShadowShell:
    """구성을 마친 대화상자를 메인 창과 같은 모양(제목 줄·둥근 모서리·그림자)으로 감쌉니다.

    대화상자에 이미 깔린 레이아웃을 표면 안으로 옮기는 방식이라, 내용을 다 만든 뒤에 부릅니다.
    """
    inner = dialog.layout()
    make_frameless(dialog)
    extra_w, extra_h = extra_size()
    extra_h += DIALOG_TITLE_HEIGHT

    def grown(value: int, extra: int) -> int:
        return value if value in (0, WIDGET_SIZE_MAX) else min(WIDGET_SIZE_MAX, value + extra)

    minimum, maximum = dialog.minimumSize(), dialog.maximumSize()
    dialog.setMinimumSize(grown(minimum.width(), extra_w), grown(minimum.height(), extra_h))
    dialog.setMaximumSize(grown(maximum.width(), extra_w), grown(maximum.height(), extra_h))

    shell = ShadowShell(resizable=resizable)
    body = QWidget()
    body.setObjectName("DialogBody")
    if inner is not None:
        body.setLayout(inner)
    surface_layout = QVBoxLayout(shell.surface)
    surface_layout.setContentsMargins(0, 0, 0, 0)
    surface_layout.setSpacing(0)
    bar = DialogTitleBar(dialog.reject, title or dialog.windowTitle(), closable)
    surface_layout.addWidget(bar)
    surface_layout.addWidget(body, 1)
    outer = QVBoxLayout(dialog)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(0)
    outer.addWidget(shell)
    shell.raise_grips()

    placer = _DialogPlacer(dialog)
    dialog.installEventFilter(placer)
    dialog.setProperty("framed", True)
    return shell


def run_dialog(dialog: QDialog) -> int:
    """모달로 띄우고 결과를 돌려준 뒤 지웁니다. 부모가 붙잡고 있어 메모리에 남는 것을 막습니다."""
    try:
        return dialog.exec()
    finally:
        dialog.deleteLater()
