# main_window.py
"""메인 창: 부품 위젯을 배치하고, 동영상 열기·프리뷰·GIF 생성·설정 저장 흐름을 잇습니다.

무거운 작업(ffprobe, 프레임 추출, 인코딩, 다운로드)은 모두 workers.py의 스레드에서 실행합니다.
업데이트 흐름은 update_flow.py, 설정 메뉴는 menus.py에 있습니다.
"""
from __future__ import annotations

import tempfile
import time
from pathlib import Path

from PySide6.QtCore import QRect, QTimer, QUrl
from PySide6.QtGui import (QAction, QCloseEvent, QDesktopServices, QDragEnterEvent, QDragLeaveEvent, QDropEvent,
                           QImage, QKeySequence, QShortcut, QShowEvent)
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QVBoxLayout, QWidget

from ..core import config
from ..core import ffmpeg as ff
from ..core.encoder import EncodeResult, GifEncoder
from ..core.gif import suggest_filename
from ..core.settings import Settings, cleanup_legacy_cache, save_settings
from ..core.timecode import format_time
from ..i18n import tr
from . import dialogs, theme, win32
from .app_icon import app_icon
from .frame import ShadowShell, WindowFrame, extra_size, handle_system_command, make_frameless, run_dialog
from .menus import build_settings_menu
from .result_dialog import ResultDialog, format_size
from .titlebar import TitleBar
from .update_flow import UpdateFlow
from .widgets.log_panel import LogPanel
from .widgets.options_panel import OptionsPanel
from .widgets.output_panel import OutputPanel
from .widgets.preview import PreviewArea
from .widgets.timeline_panel import TimelinePanel
from .workers import FfmpegSetupJob, FrameLoader, GifJob, TaskRunner, ThumbnailLoader, ToolUpdateJob

DEFAULT_SIZE = (1280, 860)
MIN_SIZE = (1000, 720)


class MainWindow(QWidget):
    def __init__(self, settings: Settings, *, settings_error: str | None = None, initial_file: str = "",
                 background: bool = True, persist: bool = True):
        """background=False면 ffmpeg 준비·업데이트 확인을 시작하지 않고, persist=False면 설정을 저장하지 않습니다.
        (둘 다 검사·스모크 테스트용)"""
        super().__init__()
        self._persist = persist
        make_frameless(self)
        self.setWindowTitle(f"{config.APP_NAME} v{config.APP_VERSION}")
        self.setWindowIcon(app_icon())
        self.setAcceptDrops(True)
        self.settings = settings
        self.ffmpeg = ff.find_executable("ffmpeg")
        self.ffprobe = ff.find_executable("ffprobe")
        self.ffmpeg_version = ""
        self.video: ff.VideoInfo | None = None
        self._pending_file = initial_file
        self._probe_serial = 0
        self._last_sel = (-1.0, -1.0)
        self._job: GifJob | None = None
        self._setup_job: FfmpegSetupJob | None = None
        self._tool_job: ToolUpdateJob | None = None
        self._background = background
        self._quitting = False
        self._first_show = True
        self.confirm_exit_action: QAction | None = None     # menus.build_settings_menu가 채움

        self.tasks = TaskRunner(2, self)
        self.tasks.finished.connect(self._on_task_done)
        self.tasks.failed.connect(self._on_task_failed)
        self.frames = FrameLoader(self)
        self.frames.frameReady.connect(self._on_frame)
        self.frames.frameFailed.connect(self._on_frame_failed)
        self.thumbs = ThumbnailLoader(self)
        self.thumbs.thumbnailReady.connect(self._on_thumbnail)
        self.updates = UpdateFlow(self)

        self._build()
        self._restore_settings()
        if settings_error:
            self.log(f"[WARN] {tr('log.settings_error', error=settings_error)}")
        if background:
            QTimer.singleShot(0, self._start_ffmpeg_setup)
            QTimer.singleShot(0, self._housekeeping)
            QTimer.singleShot(2500, lambda: self.updates.check(silent=True))

    # ------------------------------------------------------------------ 화면 구성
    def _build(self) -> None:
        self.shell = ShadowShell(resizable=True)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.shell)
        self.frame = WindowFrame(self, self._on_maximized)
        surface = QVBoxLayout(self.shell.surface)
        surface.setContentsMargins(0, 0, 0, 0)
        surface.setSpacing(0)

        self.settings_menu = build_settings_menu(self)
        self.title_bar = TitleBar(self.settings_menu)
        self.title_bar.frame = self.frame
        surface.addWidget(self.title_bar)

        content = QWidget()
        content.setObjectName("Content")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(14, 2, 14, 12)
        layout.setSpacing(10)
        self.preview = PreviewArea()
        layout.addWidget(self.preview, 1)
        self.timeline_panel = TimelinePanel()
        self.timeline = self.timeline_panel.timeline
        layout.addWidget(self.timeline_panel)
        row = QHBoxLayout()
        row.setSpacing(10)
        self.options_panel = OptionsPanel()
        self.output_panel = OutputPanel()
        row.addWidget(self.options_panel, 3)
        row.addWidget(self.output_panel, 2)
        layout.addLayout(row)
        self.log_panel = LogPanel()
        layout.addWidget(self.log_panel)
        surface.addWidget(content, 1)
        self.shell.raise_grips()

        bar = self.title_bar
        bar.openRequested.connect(self.browse_video)
        bar.aboutRequested.connect(self.show_about)
        bar.minimizeRequested.connect(self.showMinimized)
        bar.maximizeRequested.connect(self.frame.toggle)
        bar.closeRequested.connect(self.close)
        self.preview.openRequested.connect(self.browse_video)
        self.timeline_panel.playRequested.connect(self.play_range)
        self.timeline.selectionChanged.connect(self._on_selection_changed)
        self.timeline.thumbnailsNeeded.connect(self.thumbs.request)
        self.options_panel.changed.connect(self._on_options_changed)
        self.options_panel.helpRequested.connect(
            lambda: dialogs.info(self, tr("options.dither.help_text"), tr("options.dither.help")))
        self.output_panel.generateRequested.connect(self.generate)
        self.output_panel.cancelRequested.connect(self.cancel_generate)
        self.output_panel.chooseFolderRequested.connect(self.choose_folder)
        self.output_panel.openFolderRequested.connect(self.open_output_folder)
        for keys, slot in (("Ctrl+O", self.browse_video), ("Ctrl+Return", self.generate),
                           ("Ctrl+Enter", self.generate), ("Ctrl+P", self.play_range)):
            QShortcut(QKeySequence(keys), self).activated.connect(slot)

        extra_w, extra_h = extra_size()
        self.setMinimumSize(MIN_SIZE[0] + extra_w, MIN_SIZE[1] + extra_h)
        self._update_ready_state()
        self._on_options_changed()

    def _on_maximized(self, maximized: bool) -> None:
        self.shell.set_maximized(maximized)
        self.title_bar.set_maximized(maximized)

    def log(self, text: str) -> None:
        self.log_panel.append(text)

    def _update_ready_state(self) -> None:
        ready = self.video is not None and bool(self.ffmpeg)
        self.output_panel.set_ready(ready)
        self.timeline_panel.play_button.setEnabled(ready)

    # ------------------------------------------------------------------ 설정
    def _restore_settings(self) -> None:
        s = self.settings
        self.options_panel.set_options(s.options)
        self.output_panel.set_folder(s.output_dir)
        self.log_panel.set_expanded(s.log_expanded)
        extra_w, extra_h = extra_size()
        rect = _parse_rect(s.window_geometry)
        screen = self.screen()
        if rect is not None and screen is not None and any(
                sc.availableGeometry().intersects(rect) for sc in screen.virtualSiblings()):
            self.setGeometry(rect)
        else:
            self.resize(DEFAULT_SIZE[0] + extra_w, DEFAULT_SIZE[1] + extra_h)
            if screen is not None:
                area = screen.availableGeometry()
                self.move(area.center().x() - self.width() // 2, area.center().y() - self.height() // 2)

    def _save_settings(self) -> None:
        s = self.settings
        s.options = self.options_panel.options()
        s.output_dir = self.output_panel.folder()
        s.log_expanded = self.log_panel.expanded()
        normal = self.frame.normal_geometry()
        s.window_geometry = f"{normal.x()},{normal.y()},{normal.width()},{normal.height()}"
        s.window_maximized = self.frame.is_maximized()
        try:
            save_settings(s)
        except OSError as exc:
            self.log(f"[WARN] {tr('log.settings_save_error', error=exc)}")

    def set_theme(self, mode: str) -> None:
        self.settings.theme = mode
        theme.manager().apply(mode)

    def set_language(self, code: str) -> None:
        if code != self.settings.language:
            self.settings.language = code
            dialogs.info(self, tr("lang.restart"))

    def set_confirm_exit(self, value: bool) -> None:
        self.settings.confirm_exit = value

    def show_about(self) -> None:
        dialog = dialogs.AboutDialog(self, self.ffmpeg_version)
        dialog.checkUpdateRequested.connect(lambda: self.updates.check(silent=False))
        run_dialog(dialog)

    def _housekeeping(self) -> None:
        self.tasks.submit(("cleanup",), cleanup_legacy_cache)
        self.updates.report_previous_result()

    # ------------------------------------------------------------------ ffmpeg 준비
    def _start_ffmpeg_setup(self) -> None:
        if self._setup_job is not None and self._setup_job.isRunning():
            return
        self.log(f"[INFO] {tr('log.ffmpeg_checking')}")
        self.log_panel.set_ffmpeg_status(tr("status.ffmpeg.checking"), "neutral")
        job = FfmpegSetupJob(self)
        job.logLine.connect(self.log)
        job.progressChanged.connect(self._on_ffmpeg_progress)
        job.done.connect(self._on_ffmpeg_ready)
        self._setup_job = job
        job.start()

    def _on_ffmpeg_progress(self, percent: int) -> None:
        if percent >= 0:
            self.log_panel.set_ffmpeg_status(tr("status.ffmpeg.downloading", percent=percent), "accent")
            if percent % 10 == 0:
                self.log(f"[DL] {tr('log.ffmpeg_progress', percent=percent)}")

    def _on_ffmpeg_ready(self, ffmpeg_path: str, ffprobe_path: str, version: str) -> None:
        self.ffmpeg, self.ffprobe, self.ffmpeg_version = ffmpeg_path, ffprobe_path, version
        if ffmpeg_path and ffprobe_path:
            self.log_panel.set_ffmpeg_status(tr("status.ffmpeg.ready", version=ff.short_version(version) or "?"),
                                             "success")
            self.log(f"[INFO] {tr('log.ffmpeg_ready', ffmpeg=ffmpeg_path, ffprobe=ffprobe_path)}")
            if self._pending_file:
                path, self._pending_file = self._pending_file, ""
                self.open_video(path)
            if self.settings.auto_update_tools and self._background:
                QTimer.singleShot(4000, lambda: self.update_tools(manual=False))
        else:
            self.log_panel.set_ffmpeg_status(tr("status.ffmpeg.missing"), "danger")
            dialogs.error(self, tr("msg.ffmpeg_failed", path=str(config.tools_dir())))
        self._update_ready_state()

    # ------------------------------------------------------------------ 도구(ffmpeg) 업데이트
    def update_tools(self, manual: bool = True) -> None:
        """ffmpeg 새 버전을 확인해서 받습니다. manual=False(켤 때 자동)면 결과를 로그로만 알립니다."""
        if self._tool_job is not None and self._tool_job.isRunning():
            return
        if manual:
            self.log_panel.set_ffmpeg_status(tr("tools.checking"), "accent")
        self.log(f"[INFO] {tr('tools.checking')}")
        job = ToolUpdateJob(manual, self)
        job.logLine.connect(self.log)
        job.progressChanged.connect(self._on_tools_progress)
        job.finishedWith.connect(lambda *result, m=manual: self._on_tools_done(m, *result))
        self._tool_job = job
        job.start()

    def _on_tools_progress(self, percent: int) -> None:
        if percent >= 0:
            self.log_panel.set_ffmpeg_status(tr("status.ffmpeg.updating", percent=percent), "accent")

    def _on_tools_done(self, manual: bool, status: str, old: str, new: str, error: str) -> None:
        self._tool_job = None
        self.ffmpeg = ff.find_executable("ffmpeg") or self.ffmpeg
        self.ffprobe = ff.find_executable("ffprobe") or self.ffprobe
        self.ffmpeg_version = ff.ffmpeg_version(self.ffmpeg) if self.ffmpeg else ""
        version = ff.short_version(self.ffmpeg_version) or "?"
        self.log_panel.set_ffmpeg_status(tr("status.ffmpeg.ready", version=version), "success")
        messages = {
            "latest": ("info", tr("tools.latest", version=version)),
            "updated": ("success", tr("tools.updated", old=old or "?", new=new)),
            "staged": ("info", tr("tools.staged", new=new)),
            "unmanaged": ("info", tr("tools.unmanaged")),
            "failed": ("error", tr("tools.failed", error=error)),
        }
        kind, text = messages.get(status, messages["failed"])
        self.log(f"[{'ERR' if kind == 'error' else 'INFO'}] {text}")
        if status == "failed":
            self.log_panel.set_ffmpeg_status(tr("status.ffmpeg.ready", version=version), "warning")
        if manual and not self._quitting:
            if kind == "error":
                dialogs.error(self, text, tr("tools.title"))
            else:
                dialogs.info(self, text, tr("tools.title"), kind=kind)

    def set_auto_update_tools(self, value: bool) -> None:
        self.settings.auto_update_tools = value

    # ------------------------------------------------------------------ 동영상 열기
    def browse_video(self) -> None:
        patterns = " ".join(f"*{ext}" for ext in config.VIDEO_EXTENSIONS)
        path, _ = QFileDialog.getOpenFileName(self, tr("top.open_dialog"), self.settings.last_open_dir,
                                              tr("top.video_filter", patterns=patterns))
        if path:
            self.open_video(path)

    def open_video(self, path: str) -> None:
        if self._job is not None:
            return
        file = Path(path)
        if not file.is_file():
            dialogs.error(self, tr("msg.file_missing", path=path))
            return
        if not self.ffprobe:
            self._pending_file = str(file)
            dialogs.info(self, tr("msg.ffmpeg_not_ready"))
            return
        self.settings.last_open_dir = str(file.parent)
        self._probe_serial += 1
        self.log_panel.last_line.setText(tr("status.loading_video"))
        self.tasks.submit(("probe", self._probe_serial), ff.probe_video, self.ffprobe, str(file))

    def _on_probed(self, info: ff.VideoInfo) -> None:
        self.video = info
        self._last_sel = (-1.0, -1.0)
        self.frames.set_source(self.ffmpeg, info.path)
        self.thumbs.set_source(self.ffmpeg, info.path, self.timeline.thumb_height(), info.aspect)
        self.preview.show_frames(True)
        meta = _video_meta(info)
        self.title_bar.set_video(Path(info.path).name, meta)
        self.timeline_panel.set_video_loaded(True)
        self.output_panel.reset_name("")
        self.timeline.set_video(info.duration, info.aspect, info.frame_step)
        self._on_options_changed()
        self._update_ready_state()
        self.log(f"[OK] {tr('log.video_loaded', name=Path(info.path).name, info=meta)}")

    def _on_selection_changed(self, start: float, end: float) -> None:
        video = self.video
        if video is None:
            return
        self.preview.start_pane.set_time(format_time(start))
        self.preview.end_pane.set_time(format_time(end))
        if start != self._last_sel[0]:
            self.preview.start_pane.set_loading(True)
            self.frames.request("start", start)
        if end != self._last_sel[1]:
            self.preview.end_pane.set_loading(True)
            # GIF의 마지막 프레임은 끝 시각 직전 프레임입니다. (영상 끝 이후로는 프레임을 뽑을 수 없음)
            self.frames.request("end", max(start, min(end, video.duration) - video.frame_step))
        self._last_sel = (start, end)
        self.output_panel.set_auto_name(suggest_filename(video.path, start, end))

    def _on_frame(self, slot: str, _t: float, image: QImage) -> None:
        self.preview.pane(slot).set_image(image)

    def _on_frame_failed(self, slot: str, t: float, error: str) -> None:
        self.preview.pane(slot).set_error()
        self.log(f"[WARN] {tr('log.frame_failed', time=format_time(t), error=error)}")

    def _on_thumbnail(self, generation: int, t: float, image: QImage) -> None:
        if generation == self.thumbs.generation:
            self.timeline.add_thumbnail(t, image)

    def _on_options_changed(self) -> None:
        opts = self.options_panel.options()
        self.preview.set_guide(opts.aspect if opts.scale_mode == "cover" else None)
        self.timeline_panel.set_frame_settings(opts.fps, opts.frame_mode == "dedupe")

    # ------------------------------------------------------------------ 백그라운드 작업 결과
    def _on_task_done(self, token: object, result: object) -> None:
        kind = token[0] if isinstance(token, tuple) else token
        if kind == "probe" and isinstance(token, tuple) and token[1] == self._probe_serial:
            if isinstance(result, ff.VideoInfo):
                self._on_probed(result)
        elif kind == "clip":
            self.timeline_panel.play_button.setEnabled(self.video is not None)
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(result)))
        elif kind == "cleanup" and result:
            self.log(f"[INFO] {tr('log.legacy_cache', items=', '.join(map(str, result)))}")  # type: ignore[arg-type]
        elif kind == "update" and isinstance(token, tuple):
            self.updates.on_result(bool(token[1]), result)

    def _on_task_failed(self, token: object, message: str) -> None:
        kind = token[0] if isinstance(token, tuple) else token
        if kind == "probe" and isinstance(token, tuple) and token[1] == self._probe_serial:
            self.log(f"[ERR] {tr('msg.probe_failed', error=message)}")
            dialogs.error(self, tr("msg.probe_failed", error=message))
        elif kind == "clip":
            self._update_ready_state()
            self.log(f"[ERR] {tr('log.clip_failed', error=message)}")
            dialogs.error(self, tr("msg.clip_failed", error=message))
        elif kind == "update" and isinstance(token, tuple):
            self.updates.on_error(bool(token[1]), message)

    # ------------------------------------------------------------------ 구간 재생
    def play_range(self) -> None:
        if self.video is None or not self.ffmpeg:
            return
        sel = self.timeline.selection()
        self.timeline_panel.play_button.setEnabled(False)
        self.log_panel.last_line.setText(tr("status.exporting_clip"))
        self.tasks.submit(("clip",), _export_clip, self.ffmpeg, self.video.path, sel.start, sel.length)

    # ------------------------------------------------------------------ GIF 생성
    def choose_folder(self) -> None:
        start = self.output_panel.folder() or str(config.APP_DIR)
        folder = QFileDialog.getExistingDirectory(self, tr("output.folder.choose"), start)
        if folder:
            self.output_panel.set_folder(folder)

    def open_output_folder(self) -> None:
        folder = Path(self.output_panel.folder() or config.APP_DIR)
        folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def generate(self) -> None:
        if self._job is not None:
            return
        video = self.video
        if video is None:
            dialogs.warn(self, tr("msg.load_video_first"))
            return
        if not (self.ffmpeg and Path(self.ffmpeg).is_file()):
            dialogs.warn(self, tr("msg.ffmpeg_not_ready"))
            return
        name, bad = self.output_panel.filename(), self.output_panel.invalid_chars()
        if not name or bad:
            dialogs.warn(self, tr("msg.invalid_filename", chars=bad or "∅"))
            return
        folder = Path(self.output_panel.folder() or config.APP_DIR)
        if not _writable(folder):
            dialogs.warn(self, tr("msg.folder_unwritable", path=str(folder)))
            return
        target = folder / name
        if target.exists():
            confirmed, _ = dialogs.ask(self, tr("msg.overwrite", name=name), tr("msg.overwrite.title"), danger=True)
            if not confirmed:
                return
        sel = self.timeline.selection()
        encoder = GifEncoder(self.ffmpeg, video.path, sel.start, sel.end, self.options_panel.options(), target)
        job = GifJob(encoder, self)
        job.stageChanged.connect(self._on_gif_stage)
        job.progressChanged.connect(self._on_gif_progress)
        job.logLine.connect(self.log)
        job.succeeded.connect(self._on_gif_done)
        job.failed.connect(self._on_gif_failed)
        job.cancelled.connect(self._on_gif_cancelled)
        job.finished.connect(job.deleteLater)
        self._job = job
        self.output_panel.set_busy(True)
        self.timeline_panel.play_button.setEnabled(False)
        self.log_panel.last_line.setText(tr("status.generating"))
        job.start()

    def cancel_generate(self) -> None:
        if self._job is not None:
            self._job.cancel()

    def _on_gif_stage(self, stage: str) -> None:
        if stage == "palette":
            self.output_panel.set_stage(tr("output.stage.palette"), None)
        else:
            self.output_panel.set_stage(tr("output.stage.encode", percent=0), 0.0)

    def _on_gif_progress(self, fraction: float) -> None:
        self.output_panel.set_stage(tr("output.stage.encode", percent=int(fraction * 100)), fraction)

    def _finish_job(self) -> None:
        self._job = None
        self.output_panel.set_busy(False)
        self._update_ready_state()

    def _on_gif_done(self, result: object) -> None:
        self._finish_job()
        if not isinstance(result, EncodeResult):
            return
        size = Path(result.path).stat().st_size if Path(result.path).exists() else 0
        details = [format_size(size)]
        if result.info is not None:
            details += [f"{result.info.width}×{result.info.height}", tr("unit.frames", value=result.info.frames),
                        tr("unit.seconds", value=f"{result.info.duration_ms / 1000:.2f}")]
        self.log(f"[OK] {tr('log.gif_saved', path=result.path, details=', '.join(details))}")
        self.log_panel.last_line.setText(tr("status.done", name=Path(result.path).name))
        if not self._quitting:
            run_dialog(ResultDialog(self, result))

    def _on_gif_failed(self, message: str, details: str) -> None:
        self._finish_job()
        self.log(f"[ERR] {tr('log.gif_failed', error=message)}")
        if details:
            self.log(details)
        if not self._quitting:
            dialogs.error(self, tr("msg.gif_failed", error=message))

    def _on_gif_cancelled(self) -> None:
        self._finish_job()
        self.log(f"[INFO] {tr('log.gif_cancelled')}")
        self.log_panel.last_line.setText(tr("status.cancelled"))

    # ------------------------------------------------------------------ 창 이벤트
    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        if self._first_show:
            self._first_show = False
            win32.enable_taskbar_minimize(self)
            if self.settings.window_maximized:
                QTimer.singleShot(0, self.frame.maximize)

    def nativeEvent(self, eventType, message) -> object:  # noqa: N802 - Qt 이름 그대로
        if handle_system_command(self.frame, int(message)):
            return True, 0
        return super().nativeEvent(eventType, message)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if _first_local_file(event.mimeData().urls()):
            event.acceptProposedAction()
            self.preview.set_drop_active(True)

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        self.preview.set_drop_active(False)

    def dropEvent(self, event: QDropEvent) -> None:
        self.preview.set_drop_active(False)
        path = _first_local_file(event.mimeData().urls())
        if path:
            event.acceptProposedAction()
            self.open_video(path)

    def quit_for_update(self) -> None:
        """업데이트 적용 창을 띄운 뒤 묻지 않고 종료합니다."""
        self._quitting = True
        self.close()

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self._quitting:
            if self._job is not None:
                confirmed, _ = dialogs.ask(self, tr("msg.quit.busy"), tr("msg.quit.title"), danger=True)
                if not confirmed:
                    event.ignore()
                    return
            elif self.settings.confirm_exit:
                confirmed, dont_ask = dialogs.ask(self, tr("msg.quit"), tr("msg.quit.title"),
                                                  checkbox=tr("msg.dont_ask"))
                if not confirmed:
                    event.ignore()
                    return
                if dont_ask:
                    self.settings.confirm_exit = False
                    if self.confirm_exit_action is not None:
                        self.confirm_exit_action.setChecked(False)
        self._quitting = True
        if self._job is not None:
            self._job.cancel()
            self._job.wait(3000)
        for tool_job in (self._setup_job, self._tool_job):
            if tool_job is not None and tool_job.isRunning():
                tool_job.cancel()
                tool_job.wait(3000)
        if self._persist:
            self._save_settings()
        for worker in (self.tasks, self.frames, self.thumbs):
            worker.shutdown()
        event.accept()


# ---------------------------------------------------------------------- 도우미
def _parse_rect(text: str) -> QRect | None:
    try:
        x, y, w, h = (int(part) for part in text.split(","))
    except ValueError:
        return None
    return QRect(x, y, w, h) if w > 200 and h > 200 else None


def _video_meta(info: ff.VideoInfo) -> str:
    parts = []
    if info.width and info.height:
        parts.append(f"{info.width}×{info.height}")
    if info.fps:
        parts.append(f"{info.fps:.3g} fps")
    parts.append(format_time(info.duration))
    if info.codec:
        parts.append(info.codec)
    return " · ".join(parts)


def _first_local_file(urls: list[QUrl]) -> str:
    for url in urls:
        if url.isLocalFile() and Path(url.toLocalFile()).is_file():
            return url.toLocalFile()
    return ""


def _writable(folder: Path) -> bool:
    try:
        folder.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryFile(dir=folder):
            pass
        return True
    except OSError:
        return False


def _export_clip(ffmpeg: str, source: str, start: float, length: float) -> str:
    """구간 재생용 MP4를 임시 폴더에 만듭니다. 재생 중인 이전 파일과 겹치지 않도록 이름에 시각을 붙입니다."""
    folder = config.temp_dir() / "clips"
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob("clip-*.mp4"):
        try:
            old.unlink()
        except OSError:
            pass
    target = folder / f"clip-{int(time.time() * 1000)}.mp4"
    proc = ff.export_clip(ffmpeg, source, start, length, target)
    if proc.returncode != 0 or not target.is_file():
        raise RuntimeError(proc.stderr.strip() or f"ffmpeg exited with code {proc.returncode}")
    return str(target)
