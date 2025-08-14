# ui.py
from pathlib import Path
from PySide6.QtCore import Qt, QTimer, QUrl, QThread, Signal, QLocale
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QSplitter, QTextEdit, QFileDialog, QMessageBox,
    QHBoxLayout, QLabel, QLineEdit, QPushButton
)
from PySide6.QtGui import QDesktopServices

# ▼▼▼ 수정된 부분 1: 아이콘을 가져오기 위한 import 구문 추가 ▼▼▼
from icon import get_app_icon
# ▲▲▲ 수정 완료 ▲▲▲

from constants import (
    APP_VERSION, APP_DIR, CACHE_DIR,
    DEFAULT_WIDTH, DEFAULT_HEIGHT, DEFAULT_FPS,
    TRIM_MIN_SEC, TRIM_MAX_SEC, RECO_MIN, RECO_MAX, DEFAULT_INIT_SEC,
    LIGHT_QSS, ACCENT_SUB, GOOD_GREEN, WARN_AMBER
)
from i18n import t
from ffmpeg_tools import (
    find_executable, run_quiet, probe_duration_sec, extract_preview_frame,
    build_gif_commands_auto, tidy_ffmpeg_dir, auto_setup_ffmpeg
)
from updater import check_latest

from preview_bar import PreviewBar
from timeline_panel import TimelinePanel
from options_panel import OptionsPanel
from output_panel import OutputPanel

REPO_OWNER = "deuxdoom"
REPO_NAME  = "APEXGIFMAKER"
RELEASES_URL = f"https://github.com/{REPO_OWNER}/{REPO_NAME}/releases/latest"

class _FfmpegPrepareWorker(QThread):
    log = Signal(str)
    done = Signal(str, str)
    def run(self):
        try:
            auto_setup_ffmpeg(lambda s: self.log.emit(s))
        except Exception as e:
            self.log.emit(f"[ERR] ffmpeg 준비 실패: {e}")
        self.done.emit(find_executable("ffmpeg") or "", find_executable("ffprobe") or "")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"APEX GIF MAKER v{APP_VERSION}")
        
        # ▼▼▼ 수정된 부분 2: 생성된 아이콘을 윈도우에 적용하는 코드 추가 ▼▼▼
        # icon.py의 get_app_icon() 함수를 호출하여 QIcon 객체를 가져온 후,
        # setWindowIcon() 메소드를 통해 메인 윈도우의 아이콘으로 설정합니다.
        self.setWindowIcon(get_app_icon())
        # ▲▲▲ 수정 완료 ▲▲▲

        self.resize(1200, 820)
        self.setMinimumSize(1100, 760)

        self.lang = "ko" if QLocale.system().language() == QLocale.Korean else "en"
        self.ffmpeg_path = find_executable("ffmpeg")
        self.ffprobe_path = find_executable("ffprobe")
        self.video_path = ""
        self.duration_sec = 0.0
        self._drag_active = None
        self._drag_span_sec = None
        self._prev_lo_sec = 0.0
        self._prev_hi_sec = 0.0

        self._timeline_timer = QTimer(self)
        self._timeline_timer.setSingleShot(True)
        self._timeline_timer.setInterval(250)
        self._timeline_timer.timeout.connect(self._build_timeline)

        self._build_ui()

        self._prep_worker = None
        QTimer.singleShot(0, self._prepare_tools_async)

        self.preview_timer = QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.setInterval(200)
        self.preview_timer.timeout.connect(self._update_split_preview)

        QTimer.singleShot(1200, lambda: self._check_updates(True))

    def _build_ui(self):
        self.setStyleSheet(LIGHT_QSS)

        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(10, 8, 10, 10)
        root.setSpacing(8)
        self.setCentralWidget(central)

        splitter = QSplitter(Qt.Vertical)
        splitter.setHandleWidth(6)

        self.preview = PreviewBar(self.lang)
        self.preview.playRequested.connect(self._play_range)
        self.preview.startEdited.connect(self._apply_edits_to_range)
        self.preview.endEdited.connect(self._apply_edits_to_range)
        splitter.addWidget(self.preview)

        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        file_row = QHBoxLayout()
        self.le_video = QLineEdit()
        self.le_video.setPlaceholderText("동영상 파일 경로 (mp4 등)")
        self.btn_open = QPushButton("열기…")
        self.btn_open.setObjectName("OpenButton")
        self.btn_open.clicked.connect(self._browse_video)
        file_row.addWidget(QLabel("입력 비디오:"))
        file_row.addWidget(self.le_video, 1)
        file_row.addWidget(self.btn_open)
        lay.addLayout(file_row)

        self.timeline = TimelinePanel()
        self.timeline.range.changed.connect(self._on_range_changed)
        lay.addWidget(self.timeline)

        self.options = OptionsPanel(self.lang)
        self.options.ditherHelp.connect(self._show_dither_help)
        lay.addWidget(self.options)

        self.output = OutputPanel(self.lang)
        self.output.chooseClicked.connect(self._choose_output)
        self.output.generateClicked.connect(self._generate)
        lay.addWidget(self.output)

        self.log = QTextEdit(); self.log.setReadOnly(True); lay.addWidget(self.log, 1)

        splitter.addWidget(content)
        splitter.setSizes([self.height() * 58 // 100, self.height() * 42 // 100])
        root.addWidget(splitter)

        self._apply_language()

    def _apply_language(self):
        tr = lambda k: t(self.lang, k)
        self.options.apply_texts(tr)
        self.output.apply_texts(tr)
        self._update_duration_badge()

    def _msgbox(self, title, text, icon="info", info=None,
                buttons=QMessageBox.Ok, default=QMessageBox.Ok):
        m = QMessageBox(self)
        m.setWindowTitle(title)
        m.setText(text)
        if info:
            m.setInformativeText(info)
        m.setIcon({"info": QMessageBox.Information,
                   "warn": QMessageBox.Warning,
                   "error": QMessageBox.Critical}.get(icon, QMessageBox.NoIcon))
        m.setStandardButtons(buttons)
        m.setDefaultButton(default)
        for role, ko, en in ((QMessageBox.Yes, "예", "Yes"),
                             (QMessageBox.No, "아니오", "No"),
                             (QMessageBox.Ok, "확인", "OK"),
                             (QMessageBox.Cancel, "취소", "Cancel")):
            b = m.button(role)
            if b:
                b.setText(ko if self.lang == "ko" else en)
        m.setStyleSheet("""
            QMessageBox{background:#fff;}
            QLabel{color:#0f172a;}
            QPushButton{border-radius:8px;padding:6px 12px;font-weight:600;background:#fff;color:#0f172a;border:1px solid #cbd5e1;min-width:80px;}
            QPushButton:hover{background:#f1f5f9;}
        """)
        return m.exec()

    def info(self, t1, t2, i=None): return self._msgbox(t1, t2, "info", i)
    def warn(self, t1, t2, i=None): return self._msgbox(t1, t2, "warn", i)
    def error(self, t1, t2, i=None): return self._msgbox(t1, t2, "error", i)
    def ask_yes_no(self, t1, t2, i=None) -> bool:
        return self._msgbox(t1, t2, "info", i,
                            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes) == QMessageBox.Yes

    def _prepare_tools_async(self):
        if getattr(self, "_prep_worker", None) and self._prep_worker.isRunning():
            return
        self._append_log("[INFO] ffmpeg/ffprobe 확인 중…")
        self._prep_worker = _FfmpegPrepareWorker(self)
        self._prep_worker.log.connect(self._append_log)
        self._prep_worker.done.connect(self._on_prepare_done)
        self._prep_worker.start()

    def _on_prepare_done(self, ff, fp):
        self.ffmpeg_path, self.ffprobe_path = ff, fp
        self._append_log(f"[INFO] ffmpeg: {Path(ff).name if ff else '없음'} | ffprobe: {Path(fp).name if fp else '없음'}")

    def _browse_video(self):
        cap = "Videos (*.mp4 *.mov *.mkv *.webm *.avi);;All files (*.*)"
        title = "Open Video" if self.lang == "en" else "비디오 파일 선택"
        path, _ = QFileDialog.getOpenFileName(self, title, "", cap)
        if path:
            self._load_video(path)

    def _load_video(self, path: str):
        p = Path(path)
        if not p.is_file():
            self.warn("오류" if self.lang == "ko" else "Error",
                      "파일이 존재하지 않습니다." if self.lang == "ko" else "File not found")
            return
        if not self.ffprobe_path:
            self._prepare_tools_async()
            self.warn("오류" if self.lang == "ko" else "Error",
                      "ffmpeg/ffprobe 준비가 필요합니다." if self.lang == "ko" else "ffmpeg/ffprobe required")
            return
        try:
            self.le_video.setText(str(p))
            self.duration_sec = probe_duration_sec(self.ffprobe_path, str(p))
            self.video_path = str(p)

            span = min(DEFAULT_INIT_SEC, TRIM_MAX_SEC, self.duration_sec)
            if span < TRIM_MIN_SEC:
                span = min(self.duration_sec, TRIM_MIN_SEC)
            hi = span / max(1e-9, self.duration_sec)
            self.timeline.range.setRange(0.0, hi)

            self._update_time_edits()
            self._build_timeline()
            self._update_split_preview()
            self._update_duration_badge()

            self._append_log(f"[OK] loaded: {p.name}")
        except Exception as e:
            self.error("오류" if self.lang == "ko" else "Error",
                       f"동영상 정보를 읽는 중 문제 발생:\n{e}" if self.lang == "ko" else f"Failed to probe video:\n{e}")

    def _on_range_changed(self, _lo, _hi):
        if self.duration_sec <= 0:
            return
        active = self.timeline.range.active_handle()
        lo = self.timeline.range.lower() * self.duration_sec
        hi = self.timeline.range.upper() * self.duration_sec

        if active and self._drag_active != active:
            self._drag_active = active
            base = (self._prev_hi_sec - self._prev_lo_sec) or (hi - lo)
            self._drag_span_sec = max(TRIM_MIN_SEC, min(TRIM_MAX_SEC, base))

        if active and self._drag_span_sec:
            span = self._drag_span_sec
            if active == 'l':
                new_hi = lo + span
                if new_hi > self.duration_sec:
                    new_hi = self.duration_sec
                    lo = max(0.0, new_hi - span)
                self.timeline.range.setRange(lo/self.duration_sec, new_hi/self.duration_sec, emit_signal=False)
            elif active == 'u':
                new_lo = hi - span
                if new_lo < 0.0:
                    new_lo = 0.0
                    hi = min(self.duration_sec, new_lo + span)
                self.timeline.range.setRange(new_lo/self.duration_sec, hi/self.duration_sec, emit_signal=False)

        self._update_time_edits()
        self._update_duration_badge()
        self.preview_timer.start()

        self._prev_lo_sec = self.timeline.range.lower() * self.duration_sec
        self._prev_hi_sec = self.timeline.range.upper() * self.duration_sec
        if not active:
            self._drag_active = None
            self._drag_span_sec = None

    def _apply_edits_to_range(self):
        if self.duration_sec <= 0:
            return

        def _parse(s: str) -> float:
            s = s.strip()
            if not s: return 0.0
            p = s.split(":")
            if len(p) == 1: return float(s)
            if len(p) == 2: m, x = p; return int(m) * 60 + float(x)
            h, m, x = p; return int(h) * 3600 + int(m) * 60 + float(x)

        try:
            s, e = self.preview.get_times()
            lo, hi = _parse(s), _parse(e)
        except Exception:
            self._update_time_edits()
            return

        lo = max(0.0, min(lo, self.duration_sec))
        hi = max(0.0, min(hi, self.duration_sec))
        if hi <= lo:
            hi = min(self.duration_sec, lo + TRIM_MIN_SEC)

        span = hi - lo
        if span < TRIM_MIN_SEC: hi = min(self.duration_sec, lo + TRIM_MIN_SEC)
        if span > TRIM_MAX_SEC:
            if lo + TRIM_MAX_SEC <= self.duration_sec:
                hi = lo + TRIM_MAX_SEC
            else:
                hi = self.duration_sec
                lo = max(0.0, hi - TRIM_MAX_SEC)

        self.timeline.range.setRange(lo / max(1e-9, self.duration_sec),
                                     hi / max(1e-9, self.duration_sec))
        self._update_duration_badge()
        self.preview_timer.start()

    def _update_time_edits(self):
        def fmt(s: float) -> str:
            h, m, x = int(s // 3600), int((s % 3600) // 60), s % 60
            return f"{h:02d}:{m:02d}:{x:06.3f}" if h else f"{m:02d}:{x:06.3f}"

        lo = self.timeline.range.lower() * self.duration_sec
        hi = self.timeline.range.upper() * self.duration_sec
        self.preview.set_times(fmt(lo), fmt(hi))

    def _update_duration_badge(self):
        if self.duration_sec <= 0:
            self.preview.set_badge("권장 3~6초" if self.lang == "ko" else "Recommend 3–6s")
            self.preview.set_badge_color("#0f172a", ACCENT_SUB)
            return
        lo = self.timeline.range.lower() * self.duration_sec
        hi = self.timeline.range.upper() * self.duration_sec
        span = hi - lo
        text = (f"선택 길이: {span:.3f}초  • 권장 3~6초" if self.lang == "ko"
                else f"Length: {span:.3f}s  • recommend 3–6s")
        color = GOOD_GREEN if (RECO_MIN <= span <= RECO_MAX) else WARN_AMBER
        self.preview.set_badge(text)
        self.preview.set_badge_color(color, ACCENT_SUB)

    def _update_split_preview(self):
        if not (self.video_path and self.ffmpeg_path):
            return
        lo = self.timeline.range.lower() * self.duration_sec
        hi = self.timeline.range.upper() * self.duration_sec
        try:
            p1 = extract_preview_frame(self.ffmpeg_path, self.video_path, lo)
            p2 = extract_preview_frame(self.ffmpeg_path, self.video_path, hi)
            self.preview.set_images(str(p1), str(p2))
        except Exception as e:
            self._append_log(f"[ERR] preview: {e}")

    def _build_timeline(self):
        thumbs = CACHE_DIR / "timeline"
        thumbs.mkdir(parents=True, exist_ok=True)
        for fp in thumbs.glob("thumb_*.png"):
            try: fp.unlink()
            except: pass
        self.timeline.clear_thumbs()
        if not (self.video_path and self.ffmpeg_path and self.duration_sec > 0):
            return

        K = self.timeline.visible_cells()
        fps_val = max(0.01, K / self.duration_sec)
        vf = f"fps={fps_val:.6f},scale=320:-1:flags=lanczos"
        cmd = [self.ffmpeg_path, "-hide_banner", "-loglevel", "error",
               "-i", self.video_path, "-vf", vf, str(thumbs / "thumb_%05d.png")]
        self._append_log("[RUN] thumbs(adaptive): " + " ".join(map(str, cmd)))
        run_quiet(cmd)

        files = sorted(thumbs.glob("thumb_*.png"))
        self.timeline.add_thumb_files(list(files))

    def _play_range(self):
        if not (self.video_path and self.ffmpeg_path):
            self.warn("오류" if self.lang == "ko" else "Error",
                      "먼저 비디오를 불러오세요." if self.lang == "ko" else "Load a video first")
            return
        lo = self.timeline.range.lower() * self.duration_sec
        hi = self.timeline.range.upper() * self.duration_sec
        dur = max(0.0, hi - lo)
        try:
            out = CACHE_DIR / "preview_play.mp4"
            cmd_copy = [self.ffmpeg_path, "-ss", f"{lo:.3f}", "-t", f"{dur:.3f}", "-i", self.video_path,
                        "-c", "copy", "-movflags", "faststart", "-y", "-hide_banner", "-loglevel", "error", str(out)]
            p = run_quiet(cmd_copy)
            if p.returncode != 0 or not out.exists() or out.stat().st_size == 0:
                cmd_enc = [self.ffmpeg_path, "-ss", f"{lo:.3f}", "-t", f"{dur:.3f}", "-i", self.video_path,
                           "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23", "-c:a", "aac", "-b:a", "128k",
                           "-movflags", "faststart", "-y", "-hide_banner", "-loglevel", "error", str(out)]
                p = run_quiet(cmd_enc)
                if p.returncode != 0: raise RuntimeError(p.stderr)
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(out)))
        except Exception as e:
            self.error("실패" if self.lang == "ko" else "Failed", str(e))

    def _choose_output(self):
        name = str(APP_DIR / "output.gif")
        path, _ = QFileDialog.getSaveFileName(self,
                                              "출력 GIF 저장" if self.lang == "ko" else "Save GIF",
                                              name, "GIF (*.gif)")
        if path:
            if not path.lower().endswith(".gif"):
                path += ".gif"
            self.output.set_path(path)

    def _ensure_tools(self) -> bool:
        if not self.ffmpeg_path or not Path(self.ffmpeg_path).exists():
            self._append_log("[ERR] ffmpeg 경로를 찾을 수 없습니다.")
            return False
        if not self.ffprobe_path or not Path(self.ffprobe_path).exists():
            self._append_log("[ERR] ffprobe 경로를 찾을 수 없습니다.")
            return False
        return True

    def _generate(self):
        if not self._ensure_tools():
            self.warn("오류" if self.lang == "ko" else "Error",
                      "ffmpeg/ffprobe 준비가 필요합니다." if self.lang == "ko" else "ffmpeg/ffprobe required")
            return
        if not self.video_path:
            self.warn("오류" if self.lang == "ko" else "Error",
                      "먼저 비디오를 불러오세요." if self.lang == "ko" else "Load a video first")
            return

        lo = self.timeline.range.lower() * self.duration_sec
        hi = self.timeline.range.upper() * self.duration_sec
        duration = max(0.0, hi - lo)
        if not (TRIM_MIN_SEC <= duration <= TRIM_MAX_SEC):
            self.warn("오류" if self.lang == "ko" else "Error",
                      "구간은 1~15초입니다." if self.lang == "ko" else "Range must be 1–15s")
            return

        mode_idx, fps, w, h, scale_mode, dither_key = self.options.values()
        out_path = self.output.get_path()
        if not out_path:
            base = Path(self.video_path).with_suffix("")
            out_path = str(APP_DIR / f"{Path(base).name}_{int(lo*1000)}_{int(hi*1000)}.gif")
            self.output.set_path(out_path)

        alg = "even" if mode_idx == 0 else "mpdecimate"
        cmds = build_gif_commands_auto(
            self.ffmpeg_path, self.video_path, lo, hi, fps, w, h, scale_mode, alg, dither_key, out_path
        )

        self.output.btn_generate.setEnabled(False)
        self._append_log("[RUN] gif start")
        for i, cmd in enumerate(cmds, start=1):
            self._append_log(f"[RUN] pass{i}: {' '.join(map(str, cmd))}")
            p = run_quiet(cmd)
            if p.stdout.strip(): self._append_log(p.stdout.strip())
            if p.stderr.strip(): self._append_log(p.stderr.strip())
            if p.returncode != 0:
                self.error("오류" if self.lang == "ko" else "Error", f"ffmpeg 실패 (pass {i})")
                self.output.btn_generate.setEnabled(True)
                return

        if Path(out_path).is_file():
            self._append_log(f"[OK] saved: {out_path}")
            self.info("완료" if self.lang == "ko" else "Done",
                      ("GIF 생성 완료:\n{}" if self.lang == "ko" else "Saved:\n{}").format(out_path))
        else:
            self._append_log("[ERR] no output")
            self.warn("경고" if self.lang == "ko" else "Warn",
                      "출력 파일을 찾을 수 없습니다." if self.lang == "ko" else "Output not found")

        tidy_ffmpeg_dir(self._append_log)
        self.output.btn_generate.setEnabled(True)

    def _show_dither_help(self):
        if self.lang == "ko":
            self.info("디더링이란?",
                      "GIF는 256색 팔레트를 사용합니다. 디더링은 색 밴딩을 줄이기 위해 작은 패턴/노이즈를 섞는 기법입니다.\n\n"
                      "• 플로이드-슈타인버그: 부드럽고 자연스러움\n• 바이어: 격자 패턴, 선명\n• 없음: 또렷하지만 밴딩 가능")
        else:
            self.info("What is dithering?",
                      "GIF uses a 256-color palette. Dithering mixes small patterns to reduce banding.\n\n"
                      "• floyd_steinberg (smooth)\n• bayer (ordered pattern)\n• none (no dithering; may band)")

    def _check_updates(self, startup=False):
        tag, newer, err = check_latest(REPO_OWNER, REPO_NAME, APP_VERSION)
        if err:
            self._append_log(f"[UPDATE] check failed: {err}")
            return
        if newer:
            self._append_log(f"[UPDATE] new version: {tag}")
            if self.ask_yes_no("업데이트", "새로운 버전이 나왔습니다.\n다운하러 이동하시겠습니까?"):
                QDesktopServices.openUrl(QUrl(RELEASES_URL))
        elif not startup:
            self._append_log("[UPDATE] 최신 상태")


    def closeEvent(self, e):
        if self.ask_yes_no("종료" if self.lang == "ko" else "Quit",
                           "프로그램을 종료하시겠습니까?" if self.lang == "ko" else "Do you want to exit?"):
            e.accept()
        else:
            e.ignore()

    def _append_log(self, s: str):
        if hasattr(self, "log") and self.log is not None:
            self.log.append(s)
        else:
            print(s)

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self._timeline_timer.start()