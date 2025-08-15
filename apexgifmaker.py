# APEXGIFMAKER / apexgifmaker.py
import os
import sys
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QLockFile, QStandardPaths, QThread, Qt, QLocale
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from src.ui import MainWindow

APP_UNIQUE_NAME = "ApexGifMaker_v2_localserver"
LOCKFILE_NAME   = "ApexGifMaker_v2.lock"


def _temp_dir() -> str:
    path = QStandardPaths.writableLocation(QStandardPaths.TempLocation)
    if not path:
        path = os.environ.get("TMP") or os.environ.get("TEMP") or os.getcwd()
    return path


def _allow_set_foreground_for(pid: int) -> None:
    """새 인스턴스에서 기존 인스턴스 PID에 포커스 권한 부여(Windows)."""
    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes
        ctypes.windll.user32.AllowSetForegroundWindow(int(pid))
    except Exception:
        pass


def _send_activate_signal(name: str) -> bool:
    """
    이미 실행 중인 인스턴스에 활성화 요청.
    1) 서버가 먼저 'pid:<pid>'를 보내옴 → 그 PID에 AllowSetForegroundWindow(pid)
    2) 'activate' 전송 → ack 수신
    """
    sock = QLocalSocket()
    sock.connectToServer(name)
    if not sock.waitForConnected(600):
        sock.abort()
        return False

    try:
        # 1) 서버 PID 수신
        if not sock.waitForReadyRead(800):
            return False
        raw = bytes(sock.readAll() or b"")
        if raw.startswith(b"pid:"):
            try:
                server_pid = int(raw[4:].strip() or b"0")
                _allow_set_foreground_for(server_pid)
            except Exception:
                pass

        # 2) activate 전송
        sock.write(b"activate")
        sock.flush()
        sock.waitForBytesWritten(400)

        # ack 동기화(선택)
        sock.waitForReadyRead(400)
        _ = sock.readAll()
    finally:
        sock.close()
    return True


def _bring_to_front(win: MainWindow):
    """기존 창을 확실히 전면 활성화 (Windows 강화 루틴 포함)."""
    try:
        win.setWindowState(win.windowState() & ~Qt.WindowMinimized)
        win.show()
        win.raise_()
        win.activateWindow()
    except Exception:
        pass

    if not sys.platform.startswith("win"):
        return

    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        hwnd = int(win.winId())

        GetForegroundWindow = user32.GetForegroundWindow
        GetForegroundWindow.restype = wintypes.HWND

        GetWindowThreadProcessId = user32.GetWindowThreadProcessId
        GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        GetWindowThreadProcessId.restype  = wintypes.DWORD

        AttachThreadInput = user32.AttachThreadInput
        AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
        AttachThreadInput.restype  = wintypes.BOOL

        SetForegroundWindow = user32.SetForegroundWindow
        SetForegroundWindow.argtypes = [wintypes.HWND]
        SetForegroundWindow.restype  = wintypes.BOOL

        SetActiveWindow = user32.SetActiveWindow
        SetActiveWindow.argtypes = [wintypes.HWND]
        SetActiveWindow.restype  = wintypes.HWND

        SetFocus = user32.SetFocus
        SetFocus.argtypes = [wintypes.HWND]
        SetFocus.restype  = wintypes.HWND

        ShowWindow = user32.ShowWindow
        ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        ShowWindow.restype  = wintypes.BOOL

        SetWindowPos = user32.SetWindowPos
        SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
        SetWindowPos.restype  = wintypes.BOOL

        FLASHW_TRAY = 0x00000002
        class FLASHWINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", ctypes.c_uint),
                ("hwnd",   wintypes.HWND),
                ("dwFlags", ctypes.c_uint),
                ("uCount", ctypes.c_uint),
                ("dwTimeout", ctypes.c_uint),
            ]
        FlashWindowEx = user32.FlashWindowEx

        SW_RESTORE = 9
        HWND_TOPMOST     = wintypes.HWND(-1)
        HWND_NOTOPMOST   = wintypes.HWND(-2)
        SWP_NOMOVE  = 0x0002
        SWP_NOSIZE  = 0x0001
        SWP_SHOWWINDOW = 0x0040

        # 1) 최소화 복구
        ShowWindow(hwnd, SW_RESTORE)

        # 2) 포그라운드 쓰레드와 입력 연결하여 포커스 제한 우회
        fg_hwnd = GetForegroundWindow()
        fg_tid = wintypes.DWORD(0)
        cur_tid = kernel32.GetCurrentThreadId()
        if fg_hwnd:
            GetWindowThreadProcessId(fg_hwnd, ctypes.byref(fg_tid))
            if fg_tid.value:
                AttachThreadInput(fg_tid.value, cur_tid, True)

        # 3) TopMost → NotTopMost 토글로 Z-order 끌어올림
        SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
        SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)

        # 4) 활성/포커스 부여
        SetForegroundWindow(hwnd)
        SetActiveWindow(hwnd)
        SetFocus(hwnd)

        # 5) 입력 연결 해제
        if fg_hwnd and fg_tid.value:
            AttachThreadInput(fg_tid.value, cur_tid, False)

        # 6) 마지막 안전장치: 작업표시줄 깜빡임
        f = FLASHWINFO(ctypes.sizeof(FLASHWINFO), hwnd, FLASHW_TRAY, 3, 0)
        FlashWindowEx(ctypes.byref(f))
    except Exception:
        pass


def _acquire_single_instance(name: str, lockfile_path: str):
    """
    QLockFile로 단일 인스턴스 보장.
      - tryLock 실패 시 removeStaleLockFile() 후 재시도
      - 실패하면 기존 인스턴스로 'activate' 신호 전송 후 False 반환
      - 성공하면 QLocalServer로 'pid' 먼저 송신 → 클라이언트가 AllowSetForegroundWindow(pid) 호출 후 'activate' 송신
    반환: (locked: bool, server: QLocalServer|None, lock: QLockFile|None)
    """
    lock = QLockFile(lockfile_path)
    lock.setStaleLockTime(10_000)

    if not lock.tryLock(1):
        lock.removeStaleLockFile()
        if not lock.tryLock(1):
            _send_activate_signal(name)
            return False, None, None

    server = QLocalServer()
    QLocalServer.removeServer(name)
    server.listen(name)
    return True, server, lock


def main() -> int:
    app = QApplication(sys.argv)

    # 단일 인스턴스 확보
    lock_path = os.path.join(_temp_dir(), LOCKFILE_NAME)
    locked, server, lock = _acquire_single_instance(APP_UNIQUE_NAME, lock_path)
    if not locked:
        # 새 인스턴스 쪽에서만 안내 메시지 표시 (기존 인스턴스는 알림 표시 X)
        ko = (QLocale.system().language() == QLocale.Korean)
        QMessageBox.information(
            None,
            "실행 중" if ko else "Already Running",
            "Apex GIF Maker가 이미 실행 중입니다.\n기존 창을 앞으로 가져왔습니다."
            if ko else "Apex GIF Maker is already running.\nBrought the existing window to the front."
        )
        return 0

    # 메인 윈도우
    w = MainWindow()
    w.show()

    # 클라이언트 연결 시: PID 먼저 송신 → 클라이언트가 포커스 권한 부여 후 activate 수신 → 창 전면화
    if server is not None:
        def _on_new_conn():
            while server.hasPendingConnections():
                sock = server.nextPendingConnection()
                try:
                    # 1) 먼저 PID 송신
                    pid_payload = f"pid:{os.getpid()}".encode()
                    sock.write(pid_payload)
                    sock.flush()
                    sock.waitForBytesWritten(300)

                    # 2) 클라이언트의 activate 수신 대기
                    sock.waitForReadyRead(1200)
                    _ = bytes(sock.readAll() or b"")

                    # 3) ack
                    sock.write(b"ok")
                    sock.flush()
                    sock.waitForBytesWritten(200)
                    sock.close()
                except Exception:
                    pass

            # 창 활성화(기존 인스턴스 쪽 알림 팝업은 더 이상 띄우지 않음)
            _bring_to_front(w)

        server.newConnection.connect(_on_new_conn)

    try:
        return app.exec()
    finally:
        # 종료 정리
        if server is not None:
            try:
                server.close()
                QLocalServer.removeServer(APP_UNIQUE_NAME)
            except Exception:
                pass
        if lock is not None:
            try:
                lock.unlock()
            except Exception:
                pass


if __name__ == "__main__":
    sys.exit(main())
