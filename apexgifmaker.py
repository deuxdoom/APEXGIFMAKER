#APEXGIFMAKER
#coding: utf-8
"""
apexgifmaker.py — Apex GIF Maker (MP4 → GIF), PySide6 + FFmpeg

v1.0.0
- 듀얼 핸들 구간 트림(2–10초) + 시간 직접 입력(mm:ss.mmm / hh:mm:ss.mmm)
- 스케일 모드 3종: 꽉 채우기(크롭, 기본) / 레터박스 / 스트레치
- 프리뷰 2분할(시작/끝) 1280×720, 2초 간격 타임라인 썸네일
- 자동(균등/중복제거) + 수동 선택, 2-pass 팔레트 + 디더링
- FFmpeg 자동 준비(+ 정리: ffmpeg/ffprobe만 유지)

icon credit https://www.flaticon.com/free-icon/gif-file_3979434
"""

import os
import sys
import stat
import shutil
import subprocess
import platform
import urllib.request
import zipfile
import tarfile
import base64
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QSize, QRect, Signal, QTimer
from PySide6.QtGui import QAction, QPixmap, QPainter, QColor, QIcon
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFileDialog, QMessageBox,
    QLabel, QLineEdit, QSpinBox, QComboBox, QPushButton,
    QGroupBox, QGridLayout, QVBoxLayout, QHBoxLayout, QTextEdit,
    QListWidget, QListWidgetItem, QListView, QScrollArea
)

APP_TITLE = "Apex GIF Maker (MP4 → GIF)"
DEFAULT_WIDTH = 160
DEFAULT_HEIGHT = 80
DEFAULT_FPS = 12
TRIM_MIN_SEC = 2.0
TRIM_MAX_SEC = 10.0

# =========================================================
# 내장 아이콘(Base64 PNG) — Flaticon GIF 파일 아이콘(파란 계열)
# PNG → Base64 (icons/icon.png 512x512) 로 변환한 값. 필요 시 교체 가능.
# =========================================================
EMBED_ICON_PNG_B64 = (
    "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"
)
# ↑ 주의: 위 Base64는 실제 아이콘 PNG의 전체 데이터입니다(512x512 RGBA).
#    다른 아이콘을 쓰려면 원하는 PNG를 Base64로 변환해 문자열만 교체하세요.

# ---------- Paths ----------
def app_root() -> Path:
    return Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent

APP_DIR    = app_root()
CACHE_DIR  = APP_DIR / "cache"
FFMPEG_DIR = APP_DIR / "ffmpeg-bin"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
FFMPEG_DIR.mkdir(parents=True, exist_ok=True)

def find_executable(name: str) -> str:
    local = FFMPEG_DIR / (name + (".exe" if os.name == "nt" else ""))
    if local.exists():
        return str(local)
    return shutil.which(name) or ""

# ---------- Icon / Branding ----------
def get_app_icon() -> QIcon:
    """내장 Base64 PNG → QIcon. 여러 사이즈로 등록."""
    try:
        data = base64.b64decode(EMBED_ICON_PNG_B64)
        pm = QPixmap()
        pm.loadFromData(data, "PNG")
        if pm.isNull():
            return QIcon()
        icon = QIcon()
        for s in (16, 20, 24, 32, 40, 48, 64, 128, 256):
            icon.addPixmap(pm.scaled(s, s, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        return icon
    except Exception:
        return QIcon()

def _set_win_appusermodel_id(appid: str = "ApexGIFMaker"):
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(appid)
        except Exception:
            pass

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
    if secs < 0:
        secs = 0
    h = int(secs // 3600)
    m = int((secs % 3600) // 60)
    s = secs % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}" if h > 0 else f"{m:02d}:{s:06.3f}"

# ---------- subprocess helper (콘솔 비표시) ----------
def run_quiet(cmd):
    kw = dict(capture_output=True, text=True)
    if os.name == "nt":
        kw["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        kw["startupinfo"] = si
    return subprocess.run(cmd, **kw)

# ---------- ffmpeg helpers ----------
def probe_duration_sec(ffprobe_path: str, video_path: str) -> float:
    cmd = [ffprobe_path, "-v", "error", "-show_entries", "format=duration",
           "-of", "default=noprint_wrappers=1:nokey=1", video_path]
    proc = run_quiet(cmd)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "ffprobe 실패")
    return float(proc.stdout.strip())

def extract_preview_frame(ffmpeg_path: str, video_path: str, ts: float) -> Path:
    w, h = 1280, 720
    out_dir = CACHE_DIR / "previews"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"preview_{abs(hash((video_path, round(ts,3), '1280x720')))}.png"
    cmd = [ffmpeg_path, "-hide_banner", "-loglevel", "error", "-ss", f"{ts:.3f}", "-i", video_path,
           "-frames:v", "1", "-vf", f"scale={w}:{h}:flags=lanczos", "-y", str(out_path)]
    proc = run_quiet(cmd)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "프리뷰 추출 실패")
    return out_path

def build_filters(width: int, height: int, mode: str, fps: int, extra: str = "") -> str:
    if mode == "letterbox":
        scale = f"scale={width}:{height}:force_original_aspect_ratio=decrease:flags=lanczos"
        post  = f",pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"
    elif mode == "cover":
        scale = f"scale={width}:{height}:force_original_aspect_ratio=increase:flags=lanczos"
        post  = f",crop={width}:{height}"
    else:  # stretch
        scale = f"scale={width}:{height}:flags=lanczos"
        post  = ""
    base = f"fps={fps},{scale}{post}"
    return f"{base},{extra}" if extra else base

def build_gif_commands_auto(ffmpeg_path: str, video_path: str, start: float, end: float,
                            fps: int, width: int, height: int, mode: str,
                            alg: str, dither: str, out_path: str):
    duration = max(0.0, end - start)
    if duration <= 0:
        raise ValueError("시작/끝 시간이 올바르지 않습니다.")
    extra = "" if alg == "even" else "mpdecimate,setpts=N/FRAME_RATE/TB"
    vf = build_filters(width, height, mode, fps, extra)
    palette_path = str(CACHE_DIR / "palette.png")
    pass1 = [ffmpeg_path, "-hide_banner", "-loglevel", "error", "-ss", f"{start:.3f}", "-t", f"{duration:.3f}",
             "-i", video_path, "-vf", f"{vf},palettegen=stats_mode=full", "-y", palette_path]
    pass2 = [ffmpeg_path, "-hide_banner", "-loglevel", "error", "-ss", f"{start:.3f}", "-t", f"{duration:.3f}",
             "-i", video_path, "-i", palette_path,
             "-lavfi", f"{vf}[x];[x][1:v]paletteuse=dither={dither}",
             "-loop", "0", "-y", out_path]
    return [pass1, pass2]

def build_gif_commands_manual(ffmpeg_path: str, frames_dir: Path, fps: int,
                              width: int, height: int, mode: str,
                              dither: str, out_path: str):
    vf = build_filters(width, height, mode, fps)
    palette_path = str(CACHE_DIR / "palette_manual.png")
    pass1 = [ffmpeg_path, "-hide_banner", "-loglevel", "error", "-framerate", str(fps),
             "-i", str(frames_dir / "frame_%04d.png"),
             "-vf", f"{vf},palettegen=stats_mode=full", "-y", palette_path]
    pass2 = [ffmpeg_path, "-hide_banner", "-loglevel", "error", "-framerate", str(fps),
             "-i", str(frames_dir / "frame_%04d.png"), "-i", palette_path,
             "-lavfi", f"{vf}[x];[x][1:v]paletteuse=dither={dither}",
             "-loop", "0", "-y", out_path]
    return [pass1, pass2]

# ---------- FFmpeg tidy helpers ----------
def _onerror_chmod(func, path, excinfo):
    try:
        os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
        func(path)
    except Exception:
        pass

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
        if upper < lower:
            upper = lower
        self._lower, self._upper = lower, upper
        self.update()
        if emit_signal:
            self.changed.emit(self._lower, self._upper)
    def paintEvent(self, e):
        p = QPainter(self); w = self.width(); h = self.height()
        bar_rect = QRect(10, h//2 - 4, w-20, 8)
        p.setPen(Qt.NoPen); p.setBrush(QColor(60,60,60)); p.drawRect(bar_rect)
        lpx = bar_rect.x() + int(bar_rect.width()*self._lower)
        upx = bar_rect.x() + int(bar_rect.width()*self._upper)
        sel_rect = QRect(lpx, bar_rect.y(), upx - lpx, bar_rect.height())
        p.setBrush(QColor(90,160,255)); p.drawRect(sel_rect)
        handle_w, handle_h = 8, 22
        p.setBrush(QColor(220,220,220)); p.setPen(QColor(80,80,80))
        p.drawRoundedRect(QRect(lpx- handle_w//2, bar_rect.center().y()-handle_h//2, handle_w, handle_h), 3,3)
        p.drawRoundedRect(QRect(upx- handle_w//2, bar_rect.center().y()-handle_h//2, handle_w, handle_h), 3,3)
    def mousePressEvent(self, e):
        bar_w = self.width()-20
        x = e.position().x()
        lpx = 10 + int(bar_w*self._lower)
        upx = 10 + int(bar_w*self._upper)
        self._active = 'l' if abs(x-lpx) < abs(x-upx) else 'u'
        self.mouseMoveEvent(e)
    def mouseMoveEvent(self, e):
        if not self._active:
            return
        val = (e.position().x()-10)/max(1,(self.width()-20))
        val = max(0.0, min(1.0, val))
        if self._active == 'l':
            self._lower = min(val, self._upper)
        else:
            self._upper = max(val, self._lower)
        self.update()
        self.changed.emit(self._lower, self._upper)
    def mouseReleaseEvent(self, e):
        self._active = None

# ---------- Main ----------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(1280, 860)

        app_icon = get_app_icon()
        if not app_icon.isNull():
            self.setWindowIcon(app_icon)

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

    # ----- UI -----
    def _build_ui(self):
        menu = self.menuBar().addMenu("설정")
        act_paths = QAction("도구 경로 설정(ffmpeg/ffprobe)", self)
        act_paths.triggered.connect(self._select_tools)
        menu.addAction(act_paths)

        act_dl = QAction("ffmpeg 자동 준비(재실행)", self)
        act_dl.triggered.connect(self._auto_setup_tools)
        menu.addAction(act_dl)

        act_clean = QAction("ffmpeg 폴더 정리", self)
        act_clean.triggered.connect(self._tidy_ffmpeg_dir)
        menu.addAction(act_clean)

        central = QWidget()
        root = QVBoxLayout(central)
        self.setCentralWidget(central)

        # ── 헤더(로고 + 타이틀)
        header = QHBoxLayout()
        self.lbl_logo = QLabel()
        ico = get_app_icon()
        if not ico.isNull():
            self.lbl_logo.setPixmap(ico.pixmap(28, 28))
        self.lbl_logo.setFixedSize(32, 32)
        title = QLabel("<b>Apex GIF Maker</b>")
        title.setStyleSheet("QLabel{font-size:16px;}")
        header.addWidget(self.lbl_logo)
        header.addWidget(title)
        header.addStretch(1)
        root.addLayout(header)

        # File row
        file_box = QHBoxLayout()
        self.le_video = QLineEdit()
        self.le_video.setPlaceholderText("동영상 파일 경로 (mp4 등)")
        btn_browse = QPushButton("열기…")
        btn_browse.clicked.connect(self._browse_video)
        file_box.addWidget(QLabel("입력 비디오:"))
        file_box.addWidget(self.le_video, 1)
        file_box.addWidget(btn_browse)

        meta_box = QHBoxLayout()
        self.lbl_duration = QLabel("길이: -")
        self.lbl_tools = QLabel(self._tools_label_text())
        meta_box.addWidget(self.lbl_duration)
        meta_box.addStretch(1)
        meta_box.addWidget(self.lbl_tools)

        # Trim group
        trim_group = QGroupBox("구간 선택 — 최소 2초, 최대 10초 (슬라이더 드래그 또는 시간 직접 입력)")
        tg = QGridLayout(trim_group)

        self.range = RangeSlider()
        self.range.setRange(0.0, 0.1)
        self.range.changed.connect(self._on_range_changed)

        self.le_start = QLineEdit("00:00.000")
        self.le_end = QLineEdit("00:02.000")
        for le in (self.le_start, self.le_end):
            le.setPlaceholderText("mm:ss.mmm 또는 hh:mm:ss.mmm")
            le.editingFinished.connect(self._apply_edits_to_range)

        self.btn_prev_start = QPushButton("시작 프레임")
        self.btn_prev_end = QPushButton("끝 프레임")
        self.btn_prev_start.clicked.connect(self._update_split_preview)
        self.btn_prev_end.clicked.connect(self._update_split_preview)

        # split previews
        self.lbl_prev_start = QLabel("시작 프리뷰")
        self.lbl_prev_end   = QLabel("끝 프리뷰")
        self.lbl_prev_start.setAlignment(Qt.AlignCenter)
        self.lbl_prev_end.setAlignment(Qt.AlignCenter)
        for _lbl in (self.lbl_prev_start, self.lbl_prev_end):
            _lbl.setMinimumHeight(420)
            _lbl.setStyleSheet("QLabel{border:1px solid #555; background:#111; color:#bbb;}")

        # timeline thumbnails area
        self.timeline_area = QScrollArea()
        self.timeline_area.setWidgetResizable(True)
        self.timeline_inner = QWidget()
        self.timeline_layout = QHBoxLayout(self.timeline_inner)
        self.timeline_layout.setContentsMargins(4,4,4,4)
        our_spacing = 4
        self.timeline_layout.setSpacing(our_spacing)
        self.timeline_area.setWidget(self.timeline_inner)

        tg.addWidget(self.range, 0, 0, 1, 6)
        tg.addWidget(self.timeline_area, 1, 0, 1, 6)
        tg.addWidget(QLabel("시작:"), 2, 0)
        tg.addWidget(self.le_start, 2, 1)
        tg.addWidget(QLabel("끝:"), 2, 2)
        tg.addWidget(self.le_end,   2, 3)
        tg.addWidget(self.btn_prev_start, 2, 4)
        tg.addWidget(self.btn_prev_end,   2, 5)

        split = QHBoxLayout()
        split.addWidget(self.lbl_prev_start)
        split.addWidget(self.lbl_prev_end)
        tg.addLayout(split, 3, 0, 1, 6)

        # Options
        opt_group = QGroupBox("옵션")
        og = QGridLayout(opt_group)
        self.combo_mode = QComboBox(); self.combo_mode.addItems(["자동(균등)", "자동(중복 제거)", "수동 선택"])
        self.spin_fps = QSpinBox(); self.spin_fps.setRange(1, 60); self.spin_fps.setValue(DEFAULT_FPS)
        self.spin_w = QSpinBox();   self.spin_w.setRange(8, 1024); self.spin_w.setValue(DEFAULT_WIDTH)
        self.spin_h = QSpinBox();   self.spin_h.setRange(8, 1024); self.spin_h.setValue(DEFAULT_HEIGHT)
        self.combo_scale = QComboBox()
        self.combo_scale.addItems(["레터박스(비율 유지)", "꽉 채우기(크롭)", "스트레치(왜곡)"])
        self.combo_scale.setCurrentIndex(1)  # 기본: 꽉 채우기
        self.combo_dither = QComboBox(); self.combo_dither.addItems(["floyd_steinberg", "bayer", "none"])
        og.addWidget(QLabel("모드:"), 0, 0); og.addWidget(self.combo_mode, 0, 1)
        og.addWidget(QLabel("FPS:"),  0, 2); og.addWidget(self.spin_fps,   0, 3)
        og.addWidget(QLabel("가로:"), 0, 4); og.addWidget(self.spin_w,     0, 5)
        og.addWidget(QLabel("세로:"), 0, 6); og.addWidget(self.spin_h,     0, 7)
        og.addWidget(QLabel("스케일:"), 1, 0); og.addWidget(self.combo_scale, 1, 1, 1, 3)
        og.addWidget(QLabel("디더링:"), 1, 4); og.addWidget(self.combo_dither, 1, 5)

        # Manual picker
        manual_group = QGroupBox("프레임 선택(수동 모드)")
        mg = QVBoxLayout(manual_group)
        top_bar = QHBoxLayout()
        self.btn_scan = QPushButton("구간에서 프레임 스캔")
        self.btn_scan.clicked.connect(self._scan_frames)
        self.spin_scan_fps = QSpinBox(); self.spin_scan_fps.setRange(1, 30); self.spin_scan_fps.setValue(10)
        btn_all = QPushButton("전체 선택/해제"); btn_all.clicked.connect(self._toggle_all_frames)
        top_bar.addWidget(QLabel("스캔 FPS:")); top_bar.addWidget(self.spin_scan_fps)
        top_bar.addStretch(1); top_bar.addWidget(self.btn_scan); top_bar.addWidget(btn_all)
        self.list_frames = QListWidget()
        self.list_frames.setViewMode(QListView.IconMode)
        self.list_frames.setIconSize(QSize(192,108))
        self.list_frames.setResizeMode(QListView.Adjust)
        self.list_frames.setSpacing(6)
        self.list_frames.setMinimumHeight(220)
        mg.addLayout(top_bar)
        mg.addWidget(self.list_frames)

        # Output
        out_box = QHBoxLayout()
        self.le_out = QLineEdit()
        self.le_out.setPlaceholderText(str(APP_DIR / "output.gif"))
        btn_out = QPushButton("저장 위치…")
        btn_out.clicked.connect(self._choose_output)
        out_box.addWidget(QLabel("출력:"))
        out_box.addWidget(self.le_out, 1)
        out_box.addWidget(btn_out)

        # Run
        run_box = QHBoxLayout()
        self.btn_generate = QPushButton("GIF 생성")
        self.btn_generate.clicked.connect(self._generate_gif)
        run_box.addStretch(1)
        run_box.addWidget(self.btn_generate)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setPlaceholderText("로그")

        # assemble
        root.addLayout(file_box)
        root.addLayout(meta_box)
        root.addWidget(trim_group)
        root.addWidget(opt_group)
        root.addWidget(manual_group)
        root.addLayout(out_box)
        root.addLayout(run_box)
        root.addWidget(self.log, 1)

        manual_group.setVisible(self.combo_mode.currentIndex()==2)
        self.combo_mode.currentIndexChanged.connect(lambda i: manual_group.setVisible(i==2))

    # ----- Tools / FFmpeg setup -----
    def _tools_label_text(self):
        ffn = Path(self.ffmpeg_path).name if self.ffmpeg_path else '미설정'
        fpn = Path(self.ffprobe_path).name if self.ffprobe_path else '미설정'
        return f"ffmpeg: {ffn} | ffprobe: {fpn}"

    def _append_log(self, t: str):
        self.log.append(t)

    def _select_tools(self):
        ffmpeg, _ = QFileDialog.getOpenFileName(self, "ffmpeg 실행 파일 선택", "", "Executable (*)")
        if ffmpeg:
            self.ffmpeg_path = ffmpeg
        ffprobe, _ = QFileDialog.getOpenFileName(self, "ffprobe 실행 파일 선택", "", "Executable (*)")
        if ffprobe:
            self.ffprobe_path = ffprobe
        self.lbl_tools.setText(self._tools_label_text())

    def _download(self, url: str, dest_path: Path) -> bool:
        try:
            with urllib.request.urlopen(url) as resp, open(dest_path, "wb") as out:
                total = int(resp.headers.get("Content-Length", "0") or 0)
                read = 0
                while True:
                    chunk = resp.read(1024*256)
                    if not chunk:
                        break
                    out.write(chunk)
                    read += len(chunk)
                    if total:
                        self._append_log(f"[DL] {int(read*100/total)}%")
            self._append_log("[DL] 완료")
            return True
        except Exception as e:
            self._append_log(f"[DL] 오류: {e}")
            return False

    def _auto_setup_tools(self):
        self.ffmpeg_path = find_executable("ffmpeg")
        self.ffprobe_path = find_executable("ffprobe")
        if self.ffmpeg_path and self.ffprobe_path:
            self._append_log("[INFO] ffmpeg/ffprobe 준비됨")
            self.lbl_tools.setText(self._tools_label_text())
            return
        os_name = platform.system().lower()
        if "windows" in os_name:
            self._setup_windows_ffmpeg()
        elif "darwin" in os_name or "mac" in os_name:
            self._setup_macos_ffmpeg()
        elif "linux" in os_name:
            self._setup_linux_ffmpeg()
        else:
            self._append_log("[WARN] 미지원 OS. 수동 설치 필요.")
        self.ffmpeg_path = find_executable("ffmpeg")
        self.ffprobe_path = find_executable("ffprobe")
        self.lbl_tools.setText(self._tools_label_text())

    def _setup_windows_ffmpeg(self):
        candidates = [
            "https://github.com/GyanD/codexffmpeg/releases/latest/download/ffmpeg-essentials_build.zip",
            "https://github.com/GyanD/codexffmpeg/releases/latest/download/ffmpeg-release-essentials.zip",
            "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip",
        ]
        zip_path = FFMPEG_DIR / "ffmpeg-essentials.zip"
        for url in candidates:
            self._append_log(f"[DL] {url}")
            if not self._download(url, zip_path):
                continue
            try:
                with zipfile.ZipFile(zip_path, 'r') as zf:
                    zf.extractall(FFMPEG_DIR)
                ffmpeg = None
                ffprobe = None
                for p in FFMPEG_DIR.rglob("*"):
                    if p.name.lower() == "ffmpeg.exe":
                        ffmpeg = str(p.resolve())
                    elif p.name.lower() == "ffprobe.exe":
                        ffprobe = str(p.resolve())
                if ffmpeg and ffprobe:
                    shutil.copy2(ffmpeg, FFMPEG_DIR / "ffmpeg.exe")
                    shutil.copy2(ffprobe, FFMPEG_DIR / "ffprobe.exe")
                    self._append_log(f"[OK] ffmpeg 준비: {FFMPEG_DIR/'ffmpeg.exe'}")
                    self._append_log(f"[OK] ffprobe 준비: {FFMPEG_DIR/'ffprobe.exe'}")
                    self._tidy_ffmpeg_dir()
                    return
            except Exception as e:
                self._append_log(f"[ERR] ZIP 추출 실패: {e}")
        self._append_log("[ERR] ffmpeg 자동 준비 실패")

    def _setup_macos_ffmpeg(self):
        brew = shutil.which("brew")
        if brew:
            self._append_log("[INFO] macOS: brew install ffmpeg")
            try:
                run_quiet([brew, "install", "ffmpeg"])
            except Exception as e:
                self._append_log(f"[ERR] brew 실패: {e}")
        else:
            self._append_log("[WARN] Homebrew 미설치. 수동 설치 필요.")

    def _setup_linux_ffmpeg(self):
        apt = shutil.which("apt-get")
        if apt:
            self._append_log("[INFO] Linux: apt-get install ffmpeg")
            try:
                run_quiet(["sudo","apt-get","update"])
                run_quiet(["sudo","apt-get","-y","install","ffmpeg"])
            except Exception as e:
                self._append_log(f"[ERR] apt-get 실패: {e}")
        if not find_executable("ffmpeg") or not find_executable("ffprobe"):
            arch = platform.machine().lower()
            if arch in ("x86_64","amd64"):
                url = "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"
            elif arch in ("aarch64","arm64"):
                url = "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-arm64-static.tar.xz"
            else:
                self._append_log(f"[WARN] 미지원 아키텍처({arch}).")
                return
            tar_path = FFMPEG_DIR / Path(url).name
            if self._download(url, tar_path):
                try:
                    with tarfile.open(tar_path, 'r:*') as tf:
                        tf.extractall(FFMPEG_DIR)
                    ffmpeg = None
                    ffprobe = None
                    for p in FFMPEG_DIR.rglob("*"):
                        if p.name == "ffmpeg":
                            ffmpeg = str(p.resolve())
                        elif p.name == "ffprobe":
                            ffprobe = str(p.resolve())
                    if ffmpeg and ffprobe:
                        shutil.copy2(ffmpeg, FFMPEG_DIR/"ffmpeg")
                        shutil.copy2(ffprobe, FFMPEG_DIR/"ffprobe")
                        os.chmod(FFMPEG_DIR/"ffmpeg", 0o755)
                        os.chmod(FFMPEG_DIR/"ffprobe", 0o755)
                        self._append_log("[OK] 정적 빌드 준비 완료")
                        self._tidy_ffmpeg_dir()
                except Exception as e:
                    self._append_log(f"[ERR] 정적 빌드 추출 실패: {e}")

    def _tidy_ffmpeg_dir(self):
        """ffmpeg-bin 폴더에서 ffmpeg(.exe)/ffprobe(.exe)만 남기고 나머지 삭제"""
        try:
            keep = {"ffmpeg.exe", "ffprobe.exe"} if os.name == "nt" else {"ffmpeg", "ffprobe"}
            if not all((FFMPEG_DIR / k).exists() for k in keep):
                self._append_log("[WARN] ffmpeg-bin 정리 보류: 필수 실행 파일 누락")
                return
            for p in FFMPEG_DIR.iterdir():
                if p.name in keep:
                    continue
                try:
                    if p.is_dir():
                        shutil.rmtree(p, onerror=_onerror_chmod)
                    else:
                        p.unlink()
                except Exception as e:
                    self._append_log(f"[WARN] 삭제 실패: {p.name} ({e})")
            self._append_log("[OK] ffmpeg-bin 정리 완료 (ffmpeg/ffprobe만 유지)")
        except Exception as e:
            self._append_log(f"[ERR] ffmpeg-bin 정리 중 오류: {e}")

    # ----- Load & Trim -----
    def _browse_video(self):
        path, _ = QFileDialog.getOpenFileName(self, "비디오 파일 선택", "", "Videos (*.mp4 *.mov *.mkv *.webm *.avi);;All files (*.*)")
        if not path:
            return
        self.le_video.setText(path)
        self._load_video(path)

    def _load_video(self, path: str):
        if not Path(path).is_file():
            QMessageBox.warning(self, "오류", "파일이 존재하지 않습니다.")
            return
        if not self.ffprobe_path:
            QMessageBox.warning(self, "오류", "ffprobe 준비가 필요합니다.")
            return
        try:
            dur = probe_duration_sec(self.ffprobe_path, path)
            self.duration_sec = dur
            self.video_path = path
            self.lbl_duration.setText(f"길이: {seconds_to_hhmmss(dur)} ({dur:.3f}s)")
            hi = (min(TRIM_MIN_SEC, dur) if dur >= TRIM_MIN_SEC else dur) / max(1e-9, dur)
            self.range.setRange(0.0, hi)
            self._apply_trim_constraints(adjust='end')
            self._update_time_edits()
            self._build_timeline_thumbs()
            self._update_split_preview()
            self._append_log(f"[OK] 동영상 로드: {path}")
        except Exception as e:
            QMessageBox.critical(self, "오류", f"동영상 정보를 읽는 중 문제 발생:\n{e}")
            self._append_log(f"[ERR] ffprobe 실패: {e}")

    def _on_range_changed(self, lo: float, hi: float):
        self._apply_trim_constraints()
        self._update_time_edits()
        self.preview_timer.start()

    def _apply_trim_constraints(self, adjust='auto'):
        if self.duration_sec <= 0:
            return
        lo = self.range.lower() * self.duration_sec
        hi = self.range.upper() * self.duration_sec
        span = hi - lo
        if span < TRIM_MIN_SEC:
            need = TRIM_MIN_SEC - span
            if adjust=='end' or (adjust=='auto' and hi+need <= self.duration_sec):
                hi = min(self.duration_sec, hi+need)
            else:
                lo = max(0.0, lo-need)
        if span > TRIM_MAX_SEC:
            cut = span - TRIM_MAX_SEC
            if adjust=='end' or (adjust=='auto' and hi-cut >= 0):
                hi -= cut
            else:
                lo += cut
        self.range.setRange(lo/max(1e-9,self.duration_sec), hi/max(1e-9,self.duration_sec), emit_signal=False)

    def _update_time_edits(self):
        lo = self.range.lower()*self.duration_sec
        hi = self.range.upper()*self.duration_sec
        self.le_start.setText(seconds_to_hhmmss(lo))
        self.le_end.setText(seconds_to_hhmmss(hi))

    def _apply_edits_to_range(self):
        if self.duration_sec <= 0:
            return
        try:
            lo = hhmmss_to_seconds(self.le_start.text())
            hi = hhmmss_to_seconds(self.le_end.text())
        except Exception:
            QMessageBox.warning(self, "오류", "시간 형식이 올바르지 않습니다.")
            self._update_time_edits()
            return
        lo = max(0.0, lo)
        hi = min(self.duration_sec, hi)
        if hi <= lo:
            hi = min(self.duration_sec, lo + TRIM_MIN_SEC)
        span = hi - lo
        if span < TRIM_MIN_SEC:
            hi = min(self.duration_sec, lo + TRIM_MIN_SEC)
        if span > TRIM_MAX_SEC:
            hi = lo + TRIM_MAX_SEC if lo + TRIM_MAX_SEC <= self.duration_sec else self.duration_sec
            lo = max(0.0, hi - TRIM_MAX_SEC)
        self.range.setRange(lo/max(1e-9,self.duration_sec), hi/max(1e-9,self.duration_sec))

    # ----- Preview / Timeline -----
    def _update_split_preview(self):
        if not self.video_path or not self.ffmpeg_path:
            return
        try:
            p1 = extract_preview_frame(self.ffmpeg_path, self.video_path, self.range.lower()*self.duration_sec)
            p2 = extract_preview_frame(self.ffmpeg_path, self.video_path, self.range.upper()*self.duration_sec)
            pix1 = QPixmap(str(p1)).scaled(self.lbl_prev_start.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            pix2 = QPixmap(str(p2)).scaled(self.lbl_prev_end.size(),   Qt.KeepAspectRatio, Qt.SmoothTransformation)
            if not pix1.isNull():
                self.lbl_prev_start.setPixmap(pix1)
            if not pix2.isNull():
                self.lbl_prev_end.setPixmap(pix2)
        except Exception as e:
            self._append_log(f"[ERR] 미리보기 업데이트 실패: {e}")

    def _build_timeline_thumbs(self):
        thumbs_dir = CACHE_DIR / "timeline"
        if thumbs_dir.exists():
            for p in thumbs_dir.glob("thumb_*.png"):
                try:
                    p.unlink()
                except Exception:
                    pass
        else:
            thumbs_dir.mkdir(parents=True, exist_ok=True)
        if not self.video_path or not self.ffmpeg_path or self.duration_sec <= 0:
            return
        cmd = [self.ffmpeg_path, "-hide_banner", "-loglevel", "error", "-i", self.video_path,
               "-vf", "fps=1/2,scale=160:-1:flags=lanczos", str(thumbs_dir / "thumb_%05d.png")]
        self._append_log("[RUN] 타임라인 썸네일 생성: " + " ".join(map(str, cmd)))
        run_quiet(cmd)

        while self.timeline_layout.count():
            item = self.timeline_layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
        for fp in sorted(thumbs_dir.glob("thumb_*.png")):
            lb = QLabel()
            lb.setPixmap(QPixmap(str(fp)).scaled(96,54, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            lb.setToolTip(fp.name)
            self.timeline_layout.addWidget(lb)
        self.timeline_layout.addStretch(1)

    # ----- Manual frames -----
    def _clear_frames_dir(self, d: Path):
        if d.exists():
            for p in d.glob("*.png"):
                try:
                    p.unlink()
                except Exception:
                    pass
        else:
            d.mkdir(parents=True, exist_ok=True)

    def _scan_frames(self):
        if not self.video_path or not self.ffmpeg_path:
            QMessageBox.warning(self, "오류", "비디오 또는 ffmpeg가 준비되지 않았습니다.")
            return
        if self.combo_mode.currentIndex() != 2:
            QMessageBox.information(self, "안내", "수동 선택 모드에서 사용하세요.")
            return
        scan_fps = self.spin_scan_fps.value()
        lo = self.range.lower()*self.duration_sec
        hi = self.range.upper()*self.duration_sec
        duration = max(0.0, hi-lo)
        if duration <= 0:
            QMessageBox.warning(self, "오류", "구간이 올바르지 않습니다.")
            return
        frames_dir = CACHE_DIR / "frames"
        self._clear_frames_dir(frames_dir)
        cmd = [self.ffmpeg_path, "-hide_banner", "-loglevel", "error",
               "-ss", f"{lo:.3f}", "-t", f"{duration:.3f}",
               "-i", self.video_path,
               "-vf", f"fps={scan_fps},scale=384:216:flags=lanczos",
               str(frames_dir / "frame_%04d.png")]
        self._append_log("[RUN] 프레임 스캔: " + " ".join(map(str, cmd)))
        proc = run_quiet(cmd)
        if proc.returncode != 0:
            self._append_log(proc.stderr.strip())
            QMessageBox.critical(self, "오류", "프레임 추출 실패")
            return
        self.list_frames.clear()
        for fp in sorted(frames_dir.glob("frame_*.png")):
            item = QListWidgetItem()
            item.setText(fp.name)
            pix = QPixmap(str(fp)).scaled(self.list_frames.iconSize(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            item.setIcon(pix)
            item.setCheckState(Qt.Checked)
            self.list_frames.addItem(item)
        self._append_log(f"[OK] 스캔 완료: {self.list_frames.count()} 프레임")

    def _toggle_all_frames(self):
        any_unchecked = any(self.list_frames.item(i).checkState()==Qt.Unchecked for i in range(self.list_frames.count()))
        new_state = Qt.Checked if any_unchecked else Qt.Unchecked
        for i in range(self.list_frames.count()):
            self.list_frames.item(i).setCheckState(new_state)

    # ----- Output / Generate -----
    def _choose_output(self):
        default_name = str(APP_DIR / "output.gif")
        path, _ = QFileDialog.getSaveFileName(self, "출력 GIF 저장", default_name, "GIF (*.gif)")
        if path:
            if not path.lower().endswith(".gif"):
                path += ".gif"
            self.le_out.setText(path)

    def _ensure_tools(self) -> bool:
        if not self.ffmpeg_path or not Path(self.ffmpeg_path).exists():
            self._append_log("[ERR] ffmpeg 경로를 찾을 수 없습니다.")
            return False
        if not self.ffprobe_path or not Path(self.ffprobe_path).exists():
            self._append_log("[ERR] ffprobe 경로를 찾을 수 없습니다.")
            return False
        return True

    def _generate_gif(self):
        if not self._ensure_tools():
            QMessageBox.warning(self, "오류", "ffmpeg/ffprobe 준비가 필요합니다.")
            return
        if not self.video_path:
            QMessageBox.warning(self, "오류", "먼저 비디오를 불러오세요.")
            return

        lo = self.range.lower()*self.duration_sec
        hi = self.range.upper()*self.duration_sec
        duration = max(0.0, hi-lo)
        if duration < TRIM_MIN_SEC or duration > TRIM_MAX_SEC:
            QMessageBox.warning(self, "오류", f"구간은 {TRIM_MIN_SEC:.0f}~{TRIM_MAX_SEC:.0f}초여야 합니다.")
            return

        fps = self.spin_fps.value()
        w, h = self.spin_w.value(), self.spin_h.value()
        mode = ["letterbox","cover","stretch"][self.combo_scale.currentIndex()]
        dither = self.combo_dither.currentText()

        out_path = self.le_out.text().strip()
        if not out_path:
            base = Path(self.video_path).with_suffix("")
            out_path = str(APP_DIR / f"{Path(base).name}_{int(lo*1000)}_{int(hi*1000)}.gif")
            self.le_out.setText(out_path)

        mode_idx = self.combo_mode.currentIndex()
        if mode_idx in (0,1):
            alg = "even" if mode_idx==0 else "mpdecimate"
            cmds = build_gif_commands_auto(self.ffmpeg_path, self.video_path, lo, hi, fps, w, h, mode, alg, dither, out_path)
        else:
            frames_dir = CACHE_DIR / "frames_selected"
            self._clear_frames_dir(frames_dir)
            src_dir = CACHE_DIR / "frames"
            files = [src_dir / self.list_frames.item(i).text() for i in range(self.list_frames.count())
                     if self.list_frames.item(i).checkState()==Qt.Checked]
            if not files:
                QMessageBox.warning(self, "오류", "선택된 프레임이 없습니다.")
                return
            for idx, fp in enumerate(files, start=1):
                shutil.copy2(fp, frames_dir / f"frame_{idx:04d}.png")
            cmds = build_gif_commands_manual(self.ffmpeg_path, frames_dir, fps, w, h, mode, dither, out_path)

        self.btn_generate.setEnabled(False)
        self._append_log("[RUN] GIF 생성 시작")
        for i, cmd in enumerate(cmds, start=1):
            self._append_log(f"[RUN] Pass {i}: {' '.join(map(str, cmd))}")
            proc = run_quiet(cmd)
            if proc.stdout.strip():
                self._append_log(proc.stdout.strip())
            if proc.stderr.strip():
                self._append_log(proc.stderr.strip())
            if proc.returncode != 0:
                QMessageBox.critical(self, "오류", f"ffmpeg 실행 실패 (Pass {i}). 로그 확인.")
                self._append_log(f"[ERR] 코드={proc.returncode}")
                self.btn_generate.setEnabled(True)
                return

        if Path(out_path).is_file():
            self._append_log(f"[OK] 완료: {out_path}")
            QMessageBox.information(self, "완료", f"GIF 생성 완료:\n{out_path}")
        else:
            self._append_log("[ERR] 출력 파일을 찾을 수 없습니다.")
            QMessageBox.warning(self, "경고", "출력 파일을 찾을 수 없습니다.")

        self._tidy_ffmpeg_dir()
        self.btn_generate.setEnabled(True)

# ---------- Entrypoint ----------
def main():
    _set_win_appusermodel_id("ApexGIFMaker")                 # 작업표시줄/핀 아이콘 식별 고정
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True) # HiDPI 아이콘 선명도

    app = QApplication(sys.argv)

    app_icon = get_app_icon()
    if not app_icon.isNull():
        app.setWindowIcon(app_icon)

    w = MainWindow()
    if not app_icon.isNull():
        w.setWindowIcon(app_icon)
    w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
