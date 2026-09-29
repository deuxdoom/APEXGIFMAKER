# workers.py
"""백그라운드 작업과 Qt 신호를 잇습니다. UI 스레드에서는 ffmpeg·네트워크 작업을 직접 실행하지 않습니다.

작업 스레드에서 보낸 신호는 Qt가 UI 스레드로 넘겨 주므로(queued connection), 받는 쪽은 평범한
슬롯으로 다루면 됩니다.
"""
from __future__ import annotations

import threading
import time
from collections import OrderedDict
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtGui import QImage

from ..core import ffmpeg as ff
from ..core import self_update
from ..core.apply_update import ApplyOptions, apply_update
from ..core.encoder import EncodeCancelled, EncodeError, GifEncoder
from ..core import ffmpeg_setup
from ..core.ffmpeg_setup import SetupCancelled, ensure_ffmpeg
from ..core.updater import UpdateAsset
from ..i18n import tr


def _safe_emit(signal: Any, *args: Any) -> None:
    """앱이 닫히는 중이라 받을 객체가 이미 사라졌으면 조용히 넘어갑니다."""
    try:
        signal.emit(*args)
    except RuntimeError:
        pass


class TaskRunner(QObject):
    """함수를 스레드 풀에서 실행하고 (token, 결과) 또는 (token, 오류 메시지)를 돌려줍니다."""

    finished = Signal(object, object)
    failed = Signal(object, str)

    def __init__(self, workers: int = 2, parent: QObject | None = None):
        super().__init__(parent)
        self._pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="apex-task")
        # 앱을 닫을 때 켜집니다. 오래 걸리는 작업(구간 재생 클립)은 이 신호로 ffmpeg를 멈춥니다.
        self.stop = threading.Event()

    def submit(self, token: object, fn: Callable[..., Any], *args: Any) -> Future | None:
        """닫은 뒤에 들어온 요청은 무시하고 None을 돌려줍니다."""
        if self.stop.is_set():
            return None
        future = self._pool.submit(fn, *args)
        future.add_done_callback(lambda f, t=token: self._done(t, f))
        return future

    def _done(self, token: object, future: Future) -> None:
        if future.cancelled() or self.stop.is_set():
            return
        error = future.exception()
        if error is not None:
            _safe_emit(self.failed, token, str(error) or error.__class__.__name__)
        else:
            _safe_emit(self.finished, token, future.result())

    def shutdown(self) -> None:
        self.stop.set()
        self._pool.shutdown(wait=False, cancel_futures=True)


class FrameLoader(QObject):
    """프리뷰 프레임을 슬롯('start'/'end')마다 하나씩만 추출합니다.

    추출 중에 들어온 요청은 마지막 것만 남겨 두었다가 이어서 처리합니다. 그래서 핸들을 끄는 동안에도
    ffmpeg가 쌓이지 않고, 손을 놓으면 마지막 위치의 프레임이 반드시 표시됩니다.
    앱을 닫으면(shutdown) 추출 중인 ffmpeg도 멈춰서, 창이 닫힌 뒤 프로세스가 남지 않게 합니다.
    """

    frameReady = Signal(str, float, QImage)
    frameFailed = Signal(str, float, str)
    _done = Signal(str, float, int, object, object, str)

    MAX_W, MAX_H = 1280, 720
    CACHE_SIZE = 48

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="apex-frame")
        self._busy: dict[str, bool] = {}
        self._pending: dict[str, float] = {}
        self._cache: OrderedDict[tuple[str, int], bytes] = OrderedDict()
        self._generation = 0
        self._stop = threading.Event()
        self.ffmpeg = ""
        self.path = ""
        self._done.connect(self._on_done)

    def set_source(self, ffmpeg: str, path: str) -> None:
        self.ffmpeg, self.path = ffmpeg, path
        self._generation += 1
        self._pending.clear()

    def request(self, slot: str, t: float) -> None:
        if self._stop.is_set() or not (self.ffmpeg and self.path):
            return
        data = self._cache.get((self.path, round(t * 1000)))
        if data is not None:
            self.frameReady.emit(slot, t, QImage.fromData(data))
            return
        if self._busy.get(slot):
            self._pending[slot] = t
            return
        self._busy[slot] = True
        self._pool.submit(self._work, slot, t, self._generation, self.ffmpeg, self.path)

    def _work(self, slot: str, t: float, generation: int, ffmpeg: str, path: str) -> None:
        try:
            data = ff.grab_frame(ffmpeg, path, t, self.MAX_W, self.MAX_H, cancel=self._stop)
            _safe_emit(self._done, slot, t, generation, QImage.fromData(data), data, "")
        except ff.Cancelled:
            return
        except Exception as exc:
            _safe_emit(self._done, slot, t, generation, None, None, str(exc))

    def _on_done(self, slot: str, t: float, generation: int, image: object, data: object, error: str) -> None:
        self._busy[slot] = False
        if generation == self._generation:
            if isinstance(image, QImage) and not image.isNull() and isinstance(data, bytes):
                self._cache[(self.path, round(t * 1000))] = data
                while len(self._cache) > self.CACHE_SIZE:
                    self._cache.popitem(last=False)
                self.frameReady.emit(slot, t, image)
            else:
                self.frameFailed.emit(slot, t, error)
        pending = self._pending.pop(slot, None)
        if pending is not None:
            self.request(slot, pending)

    def shutdown(self) -> None:
        self._stop.set()
        self._pool.shutdown(wait=False, cancel_futures=True)


class ThumbnailLoader(QObject):
    """타임라인 필름스트립 썸네일을 필요한 시각만 추출합니다.

    화면을 옮기거나 확대해서 더는 보이지 않는 칸은, 기다리는 요청뿐 아니라 이미 추출 중인 ffmpeg도 멈춥니다.
    그래야 일꾼(3개)이 지난 칸에 묶이지 않고 새로 보이는 칸을 바로 추출합니다. (키프레임 간격이 긴 영상은
    한 장에 1~2초씩 걸리기도 합니다.)
    """

    thumbnailReady = Signal(int, float, QImage)
    _done = Signal(int, int, object, object)     # (세대, ms, 그림, 그 요청의 취소 신호)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix="apex-thumb")
        self._jobs: dict[int, tuple[Future, threading.Event]] = {}
        self._generation = 0
        self._closed = False
        self._source = ("", "", 90, 16 / 9)
        self._done.connect(self._on_done)

    @property
    def generation(self) -> int:
        return self._generation

    def set_source(self, ffmpeg: str, path: str, height: int, aspect: float) -> int:
        self._generation += 1
        self._cancel_all()
        self._source = (ffmpeg, path, height, aspect)
        return self._generation

    def _cancel_all(self) -> None:
        for future, cancel in self._jobs.values():
            cancel.set()
            future.cancel()
        self._jobs.clear()

    def request(self, times: list[float]) -> None:
        ffmpeg, path, _height, _aspect = self._source
        if self._closed or not (ffmpeg and path):
            return
        wanted = [round(t * 1000) for t in times]
        wanted_set = set(wanted)
        for ms in [ms for ms in self._jobs if ms not in wanted_set]:
            future, cancel = self._jobs.pop(ms)
            cancel.set()
            future.cancel()
        for ms in wanted:
            if ms not in self._jobs:
                cancel = threading.Event()
                future = self._pool.submit(self._work, self._generation, ms, self._source, cancel)
                self._jobs[ms] = (future, cancel)

    def _work(self, generation: int, ms: int, source: tuple[str, str, int, float], cancel: threading.Event) -> None:
        ffmpeg, path, height, aspect = source
        try:
            width = max(16, int(height * min(max(aspect, 0.5), 2.5)))
            image = QImage.fromData(ff.grab_frame(ffmpeg, path, ms / 1000, width, height, quality=5, cancel=cancel))
        except ff.Cancelled:
            return
        except Exception:
            image = QImage()
        _safe_emit(self._done, generation, ms, image, cancel)

    def _on_done(self, generation: int, ms: int, image: object, cancel: object) -> None:
        job = self._jobs.get(ms)
        if job is not None and job[1] is cancel:    # 같은 시각을 다시 요청한 새 작업은 지우지 않습니다.
            del self._jobs[ms]
        if generation != self._generation or (isinstance(cancel, threading.Event) and cancel.is_set()):
            return
        if isinstance(image, QImage) and not image.isNull():
            self.thumbnailReady.emit(generation, ms / 1000, image)

    def shutdown(self) -> None:
        self._closed = True
        self._cancel_all()
        self._pool.shutdown(wait=False, cancel_futures=True)


class GifJob(QThread):
    """GIF 인코딩을 실행합니다. cancel()은 어느 스레드에서 불러도 ffmpeg를 바로 멈춥니다."""

    stageChanged = Signal(str)
    progressChanged = Signal(float)
    logLine = Signal(str)
    succeeded = Signal(object)
    failed = Signal(str, str)
    cancelled = Signal()

    def __init__(self, encoder: GifEncoder, parent: QObject | None = None):
        super().__init__(parent)
        self.encoder = encoder

    def run(self) -> None:
        try:
            result = self.encoder.run(on_stage=self.stageChanged.emit, on_progress=self.progressChanged.emit,
                                      on_log=self.logLine.emit)
        except EncodeCancelled:
            self.cancelled.emit()
        except EncodeError as exc:
            self.failed.emit(str(exc), exc.details)
        except Exception as exc:
            self.failed.emit(str(exc) or exc.__class__.__name__, "")
        else:
            self.succeeded.emit(result)

    def cancel(self) -> None:
        self.encoder.cancel()


class FfmpegSetupJob(QThread):
    """ffmpeg/ffprobe를 찾고, 없으면 내려받습니다. 끝나면 (ffmpeg, ffprobe, 버전)을 보냅니다."""

    logLine = Signal(str)
    progressChanged = Signal(int)
    done = Signal(str, str, str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._cancel = threading.Event()
        self._last_percent = -1

    def run(self) -> None:
        # ffmpeg를 쓰기 전에(아무것도 실행 중이지 않을 때) 예전 폴더를 옮기고, 받아 둔 새 버전을 적용합니다.
        if ffmpeg_setup.migrate_legacy_dir():
            self.logLine.emit("[INFO] " + tr("log.legacy_ffmpeg"))
        if ffmpeg_setup.apply_staged():
            self.logLine.emit("[OK] " + tr("tools.applied_staged"))
        try:
            ensure_ffmpeg(self.logLine.emit, self._progress, self._cancel)
        except SetupCancelled:
            pass
        except Exception as exc:
            self.logLine.emit(f"[ERR] {exc}")
        ffmpeg_path, ffprobe_path = ff.find_executable("ffmpeg"), ff.find_executable("ffprobe")
        version = ff.ffmpeg_version(ffmpeg_path) if ffmpeg_path else ""
        self.done.emit(ffmpeg_path, ffprobe_path, version)

    def _progress(self, received: int, total: int) -> None:
        percent = int(received * 100 / total) if total else -1
        if percent != self._last_percent:
            self._last_percent = percent
            self.progressChanged.emit(percent)

    def cancel(self) -> None:
        self._cancel.set()


class ToolUpdateJob(QThread):
    """ffmpeg 새 버전을 확인하고, 있으면 받아서 적용합니다. 실행 중이라 바꿀 수 없으면 다음 실행 때 적용합니다.

    결과 상태: latest(이미 최신) | updated(적용함) | staged(다음 실행 때 적용) | unmanaged(시스템 ffmpeg라 건너뜀) | failed
    manual=True(메뉴에서 직접 누름)이면 시스템 ffmpeg를 쓰고 있어도 앱 전용 ffmpeg를 받아 씁니다.
    """

    logLine = Signal(str)
    progressChanged = Signal(int)
    finishedWith = Signal(str, str, str, str)    # (상태, 이전 버전, 최신 버전, 오류)

    def __init__(self, manual: bool, parent: QObject | None = None):
        super().__init__(parent)
        self.manual = manual
        self._cancel = threading.Event()
        self._last_percent = -1

    def run(self) -> None:
        try:
            status = ffmpeg_setup.check_tools()
        except Exception as exc:
            self.finishedWith.emit("failed", "", "", str(exc) or exc.__class__.__name__)
            return
        if status.installed and not status.managed and not self.manual:
            self.finishedWith.emit("unmanaged", status.installed, status.latest, "")
            return
        if not status.newer and (status.managed or not status.installed):
            self.finishedWith.emit("latest", status.installed, status.latest, "")
            return
        try:
            applied = ffmpeg_setup.update_tools(self.logLine.emit, self._progress, self._cancel)
        except SetupCancelled:
            self.finishedWith.emit("failed", status.installed, status.latest, "cancelled")
            return
        except Exception as exc:
            self.finishedWith.emit("failed", status.installed, status.latest, str(exc) or exc.__class__.__name__)
            return
        self.finishedWith.emit("updated" if applied else "staged", status.installed, status.latest, "")

    def _progress(self, received: int, total: int) -> None:
        percent = int(received * 100 / total) if total else -1
        if percent != self._last_percent:
            self._last_percent = percent
            self.progressChanged.emit(percent)

    def cancel(self) -> None:
        self._cancel.set()


class UpdateDownloadJob(QThread):
    """새 버전 ZIP을 받고(크기·SHA-256 검증), 구조를 검사하고, 작업 폴더에 풉니다. 교체는 하지 않습니다."""

    progressChanged = Signal(str, int, int)     # (download|verify|extract, 진행, 전체)
    succeeded = Signal(str)
    failed = Signal(str)
    cancelled = Signal()

    SIGNAL_INTERVAL = 0.1

    def __init__(self, asset: UpdateAsset, work: Path, parent: QObject | None = None):
        super().__init__(parent)
        self.asset = asset
        self.work = work
        self._cancel = threading.Event()
        self._last = 0.0

    def run(self) -> None:
        package = self.work / self_update.PACKAGE_NAME
        try:
            self_update.download_asset(self.asset, package, self._on_download, self._cancel)
            self.progressChanged.emit("verify", 0, 1)
            root = self_update.verify_package(package)
            self_update.extract_payload(package, root, self.work / self_update.NEW_DIR_NAME,
                                        lambda i, n: self._emit("extract", i, n))
            if not self_update.staged_payload_ok(self.work):
                raise self_update.VerificationError("extracted files are incomplete")
            package.unlink(missing_ok=True)
        except self_update.DownloadCancelled:
            self.cancelled.emit()
        except Exception as exc:
            self.failed.emit(str(exc) or exc.__class__.__name__)
        else:
            self.succeeded.emit(str(self.work))

    def _on_download(self, received: int, total: int) -> None:
        self._emit("download", received, total)

    def _emit(self, task: str, done: int, total: int) -> None:
        now = time.monotonic()
        if done >= total or now - self._last >= self.SIGNAL_INTERVAL:
            self._last = now
            self.progressChanged.emit(task, done, total)

    def cancel(self) -> None:
        self._cancel.set()


class ApplyUpdateJob(QThread):
    """적용 모드에서 파일 교체(core.apply_update)를 실행합니다."""

    progressChanged = Signal(int, str, dict)
    completed = Signal(object)

    def __init__(self, options: ApplyOptions, parent: QObject | None = None):
        super().__init__(parent)
        self.options = options

    def run(self) -> None:
        result = apply_update(self.options, lambda percent, stage, detail:
                              self.progressChanged.emit(percent, stage, dict(detail)))
        self.completed.emit(result)
