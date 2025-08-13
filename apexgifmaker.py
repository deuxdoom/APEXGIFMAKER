#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apex GIF Maker (MP4 → GIF segment), PySide6 + ffmpeg
Author: ChatGPT (꾸라)

v4:
- 시작/끝 시간을 직접 입력 가능(hh:mm:ss.mmm). 슬라이더와 양방향 동기화(2~10초 강제).
- 기본 저장 폴더 = 실행 파일 경로(APP_DIR).
- 스케일 모드 추가: 레터박스(비율 유지), 꽉 채우기(크롭, 비율 유지), 스트레치(왜곡).
- 프리뷰는 1280x720로 추출하고, 큰 영역(최소 높이 420px)에 표시.
- 캐시: ./cache, ffmpeg-bin: ./ffmpeg-bin (영구).
"""

import os
import sys
import shutil
import subprocess
import platform
import urllib.request
import zipfile
import tarfile
from pathlib import Path

from PySide6.QtCore import Qt, QSize, QRect, QThread, Signal
from PySide6.QtGui import QAction, QPixmap, QPainter, QColor
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFileDialog, QMessageBox,
    QLabel, QLineEdit, QSpinBox, QComboBox, QPushButton,
    QGroupBox, QGridLayout, QVBoxLayout, QHBoxLayout, QTextEdit,
    QListWidget, QListWidgetItem, QListView
)

APP_TITLE = "Apex GIF Maker (MP4 → GIF)"
DEFAULT_WIDTH = 160
DEFAULT_HEIGHT = 80
DEFAULT_FPS = 12
TRIM_MIN_SEC = 2.0
TRIM_MAX_SEC = 10.0

# ---------- Paths ----------
def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent

APP_DIR = app_root()
CACHE_DIR = APP_DIR / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
FFMPEG_DIR = APP_DIR / "ffmpeg-bin"
FFMPEG_DIR.mkdir(parents=True, exist_ok=True)

def find_executable(name: str) -> str:
    local = FFMPEG_DIR / (name + (".exe" if os.name == "nt" else ""))
    if local.exists():
        return str(local)
    return shutil.which(name) or ""

# ---------- Time utils ----------
def hhmmss_to_seconds(text: str) -> float:
    text = text.strip()
    if not text:
        return 0.0
    parts = text.split(":")
    if len(parts) == 1:
        return float(parts[0])
    if len(parts) == 2:
        m, s = parts
        return int(m) * 60 + float(s)
    if len(parts) == 3:
        h, m, s = parts
        return int(h) * 3600 + int(m) * 60 + float(s)
    raise ValueError("시간 형식 오류")

def seconds_to_hhmmss(secs: float) -> str:
    if secs < 0: secs = 0
    h = int(secs // 3600)
    m = int((secs % 3600) // 60)
    s = secs % 60
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:06.3f}"
    return f"{m:02d}:{s:06.3f}"

# ---------- ffmpeg helpers ----------
def probe_duration_sec(ffprobe_path: str, video_path: str) -> float:
    cmd = [ffprobe_path, "-v", "error",
           "-show_entries", "format=duration",
           "-of", "default=noprint_wrappers=1:nokey=1",
           video_path]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "ffprobe 실패")
    return float(proc.stdout.strip())

def extract_preview_frame(ffmpeg_path: str, video_path: str, ts: float) -> Path:
    # Always pull a high-res preview (1280x720) for clarity
    w, h = 1280, 720
    out_dir = CACHE_DIR / "previews"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"preview_{abs(hash((video_path, round(ts,3), '1280x720')))}.png"
    cmd = [
        ffmpeg_path, "-hide_banner", "-loglevel", "error",
        "-ss", f"{ts:.3f}", "-i", video_path,
        "-frames:v", "1",
        "-vf", f"scale={w}:{h}:flags=lanczos",
        "-y", str(out_path)
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "프리뷰 추출 실패")
    return out_path

def build_filters(width: int, height: int, mode: str, fps: int, extra: str = "") -> str:
    # mode: 'letterbox'|'cover'|'stretch'
    if mode == "letterbox":
        scale = f"scale={width}:{height}:force_original_aspect_ratio=decrease:flags=lanczos"
        post = f",pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"
    elif mode == "cover":
        scale = f"scale={width}:{height}:force_original_aspect_ratio=increase:flags=lanczos"
        post = f",crop={width}:{height}"
    else:  # stretch (distort)
        scale = f"scale={width}:{height}:flags=lanczos"
        post = ""
    base = f"fps={fps},{scale}{post}"
    if extra:
        base = f"{base},{extra}"
    return base

def build_gif_commands_auto(ffmpeg_path: str, video_path: str, start: float, end: float,
                            fps: int, width: int, height: int, mode: str,
                            alg: str, dither: str, out_path: str):
    duration = max(0.0, end - start)
    if duration <= 0:
        raise ValueError("시작/끝 시간이 올바르지 않습니다.")
    extra = "" if alg == "even" else "mpdecimate,setpts=N/FRAME_RATE/TB"
    vf = build_filters(width, height, mode, fps, extra)
    palette_path = str(CACHE_DIR / "palette.png")
    pass1 = [
        ffmpeg_path, "-hide_banner", "-loglevel", "error",
        "-ss", f"{start:.3f}", "-t", f"{duration:.3f}",
        "-i", video_path,
        "-vf", f"{vf},palettegen=stats_mode=full",
        "-y", palette_path
    ]
    pass2 = [
        ffmpeg_path, "-hide_banner", "-loglevel", "error",
        "-ss", f"{start:.3f}", "-t", f"{duration:.3f}",
        "-i", video_path,
        "-i", palette_path,
        "-lavfi", f"{vf}[x];[x][1:v]paletteuse=dither={dither}",
        "-loop", "0",
        "-y", out_path
    ]
    return [pass1, pass2]

def build_gif_commands_manual(ffmpeg_path: str, frames_dir: Path, fps: int,
                              width: int, height: int, mode: str,
                              dither: str, out_path: str):
    vf = build_filters(width, height, mode, fps, extra="")
    palette_path = str(CACHE_DIR / "palette_manual.png")
    pass1 = [
        ffmpeg_path, "-hide_banner", "-loglevel", "error",
        "-framerate", str(fps),
        "-i", str(frames_dir / "frame_%04d.png"),
        "-vf", f"{vf},palettegen=stats_mode=full",
        "-y", palette_path
    ]
    pass2 = [
        ffmpeg_path, "-hide_banner", "-loglevel", "error",
        "-framerate", str(fps),
        "-i", str(frames_dir / "frame_%04d.png"),
        "-i", palette_path,
        "-lavfi", f"{vf}[x];[x][1:v]paletteuse=dither={dither}",
        "-loop", "0",
        "-y", out_path
    ]
    return [pass1, pass2]

# ---------- RangeSlider ----------
class RangeSlider(QWidget):
    changed = Signal(float, float)  # 0..1
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(36)
        self._lower = 0.0
        self._upper = 0.1
        self._active = None
    def lower(self): return self._lower
    def upper(self): return self._upper
    def setRange(self, lower: float, upper: float, emit_signal=True):
        lower = max(0.0, min(1.0, lower))
        upper = max(0.0, min(1.0, upper))
        if upper < lower: upper = lower
        self._lower, self._upper = lower, upper
        self.update()
        if emit_signal: self.changed.emit(self._lower, self._upper)
    def paintEvent(self, e):
        p = QPainter(self); w = self.width(); h = self.height()
        bar_rect = QRect(10, h//2 - 4, w-20, 8)
        p.setPen(Qt.NoPen); p.setBrush(QColor(60,60,60)); p.drawRect(bar_rect)
        lpx = bar_rect.x() + int(bar_rect.width()*self._lower)
        upx = bar_rect.x() + int(bar_rect.width()*self._upper)
        sel_rect = QRect(lpx, bar_rect.y(), upx - lpx, bar_rect.height())
        p.setBrush(QColor(90,160,255)); p.drawRect(sel_rect)
        handle_w = 8; handle_h = 22
        p.setBrush(QColor(220,220,220)); p.setPen(QColor(80,80,80))
        p.drawRoundedRect(QRect(lpx- handle_w//2, bar_rect.center().y()-handle_h//2, handle_w, handle_h), 3,3)
        p.drawRoundedRect(QRect(upx- handle_w//2, bar_rect.center().y()-handle_h//2, handle_w, handle_h), 3,3)
    def mousePressEvent(self, e):
        bar_w = self.width()-20; x = e.position().x()
        lpx = 10 + int(bar_w*self._lower); upx = 10 + int(bar_w*self._upper)
        self._active = 'l' if abs(x-lpx) < abs(x-upx) else 'u'
        self.mouseMoveEvent(e)
    def mouseMoveEvent(self, e):
        if not self._active: return
        val = (e.position().x()-10)/max(1,(self.width()-20))
        val = max(0.0, min(1.0, val))
        if self._active == 'l': self._lower = min(val, self._upper)
        else: self._upper = max(val, self._lower)
        self.update(); self.changed.emit(self._lower, self._upper)
    def mouseReleaseEvent(self, e): self._active=None

# ---------- Main ----------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(1280, 860)

        self.ffmpeg_path = find_executable("ffmpeg")
        self.ffprobe_path = find_executable("ffprobe")
        self.video_path = ""
        self.duration_sec = 0.0

        self._build_ui()
        self._auto_setup_tools()
        self.preview_timer = QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.setInterval(200)
        self.preview_timer.timeout.connect(self._update_split_preview)

    def _build_ui(self):
        menu = self.menuBar().addMenu("설정")
        act_paths = QAction("도구 경로 설정(ffmpeg/ffprobe)", self)
        act_paths.triggered.connect(self._select_tools)
        menu.addAction(act_paths)

        act_dl = QAction("ffmpeg 자동 준비(재실행)", self)
        act_dl.triggered.connect(self._auto_setup_tools)
        menu.addAction(act_dl)

        central = QWidget(); root = QVBoxLayout(central); self.setCentralWidget(central)

        # File row
        file_box = QHBoxLayout()
        self.le_video = QLineEdit(); self.le_video.setPlaceholderText("동영상 파일 경로 (mp4 등)")
        btn_browse = QPushButton("열기…"); btn_browse.clicked.connect(self._browse_video)
        file_box.addWidget(QLabel("입력 비디오:")); file_box.addWidget(self.le_video, 1); file_box.addWidget(btn_browse)

        meta_box = QHBoxLayout()
        self.lbl_duration = QLabel("길이: -")
        self.lbl_tools = QLabel(self._tools_label_text())
        meta_box.addWidget(self.lbl_duration); meta_box.addStretch(1); meta_box.addWidget(self.lbl_tools)

        # Trim group
        trim_group = QGroupBox("구간 선택 — 최소 2초, 최대 10초 (슬라이더 드래그 또는 시간 직접 입력)")
        tg = QGridLayout(trim_group)

        self.range = RangeSlider(); self.range.setRange(0.0, 0.1)
        self.range.changed.connect(self._range_changed)

        self.le_start = QLineEdit("00:00.000")
        self.le_end = QLineEdit("00:02.000")
        for le in (self.le_start, self.le_end):
            le.setPlaceholderText("mm:ss.mmm 또는 hh:mm:ss.mmm")
            le.editingFinished.connect(self._apply_edits_to_range)

        self.btn_prev_start = QPushButton("시작 프레임")
        self.btn_prev_end = QPushButton("끝 프레임")
        self.btn_prev_start.clicked.connect(lambda: self._update_preview(which='start'))
        self.btn_prev_end.clicked.connect(lambda: self._update_preview(which='end'))

        from PySide6.QtWidgets import QScrollArea
        self.lbl_prev_start = QLabel("시작 프리뷰"); self.lbl_prev_start.setAlignment(Qt.AlignCenter)
        self.lbl_prev_end = QLabel("끝 프리뷰"); self.lbl_prev_end.setAlignment(Qt.AlignCenter)
        for _lbl in (self.lbl_prev_start, self.lbl_prev_end):
            _lbl.setMinimumHeight(420)
            _lbl.setStyleSheet("QLabel{border:1px solid #555; background:#111; color:#bbb;}")
        # Timeline thumbnails area (scrollable)
        self.timeline_area = QScrollArea(); self.timeline_area.setWidgetResizable(True)
        self.timeline_inner = QWidget(); from PySide6.QtWidgets import QHBoxLayout
        self.timeline_layout = QHBoxLayout(self.timeline_inner); self.timeline_layout.setContentsMargins(4,4,4,4); self.timeline_layout.setSpacing(4)
        self.timeline_area.setWidget(self.timeline_inner)

        tg.addWidget(self.range, 0, 0, 1, 6)
        tg.addWidget(self.timeline_area, 1, 0, 1, 6)
        tg.addWidget(QLabel("시작:"), 2, 0); tg.addWidget(self.le_start, 2, 1)
        tg.addWidget(QLabel("끝:"), 2, 2); tg.addWidget(self.le_end, 2, 3)
        tg.addWidget(self.btn_prev_start, 2, 4)
        tg.addWidget(self.btn_prev_end, 2, 5)
        thumbs_split = QHBoxLayout(); thumbs_split.addWidget(self.lbl_prev_start); thumbs_split.addWidget(self.lbl_prev_end)
        tg.addLayout(thumbs_split, 3, 0, 1, 6)

        # Options
        opt_group = QGroupBox("옵션")
        og = QGridLayout(opt_group)

        self.combo_mode = QComboBox(); self.combo_mode.addItems(["자동(균등)", "자동(중복 제거)", "수동 선택"])
        self.spin_fps = QSpinBox(); self.spin_fps.setRange(1, 60); self.spin_fps.setValue(DEFAULT_FPS)
        self.spin_w = QSpinBox(); self.spin_w.setRange(8, 1024); self.spin_w.setValue(DEFAULT_WIDTH)
        self.spin_h = QSpinBox(); self.spin_h.setRange(8, 1024); self.spin_h.setValue(DEFAULT_HEIGHT)

        self.combo_scale = QComboBox(); self.combo_scale.addItems(["레터박스(비율 유지)", "꽉 채우기(크롭)", "스트레치(왜곡)"])
        self.combo_scale.setCurrentIndex(1)
        self.combo_dither = QComboBox(); self.combo_dither.addItems(["floyd_steinberg", "bayer", "none"])

        og.addWidget(QLabel("모드:"), 0, 0); og.addWidget(self.combo_mode, 0, 1)
        og.addWidget(QLabel("FPS:"), 0, 2); og.addWidget(self.spin_fps, 0, 3)
        og.addWidget(QLabel("가로:"), 0, 4); og.addWidget(self.spin_w, 0, 5)
        og.addWidget(QLabel("세로:"), 0, 6); og.addWidget(self.spin_h, 0, 7)
        og.addWidget(QLabel("스케일:"), 1, 0); og.addWidget(self.combo_scale, 1, 1, 1, 3)
        og.addWidget(QLabel("디더링:"), 1, 4); og.addWidget(self.combo_dither, 1, 5)

        # Manual picker
        manual_group = QGroupBox("프레임 선택(수동 모드)")
        mg = QVBoxLayout(manual_group)

        top_bar = QHBoxLayout()
        self.btn_scan = QPushButton("구간에서 프레임 스캔"); self.btn_scan.clicked.connect(self._scan_frames)
        self.spin_scan_fps = QSpinBox(); self.spin_scan_fps.setRange(1, 30); self.spin_scan_fps.setValue(10)
        top_bar.addWidget(QLabel("스캔 FPS:")); top_bar.addWidget(self.spin_scan_fps)
        btn_all = QPushButton("전체 선택/해제"); btn_all.clicked.connect(self._toggle_all_frames)
        top_bar.addStretch(1); top_bar.addWidget(self.btn_scan); top_bar.addWidget(btn_all)

        self.list_frames = QListWidget()
        self.list_frames.setViewMode(QListView.IconMode)
        self.list_frames.setIconSize(QSize(192, 108))
        self.list_frames.setResizeMode(QListView.Adjust)
        self.list_frames.setSpacing(6)
        self.list_frames.setMinimumHeight(220)

        mg.addLayout(top_bar); mg.addWidget(self.list_frames)

        # Output
        out_box = QHBoxLayout()
        self.le_out = QLineEdit()
        self.le_out.setPlaceholderText(str(APP_DIR / "output.gif"))
        btn_out = QPushButton("저장 위치…"); btn_out.clicked.connect(self._choose_output)
        out_box.addWidget(QLabel("출력:")); out_box.addWidget(self.le_out, 1); out_box.addWidget(btn_out)

        run_box = QHBoxLayout()
        self.btn_generate = QPushButton("GIF 생성"); self.btn_generate.clicked.connect(self._generate_gif)
        run_box.addStretch(1); run_box.addWidget(self.btn_generate)

        self.log = QTextEdit(); self.log.setReadOnly(True); self.log.setPlaceholderText("로그")

        # assemble
        root.addLayout(file_box)
        root.addLayout(meta_box)
        root.addWidget(trim_group)
        root.addWidget(opt_group)
        root.addWidget(manual_group)
        root.addLayout(out_box)
        root.addLayout(run_box)
        root.addWidget(self.log, 1)

        manual_group.setVisible(self.combo_mode.currentIndex() == 2)
        self.combo_mode.currentIndexChanged.connect(lambda idx: manual_group.setVisible(idx == 2))

        def _run(self, cmd):
            kw = dict(capture_output=True, text=True)
            if os.name == "nt":
                kw["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
                si = subprocess.STARTUPINFO(); si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                kw["startupinfo"] = si
            return subprocess.run(cmd, **kw)

        def _update_split_preview(self):
            if not self.video_path or not self.ffmpeg_path: return
            start_ts = self.range.lower() * self.duration_sec
            end_ts = self.range.upper() * self.duration_sec
            try:
                p1 = extract_preview_frame(self.ffmpeg_path, self.video_path, start_ts)
                p2 = extract_preview_frame(self.ffmpeg_path, self.video_path, end_ts)
                pix1 = QPixmap(str(p1)).scaled(self.lbl_prev_start.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                pix2 = QPixmap(str(p2)).scaled(self.lbl_prev_end.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                if not pix1.isNull(): self.lbl_prev_start.setPixmap(pix1)
                if not pix2.isNull(): self.lbl_prev_end.setPixmap(pix2)
            except Exception as e:
                self._append_log(f"[ERR] 미리보기 업데이트 실패: {e}")

        def _build_timeline_thumbs(self):
            from pathlib import Path
            thumbs_dir = CACHE_DIR / "timeline"
            if thumbs_dir.exists():
                for p in thumbs_dir.glob("thumb_*.png"):
                    try: p.unlink()
                    except: pass
            else:
                thumbs_dir.mkdir(parents=True, exist_ok=True)
            if not self.video_path or not self.ffmpeg_path or self.duration_sec <= 0: return
            cmd = [self.ffmpeg_path, "-hide_banner", "-loglevel", "error",
                   "-i", self.video_path,
                   "-vf", "fps=1/2,scale=160:-1:flags=lanczos",
                   str(thumbs_dir / "thumb_%05d.png")]
            self._append_log("[RUN] 타임라인 썸네일 생성: " + " ".join(map(str, cmd)))
            proc = self._run(cmd)
            from PySide6.QtWidgets import QLabel
            from PySide6.QtGui import QPixmap
            while self.timeline_layout.count():
                item = self.timeline_layout.takeAt(0)
                w = item.widget()
                if w: w.setParent(None)
            files = sorted(thumbs_dir.glob("thumb_*.png"))
            for fp in files:
                lb = QLabel()
                lb.setPixmap(QPixmap(str(fp)).scaled(96, 54, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                lb.setToolTip(fp.name)
                self.timeline_layout.addWidget(lb)
            self.timeline_layout.addStretch(1)

    # ---------- Tools ----------
    def _tools_label_text(self):
        ffn = Path(self.ffmpeg_path).name if self.ffmpeg_path else '미설정'
        fpn = Path(self.ffprobe_path).name if self.ffprobe_path else '미설정'
        return f"ffmpeg: {ffn} | ffprobe: {fpn}"

    def _append_log(self, t: str): self.log.append(t)

    def _select_tools(self):
        ffmpeg, _ = QFileDialog.getOpenFileName(self, "ffmpeg 실행 파일 선택", "", "Executable (*)")
        if ffmpeg: self.ffmpeg_path = ffmpeg
        ffprobe, _ = QFileDialog.getOpenFileName(self, "ffprobe 실행 파일 선택", "", "Executable (*)")
        if ffprobe: self.ffprobe_path = ffprobe
        self.lbl_tools.setText(self._tools_label_text())

    def _auto_setup_tools(self):
        self.ffmpeg_path = find_executable("ffmpeg")
        self.ffprobe_path = find_executable("ffprobe")
        if self.ffmpeg_path and self.ffprobe_path:
            self._append_log("[INFO] ffmpeg/ffprobe 준비됨")
            self.lbl_tools.setText(self._tools_label_text()); return
        os_name = platform.system().lower()
        if "windows" in os_name: self._setup_windows_ffmpeg()
        elif "darwin" in os_name or "mac" in os_name: self._setup_macos_ffmpeg()
        elif "linux" in os_name: self._setup_linux_ffmpeg()
        else: self._append_log("[WARN] 미지원 OS. 수동 설치 필요.")
        self.ffmpeg_path = find_executable("ffmpeg")
        self.ffprobe_path = find_executable("ffprobe")
        self.lbl_tools.setText(self._tools_label_text())

    def _download(self, url: str, dest_path: Path) -> bool:
        try:
            with urllib.request.urlopen(url) as resp, open(dest_path, "wb") as out:
                total = int(resp.headers.get("Content-Length", "0") or 0)
                read = 0
                while True:
                    chunk = resp.read(1024*256)
                    if not chunk: break
                    out.write(chunk); read += len(chunk)
                    if total: self._append_log(f"[DL] {int(read*100/total)}%")
            self._append_log("[DL] 완료"); return True
        except Exception as e:
            self._append_log(f"[DL] 오류: {e}"); return False

    def _setup_windows_ffmpeg(self):
        candidates = [
            "https://github.com/GyanD/codexffmpeg/releases/latest/download/ffmpeg-essentials_build.zip",
            "https://github.com/GyanD/codexffmpeg/releases/latest/download/ffmpeg-release-essentials.zip",
            "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
        ]
        zip_path = FFMPEG_DIR / "ffmpeg-essentials.zip"
        for url in candidates:
            self._append_log(f"[DL] {url}")
            if not self._download(url, zip_path): continue
            try:
                with zipfile.ZipFile(zip_path, 'r') as zf: zf.extractall(FFMPEG_DIR)
                ffmpeg = None; ffprobe = None
                for p in FFMPEG_DIR.rglob("*"):
                    if p.name.lower() == "ffmpeg.exe": ffmpeg = str(p.resolve())
                    elif p.name.lower() == "ffprobe.exe": ffprobe = str(p.resolve())
                if ffmpeg and ffprobe:
                    shutil.copy2(ffmpeg, FFMPEG_DIR / "ffmpeg.exe")
                    shutil.copy2(ffprobe, FFMPEG_DIR / "ffprobe.exe")
                    self._append_log(f"[OK] ffmpeg 준비: {FFMPEG_DIR / 'ffmpeg.exe'}")
                    self._append_log(f"[OK] ffprobe 준비: {FFMPEG_DIR / 'ffprobe.exe'}")
                    return
            except Exception as e:
                self._append_log(f"[ERR] ZIP 추출 실패: {e}")
        self._append_log("[ERR] ffmpeg 자동 준비 실패")

    def _setup_macos_ffmpeg(self):
        brew = shutil.which("brew")
        if brew:
            self._append_log("[INFO] macOS: brew install ffmpeg")
            try: subprocess.run([brew, "install", "ffmpeg"], check=False, text=True, capture_output=True)
            except Exception as e: self._append_log(f"[ERR] brew 실패: {e}")
        else: self._append_log("[WARN] Homebrew 미설치. 수동 설치 필요.")

    def _setup_linux_ffmpeg(self):
        apt = shutil.which("apt-get")
        if apt:
            self._append_log("[INFO] Linux: apt-get install ffmpeg")
            try:
                subprocess.run(["sudo", "apt-get", "update"], check=False, text=True, capture_output=True)
                subprocess.run(["sudo", "apt-get", "-y", "install", "ffmpeg"], check=False, text=True, capture_output=True)
            except Exception as e:
                self._append_log(f"[ERR] apt-get 실패: {e}")
        if not find_executable("ffmpeg") or not find_executable("ffprobe"):
            arch = platform.machine().lower()
            if arch in ("x86_64","amd64"):
                url = "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"
            elif arch in ("aarch64","arm64"):
                url = "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-arm64-static.tar.xz"
            else:
                self._append_log(f"[WARN] 미지원 아키텍처({arch})."); return
            tar_path = FFMPEG_DIR / Path(url).name
            if self._download(url, tar_path):
                try:
                    import tarfile
                    with tarfile.open(tar_path, 'r:*') as tf: tf.extractall(FFMPEG_DIR)
                    ffmpeg = None; ffprobe = None
                    for p in FFMPEG_DIR.rglob("*"):
                        if p.name == "ffmpeg": ffmpeg = str(p.resolve())
                        elif p.name == "ffprobe": ffprobe = str(p.resolve())
                    if ffmpeg and ffprobe:
                        shutil.copy2(ffmpeg, FFMPEG_DIR / "ffmpeg"); shutil.copy2(ffprobe, FFMPEG_DIR / "ffprobe")
                        os.chmod(FFMPEG_DIR / "ffmpeg", 0o755); os.chmod(FFMPEG_DIR / "ffprobe", 0o755)
                        self._append_log("[OK] 정적 빌드 준비 완료")
                except Exception as e:
                    self._append_log(f"[ERR] 정적 빌드 추출 실패: {e}")

    # ---------- Load & Trim ----------
    def _browse_video(self):
        path, _ = QFileDialog.getOpenFileName(self, "비디오 파일 선택", "", "Videos (*.mp4 *.mov *.mkv *.webm *.avi);;All files (*.*)")
        if not path: return
        self.le_video.setText(path); self._load_video(path)

    def _load_video(self, path: str):
        if not Path(path).is_file():
            QMessageBox.warning(self, "오류", "파일이 존재하지 않습니다."); return
        if not self.ffprobe_path:
            QMessageBox.warning(self, "오류", "ffprobe 준비가 필요합니다."); return
        try:
            dur = probe_duration_sec(self.ffprobe_path, path)
            self.duration_sec = dur; self.video_path = path
            self.lbl_duration.setText(f"길이: {seconds_to_hhmmss(dur)} ({dur:.3f}s)")
            end = min(TRIM_MIN_SEC, self.duration_sec) if self.duration_sec >= TRIM_MIN_SEC else self.duration_sec
            hi = end / max(1e-9, self.duration_sec)
            self.range.setRange(0.0, hi)
            self._apply_trim_constraints(adjust='end')
            self._update_time_edits()
            self._build_timeline_thumbs()
            self._update_split_preview()
            self._append_log(f"[OK] 동영상 로드: {path}")
        except Exception as e:
            QMessageBox.critical(self, "오류", f"동영상 정보를 읽는 중 문제 발생:\n{e}")
            self._append_log(f"[ERR] ffprobe 실패: {e}")

    def _range_changed(self, lo: float, hi: float):
        self._apply_trim_constraints()
        self._update_time_edits()
        self.preview_timer.start()

    def _apply_trim_constraints(self, adjust='auto'):
        if self.duration_sec <= 0: return
        lo = self.range.lower() * self.duration_sec
        hi = self.range.upper() * self.duration_sec
        span = hi - lo
        if span < TRIM_MIN_SEC:
            need = TRIM_MIN_SEC - span
            if adjust == 'end' or (adjust == 'auto' and hi + need <= self.duration_sec):
                hi = min(self.duration_sec, hi + need)
            else:
                lo = max(0.0, lo - need)
        if span > TRIM_MAX_SEC:
            cut = span - TRIM_MAX_SEC
            if adjust == 'end' or (adjust == 'auto' and hi - cut >= 0):
                hi = hi - cut
            else:
                lo = lo + cut
        self.range.setRange(lo / max(1e-9, self.duration_sec), hi / max(1e-9, self.duration_sec), emit_signal=False)

    def _update_time_edits(self):
        lo = self.range.lower() * self.duration_sec
        hi = self.range.upper() * self.duration_sec
        self.le_start.setText(seconds_to_hhmmss(lo))
        self.le_end.setText(seconds_to_hhmmss(hi))

    def _apply_edits_to_range(self):
        if self.duration_sec <= 0: return
        try:
            lo = hhmmss_to_seconds(self.le_start.text())
            hi = hhmmss_to_seconds(self.le_end.text())
        except Exception:
            QMessageBox.warning(self, "오류", "시간 형식이 올바르지 않습니다."); self._update_time_edits(); return
        if lo < 0: lo = 0.0
        if hi > self.duration_sec: hi = self.duration_sec
        if hi <= lo:
            hi = min(self.duration_sec, lo + TRIM_MIN_SEC)
        span = hi - lo
        if span < TRIM_MIN_SEC:
            hi = min(self.duration_sec, lo + TRIM_MIN_SEC)
        if span > TRIM_MAX_SEC:
            hi = lo + TRIM_MAX_SEC if lo + TRIM_MAX_SEC <= self.duration_sec else self.duration_sec
            lo = max(0.0, hi - TRIM_MAX_SEC)
        self.range.setRange(lo / max(1e-9, self.duration_sec), hi / max(1e-9, self.duration_sec))

    def _update_preview(self, which: str):
        if not self.video_path or not self.ffmpeg_path: return
        ts = self.range.lower()*self.duration_sec if which=='start' else self.range.upper()*self.duration_sec
        try:
            img = extract_preview_frame(self.ffmpeg_path, self.video_path, ts)
            pix = QPixmap(str(img))
            if not pix.isNull():
                self.lbl_preview.setPixmap(pix.scaled(self.lbl_preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        except Exception as e:
            self._append_log(f"[ERR] 프리뷰 실패: {e}")

    # ---------- Manual frames ----------
    def _clear_frames_dir(self, d: Path):
        if d.exists():
            for p in d.glob("*.png"):
                try: p.unlink()
                except: pass
        else:
            d.mkdir(parents=True, exist_ok=True)

    def _scan_frames(self):
        if not self.video_path or not self.ffmpeg_path:
            QMessageBox.warning(self, "오류", "비디오 또는 ffmpeg가 준비되지 않았습니다."); return
        if self.combo_mode.currentIndex() != 2:
            QMessageBox.information(self, "안내", "수동 선택 모드에서 사용하세요."); return
        scan_fps = self.spin_scan_fps.value()
        lo = self.range.lower() * self.duration_sec
        hi = self.range.upper() * self.duration_sec
        duration = max(0.0, hi - lo)
        if duration <= 0:
            QMessageBox.warning(self, "오류", "구간이 올바르지 않습니다."); return
        frames_dir = CACHE_DIR / "frames"
        self._clear_frames_dir(frames_dir)
        cmd = [
            self.ffmpeg_path, "-hide_banner", "-loglevel", "error",
            "-ss", f"{lo:.3f}", "-t", f"{duration:.3f}",
            "-i", self.video_path,
            "-vf", f"fps={scan_fps},scale=384:216:flags=lanczos",
            str(frames_dir / "frame_%04d.png")
        ]
        self._append_log("[RUN] 프레임 스캔: " + " ".join(map(str,cmd)))
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            self._append_log(proc.stderr.strip()); QMessageBox.critical(self, "오류", "프레임 추출 실패"); return
        self.list_frames.clear()
        files = sorted(frames_dir.glob("frame_*.png"))
        for fp in files:
            item = QListWidgetItem()
            item.setText(fp.name)
            pix = QPixmap(str(fp)).scaled(self.list_frames.iconSize(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            item.setIcon(pix); item.setCheckState(Qt.Checked)
            self.list_frames.addItem(item)
        self._append_log(f"[OK] 스캔 완료: {len(files)} 프레임")

    def _toggle_all_frames(self):
        any_unchecked = any(self.list_frames.item(i).checkState() == Qt.Unchecked for i in range(self.list_frames.count()))
        new_state = Qt.Checked if any_unchecked else Qt.Unchecked
        for i in range(self.list_frames.count()):
            self.list_frames.item(i).setCheckState(new_state)

    # ---------- Output ----------
    def _choose_output(self):
        default_name = str(APP_DIR / "output.gif")
        path, _ = QFileDialog.getSaveFileName(self, "출력 GIF 저장", default_name, "GIF (*.gif)")
        if path:
            if not path.lower().endswith(".gif"): path += ".gif"
            self.le_out.setText(path)

    # ---------- Generate ----------
    def _ensure_tools(self) -> bool:
        if not self.ffmpeg_path or not Path(self.ffmpeg_path).exists():
            self._append_log("[ERR] ffmpeg 경로를 찾을 수 없습니다."); return False
        if not self.ffprobe_path or not Path(self.ffprobe_path).exists():
            self._append_log("[ERR] ffprobe 경로를 찾을 수 없습니다."); return False
        return True

    def _generate_gif(self):
        if not self._ensure_tools():
            QMessageBox.warning(self, "오류", "ffmpeg/ffprobe 준비가 필요합니다."); return
        if not self.video_path:
            QMessageBox.warning(self, "오류", "먼저 비디오를 불러오세요."); return

        lo = self.range.lower() * self.duration_sec
        hi = self.range.upper() * self.duration_sec
        duration = max(0.0, hi - lo)
        if duration < TRIM_MIN_SEC or duration > TRIM_MAX_SEC:
            QMessageBox.warning(self, "오류", f"구간은 {TRIM_MIN_SEC:.0f}~{TRIM_MAX_SEC:.0f}초여야 합니다."); return

        fps = self.spin_fps.value()
        w = self.spin_w.value(); h = self.spin_h.value()
        mode = ["letterbox","cover","stretch"][self.combo_scale.currentIndex()]
        dither = self.combo_dither.currentText()

        out_path = self.le_out.text().strip()
        if not out_path:
            base = Path(self.video_path).with_suffix("")
            out_path = str(APP_DIR / f"{Path(base).name}_{int(lo*1000)}_{int(hi*1000)}.gif")
            self.le_out.setText(out_path)

        mode_idx = self.combo_mode.currentIndex()
        if mode_idx in (0,1):
            alg = "even" if mode_idx == 0 else "mpdecimate"
            cmds = build_gif_commands_auto(self.ffmpeg_path, self.video_path, lo, hi, fps, w, h, mode, alg, dither, out_path)
        else:
            frames_dir = CACHE_DIR / "frames_selected"
            self._clear_frames_dir(frames_dir)
            src_dir = CACHE_DIR / "frames"
            files = [src_dir / self.list_frames.item(i).text() for i in range(self.list_frames.count())
                     if self.list_frames.item(i).checkState() == Qt.Checked]
            if not files:
                QMessageBox.warning(self, "오류", "선택된 프레임이 없습니다."); return
            for idx, fp in enumerate(files, start=1):
                shutil.copy2(fp, frames_dir / f"frame_{idx:04d}.png")
            cmds = build_gif_commands_manual(self.ffmpeg_path, frames_dir, fps, w, h, mode, dither, out_path)

        self.btn_generate.setEnabled(False)
        self._append_log("[RUN] GIF 생성 시작")
        for i, cmd in enumerate(cmds, start=1):
            self._append_log(f"[RUN] Pass {i}: {' '.join(map(str,cmd))}")
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.stdout.strip(): self._append_log(proc.stdout.strip())
            if proc.stderr.strip(): self._append_log(proc.stderr.strip())
            if proc.returncode != 0:
                QMessageBox.critical(self, "오류", f"ffmpeg 실행 실패 (Pass {i}). 로그 확인.")
                self._append_log(f"[ERR] 코드={proc.returncode}")
                self.btn_generate.setEnabled(True); return

        if Path(out_path).is_file():
            self._append_log(f"[OK] 완료: {out_path}")
            QMessageBox.information(self, "완료", f"GIF 생성 완료:{out_path}")
        else:
            self._append_log("[ERR] 출력 파일을 찾을 수 없습니다.")
            QMessageBox.warning(self, "경고", "출력 파일을 찾을 수 없습니다.")
        self.btn_generate.setEnabled(True)

def main():
    app = QApplication(sys.argv)
    w = MainWindow(); w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
