# win32.py
"""Windows 전용 보조 기능입니다. 다른 OS에서는 아무 일도 하지 않습니다."""
from __future__ import annotations

import ctypes
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

IS_WINDOWS = sys.platform.startswith("win")

_GWL_STYLE = -16
_WS_MINIMIZEBOX = 0x00020000
_WS_MAXIMIZEBOX = 0x00010000
_WS_SYSMENU = 0x00080000


def set_app_user_model_id(app_id: str) -> None:
    """작업 표시줄에서 python.exe가 아니라 이 앱으로 묶이도록 AppUserModelID를 지정합니다."""
    if not IS_WINDOWS:
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(ctypes.c_wchar_p(app_id))
    except (AttributeError, OSError):
        pass


def allow_set_foreground(pid: int) -> None:
    """다른 프로세스(이미 실행 중인 인스턴스)가 자기 창을 앞으로 가져올 수 있게 허락합니다."""
    if not IS_WINDOWS:
        return
    try:
        ctypes.windll.user32.AllowSetForegroundWindow(int(pid))
    except (AttributeError, OSError):
        pass


def enable_taskbar_minimize(window: QWidget) -> None:
    """프레임 없는 창도 작업 표시줄 단추를 눌러 최소화·복원되도록 창 스타일에 최소화 상자를 켭니다."""
    if not IS_WINDOWS:
        return
    try:
        user32 = ctypes.windll.user32
        hwnd = ctypes.c_void_p(int(window.winId()))
        get_style = user32.GetWindowLongPtrW
        set_style = user32.SetWindowLongPtrW
        get_style.restype = ctypes.c_ssize_t
        get_style.argtypes = (ctypes.c_void_p, ctypes.c_int)
        set_style.restype = ctypes.c_ssize_t
        set_style.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_ssize_t)
        style = get_style(hwnd, _GWL_STYLE)
        set_style(hwnd, _GWL_STYLE, style | _WS_MINIMIZEBOX | _WS_MAXIMIZEBOX | _WS_SYSMENU)
    except (AttributeError, OSError, ValueError):
        pass


def bring_to_front(window: QWidget) -> None:
    """최소화를 풀고 창을 확실히 맨 앞으로 가져옵니다. (Windows의 포커스 제한을 우회)"""
    window.setWindowState(window.windowState() & ~Qt.WindowState.WindowMinimized)
    window.show()
    window.raise_()
    window.activateWindow()
    if not IS_WINDOWS:
        return
    try:
        user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
        hwnd = ctypes.c_void_p(int(window.winId()))
        user32.GetForegroundWindow.restype = ctypes.c_void_p
        user32.GetWindowThreadProcessId.argtypes = (ctypes.c_void_p, ctypes.c_void_p)
        user32.GetWindowThreadProcessId.restype = ctypes.c_ulong
        foreground = user32.GetForegroundWindow()
        fg_thread = user32.GetWindowThreadProcessId(foreground, None) if foreground else 0
        own_thread = kernel32.GetCurrentThreadId()
        attached = bool(fg_thread and fg_thread != own_thread
                        and user32.AttachThreadInput(fg_thread, own_thread, True))
        try:
            user32.ShowWindow(hwnd, 9)            # SW_RESTORE
            user32.SetForegroundWindow(hwnd)
            user32.SetActiveWindow(hwnd)
        finally:
            if attached:
                user32.AttachThreadInput(fg_thread, own_thread, False)
    except (AttributeError, OSError, ValueError):
        pass
