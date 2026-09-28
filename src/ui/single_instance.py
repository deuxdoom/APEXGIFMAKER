# single_instance.py
"""프로그램을 하나만 실행되게 합니다.

두 번째로 실행되면 기존 인스턴스에 "앞으로 오기"(또는 열 파일 경로)를 전달하고 끝납니다.
동영상 파일을 exe에 끌어다 놓거나 '연결 프로그램'으로 열어도 이미 떠 있는 창에서 열립니다.

주고받는 형식(한 줄 UTF-8): 서버 → "pid:<pid>", 클라이언트 → "activate" 또는 "open:<경로>", 서버 → "ok"
"""
from __future__ import annotations

import os

from PySide6.QtCore import QLockFile, QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from ..core import config
from . import win32

SERVER_NAME = "ApexGifMaker_v3_localserver"
LOCK_NAME = "ApexGifMaker_v3.lock"


def send_to_running(message: str) -> bool:
    """이미 실행 중인 인스턴스에 메시지를 보냅니다. 받는 쪽이 없으면 False입니다."""
    sock = QLocalSocket()
    sock.connectToServer(SERVER_NAME)
    if not sock.waitForConnected(800):
        sock.abort()
        return False
    try:
        if sock.waitForReadyRead(1000):
            raw = bytes(sock.readAll().data()).decode("utf-8", "replace").strip()
            if raw.startswith("pid:"):
                try:
                    win32.allow_set_foreground(int(raw[4:]))
                except ValueError:
                    pass
        sock.write((message + "\n").encode("utf-8"))
        sock.flush()
        sock.waitForBytesWritten(1000)
        sock.waitForReadyRead(1000)
    finally:
        sock.disconnectFromServer()
    return True


class SingleInstance(QObject):
    """잠금 파일과 로컬 서버로 단일 실행을 보장합니다."""

    activateRequested = Signal()
    openRequested = Signal(str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._lock = QLockFile(str(config.temp_dir() / LOCK_NAME))
        self._lock.setStaleLockTime(10_000)
        self._server: QLocalServer | None = None

    def acquire(self) -> bool:
        if not self._lock.tryLock(1):
            self._lock.removeStaleLockFile()
            if not self._lock.tryLock(1):
                return False
        QLocalServer.removeServer(SERVER_NAME)
        server = QLocalServer(self)
        server.newConnection.connect(self._on_connection)
        server.listen(SERVER_NAME)
        self._server = server
        return True

    def release(self) -> None:
        if self._server is not None:
            self._server.close()
            QLocalServer.removeServer(SERVER_NAME)
            self._server = None
        self._lock.unlock()

    def _on_connection(self) -> None:
        server = self._server
        while server is not None and server.hasPendingConnections():
            sock = server.nextPendingConnection()
            if sock is None:
                continue
            sock.write(f"pid:{os.getpid()}\n".encode("utf-8"))
            sock.flush()
            sock.readyRead.connect(lambda s=sock: self._on_message(s))
            sock.disconnected.connect(sock.deleteLater)

    def _on_message(self, sock: QLocalSocket) -> None:
        text = bytes(sock.readAll().data()).decode("utf-8", "replace").strip()
        sock.write(b"ok\n")
        sock.flush()
        if text.startswith("open:") and len(text) > 5:
            self.openRequested.emit(text[5:])
        self.activateRequested.emit()
