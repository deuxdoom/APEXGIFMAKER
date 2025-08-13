# APEXGIFMAKER
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apex GIF Maker (MP4 → GIF) — v2.0.0 (Light UI Revamp)
요청 반영:
1) ffmpeg/ffprobe 경로 표시는 UI에서 제거(내부 준비/설정은 유지)
2) 화이트 베이스 프리미엄 QSS(라운드/호버/그라디언트) 적용
3) 구간 길이 실시간 배지 + 권장 3~4초 색상 피드백
4) 메시지박스(완료/오류 등) 화이트 테마 강제
5) 종료 버튼 클릭 시 “종료하시겠습니까? 예/아니오” 확인창
6) 내장 아이콘 Base64는 icon.py로 분리(import 사용)
"""

import os
import sys
import stat
import json
import shutil
import subprocess
import platform
import urllib.request
import zipfile
import tarfile
from pathlib import Path

from PySide6.QtCore import Qt, QSize, QRect, Signal, QTimer, QUrl
from PySide6.QtGui import QAction, QPixmap, QPainter, QColor, QIcon, QDesktopServices
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFileDialog,
    QLabel, QLineEdit, QSpinBox, QComboBox, QPushButton,
    QGroupBox, QGridLayout, QVBoxLayout, QHBoxLayout, QTextEdit,
    QListWidget, QListWidgetItem, QListView, QScrollArea, QFrame, QMessageBox
)

# 아이콘 모듈(분리)
try:
    from icon import get_app_icon
except Exception:
    def get_app_icon() -> QIcon:
        return QIcon()

APP_TITLE   = "Apex GIF Maker (MP4 → GIF)"
APP_VERSION = "2.0.0"
REPO_OWNER  = "deuxdoom"
REPO_NAME   = "APEXGIFMAKER"
GITHUB_API_LATEST  = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/latest"
GITHUB_HTML_LATEST = f"https://github.com/{REPO_OWNER}/{REPO_NAME}/releases/latest"

DEFAULT_WIDTH = 160
DEFAULT_HEIGHT = 80
DEFAULT_FPS = 24
TRIM_MIN_SEC = 2.0
TRIM_MAX_SEC = 6.0
RECO_MIN = 3.0
RECO_MAX = 4.0

ACCENT      = "#2563eb"   # 버튼/강조 파랑
ACCENT_HOV  = "#1d4ed8"
ACCENT_SUB  = "#e2e8f0"   # 테두리 연회색
GOOD_GREEN  = "#059669"
WARN_AMBER  = "#d97706"
TEXT_DARK   = "#0f172a"

# ──────────────────────────────
# 경로 / 폴더
# ──────────────────────────────
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

# ──────────────────────────────
# 라이트 QSS (프리미엄 톤)
# ──────────────────────────────
LIGHT_QSS = f"""
QMainWindow {{
    background: #f8fafc;
}}
QGroupBox {{
    background: #ffffff;
    border: 1px solid {ACCENT_SUB};
    border-radius: 10px;
    margin-top: 12px;
}}
QGroupBox::title {{
    subcontrol-origin: margin; left: 12px; padding: 0 6px;
    color: {TEXT_DARK}; font-weight: 600;
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #ffffff, stop:1 #f8fafc);
}}
QLabel {{
    color: {TEXT_DARK};
}}
QLineEdit, QSpinBox, QComboBox, QTextEdit {{
    background: #ffffff; color: {TEXT_DARK};
    border: 1px solid {ACCENT_SUB}; border-radius: 8px; padding: 6px 8px;
}}
QTextEdit {{ font-family: Consolas, Menlo, monospace; }}
QPushButton {{
    border-radius: 10px; padding: 8px 14px; font-weight: 600;
    background: #ffffff; color: {TEXT_DARK}; border: 1px solid {ACCENT_SUB};
}}
QPushButton:hover {{ background: #f1f5f9; }}
QPushButton#PrimaryButton {{
    background: {ACCENT}; color: #ffffff; border: 1px solid {ACCENT};
}}
QPushButton#PrimaryButton:hover {{ background: {ACCENT_HOV}; border-color: {ACCENT_HOV}; }}
QScrollArea {{
    background: #ffffff; border: 1px solid {ACCENT_SUB}; border-radius: 8px;
}}
#HeaderCard {{
    background: #ffffff; border: 1px solid {ACCENT_SUB}; border-radius: 12px;
}}
#PreviewPane {{
    border: 1px solid {ACCENT_SUB}; border-radius: 10px;
    background: #f1f5f9; color: #64748b;
}}
#DurationBadge {{
    border-radius: 14px; padding: 6px 10px; font-weight: 700;
    background: #eef2ff; color: {ACCENT};
}}
"""

# ──────────────────────────────
# 시간 유틸
# ──────────────────────────────
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

# ──────────────────────────────
# 조용한 subprocess
# ──────────────────────────────
def run_quiet(cmd):
    kw = dict(capture_output=True, text=True)
    if os.name == "nt":
        kw["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        kw["startupinfo"] = si
    return subprocess.run(cmd, **kw)

# ──────────────────────────────
# ffmpeg 헬퍼
# ──────────────────────────────
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

def _onerror_chmod(func, path, excinfo):
    try:
        os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
        func(path)
    except Exception:
        pass

# ──────────────────────────────
# RangeSlider (화이트 톤)
# ──────────────────────────────
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
        p.setPen(Qt.NoPen); p.setBrush(QColor("#e5e7eb")); p.drawRect(bar_rect)
        lpx = bar_rect.x() + int(bar_rect.width()*self._lower)
        upx = bar_rect.x() + int(bar_rect.width()*self._upper)
        sel_rect = QRect(lpx, bar_rect.y(), upx - lpx, bar_rect.height())
        p.setBrush(QColor(37, 99, 235)); p.drawRect(sel_rect)
        handle_w, handle_h = 10, 24
        p.setBrush(QColor("#ffffff")); p.setPen(QColor("#94a3b8"))
        p.drawRoundedRect(QRect(lpx- handle_w//2, bar_rect.center().y()-handle_h//2, handle_w, handle_h), 6, 6)
        p.drawRoundedRect(QRect(upx- handle_w//2, bar_rect.center().y()-handle_h//2, handle_w, handle_h), 6, 6)
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

# ──────────────────────────────
# 메인
# ──────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(1320, 880)

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

        QTimer.singleShot(3500, lambda: self._check_for_updates(manual=False))

    # ── 공통 팝업(화이트 스타일) ──────────────────────────
    def _msgbox(self, title: str, text: str, icon: str = "info",
                informative_text: str | None = None,
                buttons=QMessageBox.Ok, default=QMessageBox.Ok) -> int:
        m = QMessageBox(self)
        m.setWindowTitle(title)
        m.setText(text)
        if informative_text:
            m.setInformativeText(informative_text)
        if icon == "info":
            m.setIcon(QMessageBox.Information)
        elif icon == "warn":
            m.setIcon(QMessageBox.Warning)
        elif icon == "error":
            m.setIcon(QMessageBox.Critical)
        else:
            m.setIcon(QMessageBox.NoIcon)
        m.setStandardButtons(buttons)
        m.setDefaultButton(default)
        btn = m.button(QMessageBox.Yes)
        if btn: btn.setText("예")
        btn = m.button(QMessageBox.No)
        if btn: btn.setText("아니오")
        btn = m.button(QMessageBox.Ok)
        if btn: btn.setText("확인")
        btn = m.button(QMessageBox.Cancel)
        if btn: btn.setText("취소")
        # 화이트 팝업 스타일 강제
        m.setStyleSheet(f"""
            QMessageBox {{
                background: #ffffff;
            }}
            QLabel {{
                color: {TEXT_DARK};
            }}
            QPushButton {{
                border-radius: 8px; padding: 6px 12px; font-weight: 600;
                background: #ffffff; color: {TEXT_DARK}; border: 1px solid {ACCENT_SUB};
                min-width: 80px;
            }}
            QPushButton:hover {{
                background: #f1f5f9;
            }}
        """)
        return m.exec()

    def info(self, title, text, info=None): return self._msgbox(title, text, "info", info)
    def warn(self, title, text, info=None): return self._msgbox(title, text, "warn", info)
    def error(self, title, text, info=None): return self._msgbox(title, text, "error", info)
    def ask_yes_no(self, title, text, info=None) -> bool:
        ret = self._msgbox(title, text, "info", info, buttons=QMessageBox.Yes | QMessageBox.No, default=QMessageBox.Yes)
        return ret == QMessageBox.Yes

    # ── UI ───────────────────────────────────────────────
    def _build_ui(self):
        menu = self.menuBar().addMenu("설정")
        act_paths = QAction("도구 경로 설정(ffmpeg/ffprobe)", self); act_paths.triggered.connect(self._select_tools)
        act_dl    = QAction("ffmpeg 자동 준비(재실행)", self); act_dl.triggered.connect(self._auto_setup_tools)
        act_clean = QAction("ffmpeg 폴더 정리", self);        act_clean.triggered.connect(self._tidy_ffmpeg_dir)
        act_update= QAction("업데이트 확인…", self);           act_update.triggered.connect(lambda: self._check_for_updates(manual=True))
        for a in (act_paths, act_dl, act_clean, act_update):
            menu.addAction(a)

        central = QWidget(); root = QVBoxLayout(central); self.setCentralWidget(central)
        self.setStyleSheet(LIGHT_QSS)

        header = QHBoxLayout()
        card = QFrame(); card.setObjectName("HeaderCard")
        card_l = QHBoxLayout(card); card_l.setContentsMargins(14,10,14,10); card_l.setSpacing(12)
        logo = QLabel()
        ico = get_app_icon()
        if not ico.isNull():
            logo.setPixmap(ico.pixmap(28,28))
        title = QLabel("Apex GIF Maker"); title.setStyleSheet("font-size:18px; font-weight:800;")
        self.lbl_duration_badge = QLabel("선택 길이: -  • 권장 3~4초"); self.lbl_duration_badge.setObjectName("DurationBadge")
        card_l.addWidget(logo); card_l.addWidget(title); card_l.addStretch(1); card_l.addWidget(self.lbl_duration_badge)
        header.addWidget(card)
        root.addLayout(header)

        file_box = QHBoxLayout()
        self.le_video = QLineEdit(); self.le_video.setPlaceholderText("동영상 파일 경로 (mp4 등)")
        btn_browse = QPushButton("열기…"); btn_browse.clicked.connect(self._browse_video)
        file_box.addWidget(QLabel("입력 비디오:")); file_box.addWidget(self.le_video, 1); file_box.addWidget(btn_browse)
        root.addLayout(file_box)

        trim_group = QGroupBox("구간 선택 — 최소 2초, 최대 6초 (슬라이더 드래그 또는 시간 직접 입력)")
        tg = QGridLayout(trim_group)

        self.range = RangeSlider(); self.range.setRange(0.0, 0.1)
        self.range.changed.connect(self._on_range_changed)

        self.le_start = QLineEdit("00:00.000")
        self.le_end   = QLineEdit("00:02.000")
        for le in (self.le_start, self.le_end):
            le.setPlaceholderText("mm:ss.mmm 또는 hh:mm:ss.mmm")
            le.editingFinished.connect(self._apply_edits_to_range)

        self.btn_prev_start = QPushButton("시작 프레임")
        self.btn_prev_end   = QPushButton("끝 프레임")
        self.btn_prev_start.clicked.connect(self._update_split_preview)
        self.btn_prev_end.clicked.connect(self._update_split_preview)

        self.timeline_area = QScrollArea(); self.timeline_area.setWidgetResizable(True)
        self.timeline_inner = QWidget(); self.timeline_layout = QHBoxLayout(self.timeline_inner)
        self.timeline_layout.setContentsMargins(4,4,4,4); self.timeline_layout.setSpacing(4)
        self.timeline_area.setWidget(self.timeline_inner)

        self.lbl_prev_start = QLabel("시작 프리뷰"); self.lbl_prev_start.setObjectName("PreviewPane"); self.lbl_prev_start.setAlignment(Qt.AlignCenter)
        self.lbl_prev_end   = QLabel("끝 프리뷰");   self.lbl_prev_end.setObjectName("PreviewPane");   self.lbl_prev_end.setAlignment(Qt.AlignCenter)
        self.lbl_prev_start.setMinimumHeight(420); self.lbl_prev_end.setMinimumHeight(420)

        tg.addWidget(self.range, 0, 0, 1, 6)
        tg.addWidget(self.timeline_area, 1, 0, 1, 6)
        tg.addWidget(QLabel("시작:"), 2, 0); tg.addWidget(self.le_start, 2, 1)
        tg.addWidget(QLabel("끝:"),   2, 2); tg.addWidget(self.le_end,   2, 3)
        tg.addWidget(self.btn_prev_start, 2, 4)
        tg.addWidget(self.btn_prev_end,   2, 5)

        split = QHBoxLayout(); split.addWidget(self.lbl_prev_start); split.addWidget(self.lbl_prev_end)
        tg.addLayout(split, 3, 0, 1, 6)
        root.addWidget(trim_group)

        opt_group = QGroupBox("옵션")
        og = QGridLayout(opt_group)
        self.combo_mode = QComboBox(); self.combo_mode.addItems(["자동(균등)", "자동(중복 제거)", "수동 선택"])
        self.spin_fps   = QSpinBox();  self.spin_fps.setRange(1, 60); self.spin_fps.setValue(DEFAULT_FPS)
        self.spin_w     = QSpinBox();  self.spin_w.setRange(8, 1024); self.spin_w.setValue(DEFAULT_WIDTH)
        self.spin_h     = QSpinBox();  self.spin_h.setRange(8, 1024); self.spin_h.setValue(DEFAULT_HEIGHT)
        self.combo_scale  = QComboBox(); self.combo_scale.addItems(["레터박스(비율 유지)", "꽉 채우기(크롭)", "스트레치(왜곡)"])
        self.combo_scale.setCurrentIndex(1)
        self.combo_dither = QComboBox(); self.combo_dither.addItems(["floyd_steinberg", "bayer", "none"])
        og.addWidget(QLabel("모드:"), 0,0); og.addWidget(self.combo_mode, 0,1)
        og.addWidget(QLabel("FPS:"),  0,2); og.addWidget(self.spin_fps,   0,3)
        og.addWidget(QLabel("가로:"),  0,4); og.addWidget(self.spin_w,     0,5)
        og.addWidget(QLabel("세로:"),  0,6); og.addWidget(self.spin_h,     0,7)
        og.addWidget(QLabel("스케일:"),1,0); og.addWidget(self.combo_scale,1,1,1,3)
        og.addWidget(QLabel("디더링:"),1,4); og.addWidget(self.combo_dither,1,5)
        root.addWidget(opt_group)

        manual_group = QGroupBox("프레임 선택(수동 모드)")
        mg = QVBoxLayout(manual_group)
        top_bar = QHBoxLayout()
        self.btn_scan = QPushButton("구간에서 프레임 스캔"); self.btn_scan.clicked.connect(self._scan_frames)
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
        mg.addLayout(top_bar); mg.addWidget(self.list_frames)
        root.addWidget(manual_group)
        manual_group.setVisible(self.combo_mode.currentIndex()==2)
        self.combo_mode.currentIndexChanged.connect(lambda i: manual_group.setVisible(i==2))

        out_box = QHBoxLayout()
        self.le_out = QLineEdit(); self.le_out.setPlaceholderText(str(APP_DIR / "output.gif"))
        btn_out = QPushButton("저장 위치…"); btn_out.clicked.connect(self._choose_output)
        out_box.addWidget(QLabel("출력:")); out_box.addWidget(self.le_out, 1); out_box.addWidget(btn_out)
        root.addLayout(out_box)

        run_box = QHBoxLayout()
        self.btn_generate = QPushButton("GIF 생성"); self.btn_generate.setObjectName("PrimaryButton")
        self.btn_generate.clicked.connect(self._generate_gif)
        run_box.addStretch(1); run_box.addWidget(self.btn_generate)
        root.addLayout(run_box)

        self.log = QTextEdit(); self.log.setReadOnly(True); self.log.setPlaceholderText("로그")
        root.addWidget(self.log, 1)

    # ── 도구/설정 ────────────────────────────────────────
    def _append_log(self, t: str): self.log.append(t)

    def _select_tools(self):
        ffmpeg, _ = QFileDialog.getOpenFileName(self, "ffmpeg 실행 파일 선택", "", "Executable (*)")
        if ffmpeg: self.ffmpeg_path = ffmpeg
        ffprobe, _ = QFileDialog.getOpenFileName(self, "ffprobe 실행 파일 선택", "", "Executable (*)")
        if ffprobe: self.ffprobe_path = ffprobe

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

    def _auto_setup_tools(self):
        self.ffmpeg_path = find_executable("ffmpeg")
        self.ffprobe_path = find_executable("ffprobe")
        if self.ffmpeg_path and self.ffprobe_path:
            self._append_log("[INFO] ffmpeg/ffprobe 준비됨"); return
        os_name = platform.system().lower()
        if "windows" in os_name: self._setup_windows_ffmpeg()
        elif "darwin" in os_name or "mac" in os_name: self._setup_macos_ffmpeg()
        elif "linux" in os_name: self._setup_linux_ffmpeg()
        else: self._append_log("[WARN] 미지원 OS. 수동 설치 필요.")
        self.ffmpeg_path = find_executable("ffmpeg")
        self.ffprobe_path = find_executable("ffprobe")

    def _setup_windows_ffmpeg(self):
        candidates = [
            "https://github.com/GyanD/codexffmpeg/releases/latest/download/ffmpeg-essentials_build.zip",
            "https://github.com/GyanD/codexffmpeg/releases/latest/download/ffmpeg-release-essentials.zip",
            "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip",
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
                    self._append_log(f"[OK] ffmpeg 준비")
                    self._tidy_ffmpeg_dir()
                    return
            except Exception as e:
                self._append_log(f"[ERR] ZIP 추출 실패: {e}")
        self._append_log("[ERR] ffmpeg 자동 준비 실패")

    def _setup_macos_ffmpeg(self):
        brew = shutil.which("brew")
        if brew:
            try: run_quiet([brew, "install", "ffmpeg"])
            except Exception as e: self._append_log(f"[ERR] brew 실패: {e}")
        else: self._append_log("[WARN] Homebrew 미설치. 수동 설치 필요.")

    def _setup_linux_ffmpeg(self):
        apt = shutil.which("apt-get")
        if apt:
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
                self._append_log(f"[WARN] 미지원 아키텍처({arch})."); return
            tar_path = FFMPEG_DIR / Path(url).name
            if self._download(url, tar_path):
                try:
                    with tarfile.open(tar_path, 'r:*') as tf: tf.extractall(FFMPEG_DIR)
                    ffmpeg = None; ffprobe = None
                    for p in FFMPEG_DIR.rglob("*"):
                        if p.name == "ffmpeg": ffmpeg = str(p.resolve())
                        elif p.name == "ffprobe": ffprobe = str(p.resolve())
                    if ffmpeg and ffprobe:
                        shutil.copy2(ffmpeg, FFMPEG_DIR/"ffmpeg")
                        shutil.copy2(ffprobe, FFMPEG_DIR/"ffprobe")
                        os.chmod(FFMPEG_DIR/"ffmpeg", 0o755); os.chmod(FFMPEG_DIR/"ffprobe", 0o755)
                        self._append_log("[OK] 정적 빌드 준비 완료")
                        self._tidy_ffmpeg_dir()
                except Exception as e:
                    self._append_log(f"[ERR] 정적 빌드 추출 실패: {e}")

    def _tidy_ffmpeg_dir(self):
        try:
            keep = {"ffmpeg.exe", "ffprobe.exe"} if os.name == "nt" else {"ffmpeg", "ffprobe"}
            if not all((FFMPEG_DIR / k).exists() for k in keep):
                self._append_log("[WARN] ffmpeg-bin 정리 보류: 필수 실행 파일 누락"); return
            for p in FFMPEG_DIR.iterdir():
                if p.name in keep: continue
                try:
                    if p.is_dir(): shutil.rmtree(p, onerror=_onerror_chmod)
                    else: p.unlink()
                except Exception as e:
                    self._append_log(f"[WARN] 삭제 실패: {p.name} ({e})")
            self._append_log("[OK] ffmpeg-bin 정리 완료")
        except Exception as e:
            self._append_log(f"[ERR] ffmpeg-bin 정리 중 오류: {e}")

    # ── 업데이트 확인 ─────────────────────────────────────
    def _normalize_version(self, v: str) -> tuple:
        try:
            v = v.strip()
            if v.startswith(("v","V")): v = v[1:]
            parts = v.split("."); nums=[]
            for p in parts:
                num=""
                for ch in p:
                    if ch.isdigit(): num+=ch
                    else: break
                nums.append(int(num) if num else 0)
            while len(nums)<3: nums.append(0)
            return tuple(nums[:3])
        except Exception:
            return tuple()

    def _check_for_updates(self, manual: bool = False):
        try:
            req = urllib.request.Request(
                GITHUB_API_LATEST,
                headers={"User-Agent": f"ApexGIFMaker/{APP_VERSION}","Accept":"application/vnd.github+json"},
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8","ignore"))
            tag = str(data.get("tag_name","")).strip()
            if not tag:
                if manual: self.info("업데이트","업데이트 정보를 가져오지 못했습니다."); return
            cur = self._normalize_version(APP_VERSION); new = self._normalize_version(tag)
            if new and cur and new>cur:
                if self.ask_yes_no("업데이트", "새로운 버전이 나왔습니다.\n다운하러 이동하시겠습니까?", f"(현재: v{APP_VERSION} / 최신: {tag})"):
                    QDesktopServices.openUrl(QUrl(GITHUB_HTML_LATEST))
            else:
                if manual: self.info("업데이트","현재 최신 버전입니다.")
        except Exception as e:
            if manual: self.warn("업데이트", f"업데이트 확인 실패:\n{e}")

    # ── 로드/트림/프리뷰 ──────────────────────────────────
    def _browse_video(self):
        path, _ = QFileDialog.getOpenFileName(self, "비디오 파일 선택", "", "Videos (*.mp4 *.mov *.mkv *.webm *.avi);;All files (*.*)")
        if not path: return
        self.le_video.setText(path); self._load_video(path)

    def _load_video(self, path: str):
        if not Path(path).is_file():
            self.warn("오류","파일이 존재하지 않습니다."); return
        if not self.ffprobe_path:
            self.warn("오류","ffprobe 준비가 필요합니다."); return
        try:
            dur = probe_duration_sec(self.ffprobe_path, path)
            self.duration_sec = dur; self.video_path = path
            end = min(TRIM_MIN_SEC, self.duration_sec) if self.duration_sec >= TRIM_MIN_SEC else self.duration_sec
            hi = end / max(1e-9, self.duration_sec)
            self.range.setRange(0.0, hi)
            self._apply_trim_constraints(adjust='end')
            self._update_time_edits()
            self._build_timeline_thumbs()
            self._update_split_preview()
            self._update_duration_badge()
            self._append_log(f"[OK] 동영상 로드: {path}")
        except Exception as e:
            self.error("오류", f"동영상 정보를 읽는 중 문제 발생:\n{e}")
            self._append_log(f"[ERR] ffprobe 실패: {e}")

    def _on_range_changed(self, lo: float, hi: float):
        self._apply_trim_constraints()
        self._update_time_edits()
        self._update_duration_badge()
        self.preview_timer.start()

    def _apply_trim_constraints(self, adjust='auto'):
        if self.duration_sec <= 0: return
        lo = self.range.lower()*self.duration_sec
        hi = self.range.upper()*self.duration_sec
        span = hi-lo
        if span < TRIM_MIN_SEC:
            need = TRIM_MIN_SEC - span
            if adjust=='end' or (adjust=='auto' and hi+need<=self.duration_sec): hi=min(self.duration_sec, hi+need)
            else: lo=max(0.0, lo-need)
        if span > TRIM_MAX_SEC:
            cut = span-TRIM_MAX_SEC
            if adjust=='end' or (adjust=='auto' and hi-cut>=0): hi -= cut
            else: lo += cut
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
            self._update_time_edits()
            return
        lo = max(0.0, min(lo, self.duration_sec))
        hi = max(0.0, min(hi, self.duration_sec))
        if hi <= lo:
            hi = min(self.duration_sec, lo + TRIM_MIN_SEC)
        span = hi - lo
        if span < TRIM_MIN_SEC:
            hi = min(self.duration_sec, lo + TRIM_MIN_SEC)
        if span > TRIM_MAX_SEC:
            if lo + TRIM_MAX_SEC <= self.duration_sec:
                hi = lo + TRIM_MAX_SEC
            else:
                hi = self.duration_sec
                lo = max(0.0, hi - TRIM_MAX_SEC)
        self.range.setRange(lo / max(1e-9, self.duration_sec), hi / max(1e-9, self.duration_sec))
        self._update_duration_badge()
        self.preview_timer.start()

    def _update_duration_badge(self):
        if self.duration_sec <= 0:
            self.lbl_duration_badge.setText("선택 길이: -  • 권장 3~4초")
            self.lbl_duration_badge.setStyleSheet("")
            return
        lo = self.range.lower()*self.duration_sec
        hi = self.range.upper()*self.duration_sec
        span = hi - lo
        txt = f"선택 길이: {span:.3f}초  • 권장 3~4초"
        color = GOOD_GREEN if RECO_MIN <= span <= RECO_MAX else WARN_AMBER
        self.lbl_duration_badge.setText(txt)
        self.lbl_duration_badge.setStyleSheet(f"QLabel#DurationBadge {{ background:#ffffff; color:{color}; border:1px solid {ACCENT_SUB}; }}")

    def _update_split_preview(self):
        if not self.video_path or not self.ffmpeg_path: return
        try:
            p1 = extract_preview_frame(self.ffmpeg_path, self.video_path, self.range.lower()*self.duration_sec)
            p2 = extract_preview_frame(self.ffmpeg_path, self.video_path, self.range.upper()*self.duration_sec)
            pix1 = QPixmap(str(p1)).scaled(self.lbl_prev_start.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            pix2 = QPixmap(str(p2)).scaled(self.lbl_prev_end.size(),   Qt.KeepAspectRatio, Qt.SmoothTransformation)
            if not pix1.isNull(): self.lbl_prev_start.setPixmap(pix1)
            if not pix2.isNull(): self.lbl_prev_end.setPixmap(pix2)
        except Exception as e:
            self._append_log(f"[ERR] 미리보기 업데이트 실패: {e}")

    def _build_timeline_thumbs(self):
        thumbs_dir = CACHE_DIR / "timeline"
        if thumbs_dir.exists():
            for p in thumbs_dir.glob("thumb_*.png"):
                try: p.unlink()
                except Exception: pass
        else:
            thumbs_dir.mkdir(parents=True, exist_ok=True)
        if not self.video_path or not self.ffmpeg_path or self.duration_sec <= 0: return
        cmd = [self.ffmpeg_path, "-hide_banner", "-loglevel", "error", "-i", self.video_path,
               "-vf", "fps=1/2,scale=160:-1:flags=lanczos", str(thumbs_dir / "thumb_%05d.png")]
        self._append_log("[RUN] 타임라인 썸네일 생성: " + " ".join(map(str, cmd)))
        run_quiet(cmd)
        while self.timeline_layout.count():
            item = self.timeline_layout.takeAt(0)
            w = item.widget()
            if w: w.setParent(None)
        for fp in sorted(thumbs_dir.glob("thumb_*.png")):
            lb = QLabel(); lb.setObjectName("PreviewPane")
            lb.setPixmap(QPixmap(str(fp)).scaled(96,54, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            lb.setToolTip(fp.name)
            self.timeline_layout.addWidget(lb)
        self.timeline_layout.addStretch(1)

    # ── 수동 프레임 ───────────────────────────────────────
    def _clear_frames_dir(self, d: Path):
        if d.exists():
            for p in d.glob("*.png"):
                try: p.unlink()
                except Exception: pass
        else:
            d.mkdir(parents=True, exist_ok=True)

    def _scan_frames(self):
        if not self.video_path or not self.ffmpeg_path:
            self.warn("오류", "비디오 또는 ffmpeg가 준비되지 않았습니다."); return
        if self.combo_mode.currentIndex()!=2:
            self.info("안내", "수동 선택 모드에서 사용하세요."); return
        scan_fps = self.spin_scan_fps.value()
        lo = self.range.lower()*self.duration_sec
        hi = self.range.upper()*self.duration_sec
        duration = max(0.0, hi-lo)
        if duration <= 0:
            self.warn("오류", "구간이 올바르지 않습니다."); return
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
            self._append_log(proc.stderr.strip()); self.error("오류", "프레임 추출 실패"); return
        self.list_frames.clear()
        for fp in sorted(frames_dir.glob("frame_*.png")):
            item = QListWidgetItem()
            item.setText(fp.name)
            pix = QPixmap(str(fp)).scaled(self.list_frames.iconSize(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            item.setIcon(pix); item.setCheckState(Qt.Checked)
            self.list_frames.addItem(item)
        self._append_log(f"[OK] 스캔 완료: {self.list_frames.count()} 프레임")

    def _toggle_all_frames(self):
        any_unchecked = any(self.list_frames.item(i).checkState()==Qt.Unchecked for i in range(self.list_frames.count()))
        new_state = Qt.Checked if any_unchecked else Qt.Unchecked
        for i in range(self.list_frames.count()):
            self.list_frames.item(i).setCheckState(new_state)

    # ── 출력/생성 ─────────────────────────────────────────
    def _choose_output(self):
        default_name = str(APP_DIR / "output.gif")
        path, _ = QFileDialog.getSaveFileName(self,"출력 GIF 저장", default_name, "GIF (*.gif)")
        if path:
            if not path.lower().endswith(".gif"): path += ".gif"
            self.le_out.setText(path)

    def _ensure_tools(self) -> bool:
        if not self.ffmpeg_path or not Path(self.ffmpeg_path).exists():
            self._append_log("[ERR] ffmpeg 경로를 찾을 수 없습니다."); return False
        if not self.ffprobe_path or not Path(self.ffprobe_path).exists():
            self._append_log("[ERR] ffprobe 경로를 찾을 수 없습니다."); return False
        return True

    def _generate_gif(self):
        if not self._ensure_tools():
            self.warn("오류", "ffmpeg/ffprobe 준비가 필요합니다."); return
        if not self.video_path:
            self.warn("오류", "먼저 비디오를 불러오세요."); return

        lo = self.range.lower()*self.duration_sec
        hi = self.range.upper()*self.duration_sec
        duration = max(0.0, hi-lo)
        if duration < TRIM_MIN_SEC or duration > TRIM_MAX_SEC:
            self.warn("오류", f"구간은 {TRIM_MIN_SEC:.0f}~{TRIM_MAX_SEC:.0f}초여야 합니다."); return

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
                self.warn("오류", "선택된 프레임이 없습니다."); return
            for idx, fp in enumerate(files, start=1):
                shutil.copy2(fp, frames_dir / f"frame_{idx:04d}.png")
            cmds = build_gif_commands_manual(self.ffmpeg_path, frames_dir, fps, w, h, mode, dither, out_path)

        self.btn_generate.setEnabled(False)
        self._append_log("[RUN] GIF 생성 시작")
        for i, cmd in enumerate(cmds, start=1):
            self._append_log(f"[RUN] Pass {i}: {' '.join(map(str, cmd))}")
            proc = run_quiet(cmd)
            if proc.stdout.strip(): self._append_log(proc.stdout.strip())
            if proc.stderr.strip(): self._append_log(proc.stderr.strip())
            if proc.returncode != 0:
                self.error("오류", f"ffmpeg 실행 실패 (Pass {i}). 로그 확인.")
                self._append_log(f"[ERR] 코드={proc.returncode}")
                self.btn_generate.setEnabled(True); return

        if Path(out_path).is_file():
            self._append_log(f"[OK] 완료: {out_path}")
            self.info("완료", f"GIF 생성 완료:\n{out_path}")
        else:
            self._append_log("[ERR] 출력 파일을 찾을 수 없습니다.")
            self.warn("경고", "출력 파일을 찾을 수 없습니다.")

        self._tidy_ffmpeg_dir()
        self.btn_generate.setEnabled(True)

    # ── 종료 확인 ─────────────────────────────────────────
    def closeEvent(self, event):
        if self.ask_yes_no("종료", "프로그램을 종료하시겠습니까?"):
            event.accept()
        else:
            event.ignore()

# ──────────────────────────────
# 엔트리포인트
# ──────────────────────────────
def main():
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # 팝업/컨트롤 일관성
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
