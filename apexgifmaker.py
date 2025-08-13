# APEXGIFMAKER
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apex GIF Maker (MP4 → GIF) — v2.1.0
- 선택 구간 재생 버튼
- 권장 길이 3–6초, 최소/최대 1–15초
- 끝점 클릭 시 윈도우 리사이즈 방지
- 끝점 드래그도 시작점 연동(고정 길이 팬)
- KOR/ENG UI 토글
- 화이트 테마 + 라이트 콤보 팝업 + 화이트 메시지박스
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
from PySide6.QtGui import (
    QAction, QPixmap, QPainter, QColor, QIcon, QDesktopServices, QPalette
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFileDialog,
    QLabel, QLineEdit, QSpinBox, QComboBox, QPushButton,
    QGroupBox, QGridLayout, QVBoxLayout, QHBoxLayout, QTextEdit,
    QListWidget, QListWidgetItem, QListView, QScrollArea, QFrame, QMessageBox, QSizePolicy
)

# 아이콘 모듈 (없으면 빈 아이콘)
try:
    from icon import get_app_icon
except Exception:
    def get_app_icon() -> QIcon:
        return QIcon()

APP_TITLE   = "Apex GIF Maker (MP4 → GIF)"
APP_VERSION = "2.1.0"
REPO_OWNER  = "deuxdoom"
REPO_NAME   = "APEXGIFMAKER"
GITHUB_API_LATEST  = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/latest"
GITHUB_HTML_LATEST = f"https://github.com/{REPO_OWNER}/{REPO_NAME}/releases/latest"

DEFAULT_WIDTH = 160
DEFAULT_HEIGHT = 80
DEFAULT_FPS = 12
TRIM_MIN_SEC = 1.0
TRIM_MAX_SEC = 15.0
RECO_MIN = 3.0
RECO_MAX = 6.0
DEFAULT_INIT_SEC = 3.0  # ▶ 최초 로드 시 기본 선택 길이(초)

ACCENT      = "#2563eb"
ACCENT_HOV  = "#1d4ed8"
ACCENT_SUB  = "#e2e8f0"
GOOD_GREEN  = "#059669"
WARN_AMBER  = "#d97706"
TEXT_DARK   = "#0f172a"

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

LIGHT_QSS = f"""
QMainWindow {{ background: #f8fafc; }}
QGroupBox {{
    background: #ffffff; border: 1px solid {ACCENT_SUB};
    border-radius: 10px; margin-top: 12px;
}}
QGroupBox::title {{
    subcontrol-origin: margin; left: 12px; padding: 0 6px;
    color: {TEXT_DARK}; font-weight: 600;
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #ffffff, stop:1 #f8fafc);
}}
QLabel {{ color: {TEXT_DARK}; }}
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
QPushButton#PrimaryButton {{ background: {ACCENT}; color: #ffffff; border: 1px solid {ACCENT}; }}
QPushButton#PrimaryButton:hover {{ background: {ACCENT_HOV}; border-color: {ACCENT_HOV}; }}
QScrollArea {{ background: #ffffff; border: 1px solid {ACCENT_SUB}; border-radius: 8px; }}
#HeaderCard {{ background: #ffffff; border: 1px solid {ACCENT_SUB}; border-radius: 12px; }}
#PreviewPane {{ border: 1px solid {ACCENT_SUB}; border-radius: 10px; background: #f1f5f9; color: #64748b; }}
#DurationBadge {{ border-radius: 14px; padding: 6px 10px; font-weight: 700; background: #eef2ff; color: {ACCENT}; }}
QComboBox::drop-down {{ border: none; }}
QComboBox QAbstractItemView, QListView, QTreeView {{
    background: #ffffff; color: {TEXT_DARK}; border: 1px solid {ACCENT_SUB};
    outline: 0; selection-background-color: #e8f0ff; selection-color: {TEXT_DARK};
}}
QComboBox QAbstractItemView::item, QListView::item, QTreeView::item {{ padding: 6px 8px; height: 28px; }}
"""

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
    raise ValueError("bad time")

def seconds_to_hhmmss(secs: float) -> str:
    if secs < 0: secs = 0
    h = int(secs // 3600)
    m = int((secs % 3600) // 60)
    s = secs % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}" if h else f"{m:02d}:{s:06.3f}"

def run_quiet(cmd):
    kw = dict(capture_output=True, text=True)
    if os.name == "nt":
        kw["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        si = subprocess.STARTUPINFO(); si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        kw["startupinfo"] = si
    return subprocess.run(cmd, **kw)

def probe_duration_sec(ffprobe_path: str, video_path: str) -> float:
    p = run_quiet([ffprobe_path, "-v", "error", "-show_entries", "format=duration",
                   "-of", "default=noprint_wrappers=1:nokey=1", video_path])
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip() or "ffprobe")
    return float(p.stdout.strip())

def extract_preview_frame(ffmpeg_path: str, video_path: str, ts: float) -> Path:
    w, h = 1280, 720
    out_dir = CACHE_DIR / "previews"; out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"preview_{abs(hash((video_path, round(ts,3), '1280x720')))}.png"
    p = run_quiet([ffmpeg_path, "-hide_banner", "-loglevel", "error",
                   "-ss", f"{ts:.3f}", "-i", video_path,
                   "-frames:v", "1", "-vf", f"scale={w}:{h}:flags=lanczos",
                   "-y", str(out_path)])
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip() or "preview")
    return out_path

def build_filters(width: int, height: int, mode: str, fps: int, extra: str = "") -> str:
    if mode == "letterbox":
        scale = f"scale={width}:{height}:force_original_aspect_ratio=decrease:flags=lanczos"; post = f",pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"
    elif mode == "cover":
        scale = f"scale={width}:{height}:force_original_aspect_ratio=increase:flags=lanczos"; post = f",crop={width}:{height}"
    else:
        scale = f"scale={width}:{height}:flags=lanczos"; post = ""
    base = f"fps={fps},{scale}{post}"
    return f"{base},{extra}" if extra else base

def build_gif_commands_auto(ffmpeg_path, video_path, start, end, fps, width, height, mode, alg, dither, out_path):
    duration = max(0.0, end - start)
    if duration <= 0: raise ValueError("bad range")
    extra = "" if alg == "even" else "mpdecimate,setpts=N/FRAME_RATE/TB"
    vf = build_filters(width, height, mode, fps, extra)
    palette = str(CACHE_DIR / "palette.png")
    pass1 = [ffmpeg_path, "-hide_banner", "-loglevel", "error", "-ss", f"{start:.3f}", "-t", f"{duration:.3f}",
             "-i", video_path, "-vf", f"{vf},palettegen=stats_mode=full", "-y", palette]
    pass2 = [ffmpeg_path, "-hide_banner", "-loglevel", "error", "-ss", f"{start:.3f}", "-t", f"{duration:.3f}",
             "-i", video_path, "-i", palette, "-lavfi", f"{vf}[x];[x][1:v]paletteuse=dither={dither}",
             "-loop", "0", "-y", out_path]
    return [pass1, pass2]

def build_gif_commands_manual(ffmpeg_path, frames_dir: Path, fps, width, height, mode, dither, out_path):
    vf = build_filters(width, height, mode, fps)
    palette = str(CACHE_DIR / "palette_manual.png")
    pass1 = [ffmpeg_path, "-hide_banner", "-loglevel", "error", "-framerate", str(fps),
             "-i", str(frames_dir / "frame_%04d.png"), "-vf", f"{vf},palettegen=stats_mode=full", "-y", palette]
    pass2 = [ffmpeg_path, "-hide_banner", "-loglevel", "error", "-framerate", str(fps),
             "-i", str(frames_dir / "frame_%04d.png"), "-i", palette,
             "-lavfi", f"{vf}[x];[x][1:v]paletteuse=dither={dither}", "-loop", "0", "-y", out_path]
    return [pass1, pass2]

def _onerror_chmod(func, path, excinfo):
    try: os.chmod(path, stat.S_IWRITE | stat.S_IREAD); func(path)
    except Exception: pass

# ──────────────────────────────
# RangeSlider — active handle 노출
# ──────────────────────────────
class RangeSlider(QWidget):
    changed = Signal(float, float)  # 0..1
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(36)
        self._lower = 0.0
        self._upper = 0.1
        self._active = None  # 'l' or 'u'
    def lower(self): return self._lower
    def upper(self): return self._upper
    def active_handle(self): return self._active
    def setRange(self, lower: float, upper: float, emit_signal=True):
        lower = max(0.0, min(1.0, lower)); upper = max(0.0, min(1.0, upper))
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
        val = (e.position().x()-10)/max(1,(self.width()-20)); val = max(0.0, min(1.0, val))
        if self._active == 'l': self._lower = min(val, self._upper)
        else: self._upper = max(val, self._lower)
        self.update(); self.changed.emit(self._lower, self._upper)
    def mouseReleaseEvent(self, e): self._active=None

# ──────────────────────────────
# 다국어 리소스
# ──────────────────────────────
STR = {
    "ko": {
        "menu_settings": "설정",
        "act_paths": "도구 경로 설정(ffmpeg/ffprobe)",
        "act_dl": "ffmpeg 자동 준비(재실행)",
        "act_clean": "ffmpeg 폴더 정리",
        "act_update": "업데이트 확인…",
        "badge_reco": "권장 3~6초",
        "input": "입력 비디오:",
        "open": "열기…",
        "trim_title": "구간 선택 — 최소 1초, 최대 15초 (슬라이더 드래그 또는 시간 직접 입력)",
        "start": "시작:",
        "end": "끝:",
        "start_frame": "시작 프레임",
        "end_frame": "끝 프레임",
        "play_range": "구간 재생",
        "opt_title": "옵션",
        "mode": "모드:", "fps": "FPS:", "w": "가로:", "h": "세로:",
        "scale": "스케일:", "dither": "디더링:",
        "modes": ["자동(균등)", "자동(중복 제거)", "수동 선택"],
        "scales": ["레터박스(비율 유지)", "꽉 채우기(크롭)", "스트레치(왜곡)"],
        "dithers": ["floyd_steinberg", "bayer", "none"],
        "manual_title": "프레임 선택(수동 모드)",
        "scan_fps": "스캔 FPS:",
        "scan_btn": "구간에서 프레임 스캔",
        "toggle_all": "전체 선택/해제",
        "output": "출력:",
        "save_as": "저장 위치…",
        "gen_gif": "GIF 생성",
        "ph_video": "동영상 파일 경로 (mp4 등)",
        "ph_output": "output.gif",
        "msg_done": "완료",
        "msg_gif_ok": "GIF 생성 완료:\n{}",
        "msg_warn": "오류",
        "msg_need_ff": "ffmpeg/ffprobe 준비가 필요합니다.",
        "msg_load_first": "먼저 비디오를 불러오세요.",
        "msg_range_bad": "구간은 1~15초여야 합니다.",
        "msg_no_frames": "선택된 프레임이 없습니다.",
        "exit": "종료",
        "exit_ask": "프로그램을 종료하시겠습니까?",
        "update_title": "업데이트",
        "update_new": "새로운 버전이 나왔습니다.\n다운하러 이동하시겠습니까?",
        "update_now": "현재 최신 버전입니다.",
        "update_fail": "업데이트 확인 실패:\n{}",
        "play_fail": "재생 미리보기 실패",
    },
    "en": {
        "menu_settings": "Settings",
        "act_paths": "Set Tool Paths (ffmpeg/ffprobe)",
        "act_dl": "Prepare ffmpeg (re-run)",
        "act_clean": "Clean ffmpeg folder",
        "act_update": "Check for updates…",
        "badge_reco": "Recommended 3–6s",
        "input": "Input video:",
        "open": "Open…",
        "trim_title": "Range — min 1s, max 15s (drag slider or type times)",
        "start": "Start:",
        "end": "End:",
        "start_frame": "Start frame",
        "end_frame": "End frame",
        "play_range": "Play range",
        "opt_title": "Options",
        "mode": "Mode:", "fps": "FPS:", "w": "Width:", "h": "Height:",
        "scale": "Scale:", "dither": "Dithering:",
        "modes": ["Auto (even)", "Auto (remove dup)", "Manual pick"],
        "scales": ["Letterbox (AR keep)", "Cover (crop)", "Stretch (distort)"],
        "dithers": ["floyd_steinberg", "bayer", "none"],
        "manual_title": "Manual frame pick",
        "scan_fps": "Scan FPS:",
        "scan_btn": "Scan frames in range",
        "toggle_all": "Select/Deselect all",
        "output": "Output:",
        "save_as": "Save as…",
        "gen_gif": "Generate GIF",
        "ph_video": "Video file path (mp4 etc.)",
        "ph_output": "output.gif",
        "msg_done": "Done",
        "msg_gif_ok": "GIF created:\n{}",
        "msg_warn": "Error",
        "msg_need_ff": "ffmpeg/ffprobe is required.",
        "msg_load_first": "Load a video first.",
        "msg_range_bad": "Range must be 1–15 seconds.",
        "msg_no_frames": "No frames selected.",
        "exit": "Quit",
        "exit_ask": "Do you want to exit?",
        "update_title": "Update",
        "update_new": "A new version is available.\nOpen releases page?",
        "update_now": "You already have the latest version.",
        "update_fail": "Failed to check updates:\n{}",
        "play_fail": "Failed to play preview",
    }
}

def t(lang, key): return STR[lang][key]

# ──────────────────────────────
# 메인
# ──────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.lang = "ko"
        self.setWindowTitle(APP_TITLE)
        self.resize(1320, 880)
        self.setMinimumSize(1200, 760)  # 리사이즈 안정화

        app_icon = get_app_icon()
        if not app_icon.isNull():
            self.setWindowIcon(app_icon)

        self.ffmpeg_path = find_executable("ffmpeg")
        self.ffprobe_path = find_executable("ffprobe")
        self.video_path = ""
        self.duration_sec = 0.0

        # ▼ 드래그 상태(고정 길이 팬)
        self._drag_active = None          # 'l' or 'u'
        self._drag_span_sec = None        # 현재 고정할 구간 길이(초)
        self._prev_lo_sec = 0.0
        self._prev_hi_sec = 0.0

        self._build_ui()
        self._auto_setup_tools()

        self.preview_timer = QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.setInterval(200)
        self.preview_timer.timeout.connect(self._update_split_preview)

        QTimer.singleShot(3500, lambda: self._check_for_updates(False))

    # ── 공통 팝업(화이트) ──────────────────────────────
    def _msgbox(self, title, text, icon="info", informative_text=None,
                buttons=QMessageBox.Ok, default=QMessageBox.Ok):
        m = QMessageBox(self)
        m.setWindowTitle(title)
        m.setText(text)
        if informative_text:
            m.setInformativeText(informative_text)
        m.setIcon({"info": QMessageBox.Information, "warn": QMessageBox.Warning,
                   "error": QMessageBox.Critical}.get(icon, QMessageBox.NoIcon))
        m.setStandardButtons(buttons); m.setDefaultButton(default)
        # 버튼 라벨 한글화/영문화
        btn = m.button(QMessageBox.Yes);    btn and btn.setText("예" if self.lang=="ko" else "Yes")
        btn = m.button(QMessageBox.No);     btn and btn.setText("아니오" if self.lang=="ko" else "No")
        btn = m.button(QMessageBox.Ok);     btn and btn.setText("확인" if self.lang=="ko" else "OK")
        btn = m.button(QMessageBox.Cancel); btn and btn.setText("취소" if self.lang=="ko" else "Cancel")
        m.setStyleSheet(f"""
            QMessageBox {{ background: #ffffff; }}
            QLabel {{ color: {TEXT_DARK}; }}
            QPushButton {{
                border-radius: 8px; padding: 6px 12px; font-weight: 600;
                background: #ffffff; color: {TEXT_DARK}; border: 1px solid {ACCENT_SUB};
                min-width: 80px;
            }}
            QPushButton:hover {{ background: #f1f5f9; }}
        """)
        return m.exec()

    def info(self, title, text, info=None): return self._msgbox(title, text, "info", info)
    def warn(self, title, text, info=None): return self._msgbox(title, text, "warn", info)
    def error(self, title, text, info=None): return self._msgbox(title, text, "error", info)
    def ask_yes_no(self, title, text, info=None) -> bool:
        ret = self._msgbox(title, text, "info", info, QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        return ret == QMessageBox.Yes

    # ── UI ─────────────────────────────────────────────
    def _build_ui(self):
        self.setStyleSheet(LIGHT_QSS)

        # 메뉴(문자열은 lang 토글 시 갱신)
        self.menu_settings = self.menuBar().addMenu("")
        self.act_paths  = QAction("", self); self.act_paths.triggered.connect(self._select_tools)
        self.act_dl     = QAction("", self); self.act_dl.triggered.connect(self._auto_setup_tools)
        self.act_clean  = QAction("", self); self.act_clean.triggered.connect(self._tidy_ffmpeg_dir)
        self.act_update = QAction("", self); self.act_update.triggered.connect(lambda: self._check_for_updates(True))
        for a in (self.act_paths, self.act_dl, self.act_clean, self.act_update):
            self.menu_settings.addAction(a)

        central = QWidget(); root = QVBoxLayout(central); self.setCentralWidget(central)
        root.setSizeConstraint(QVBoxLayout.SetNoConstraint)

        # 헤더
        header = QHBoxLayout()
        card = QFrame(); card.setObjectName("HeaderCard")
        card_l = QHBoxLayout(card); card_l.setContentsMargins(14,10,14,10); card_l.setSpacing(12)
        logo = QLabel()
        ico = get_app_icon()
        if not ico.isNull(): logo.setPixmap(ico.pixmap(28,28))
        self.lbl_title = QLabel("Apex GIF Maker"); self.lbl_title.setStyleSheet("font-size:18px; font-weight:800;")
        self.lbl_duration_badge = QLabel(""); self.lbl_duration_badge.setObjectName("DurationBadge")

        # KOR/ENG 토글
        self.btn_lang = QPushButton("ENG")
        self.btn_lang.setToolTip("Switch to English")
        self.btn_lang.clicked.connect(self._toggle_lang)

        card_l.addWidget(logo); card_l.addWidget(self.lbl_title)
        card_l.addStretch(1); card_l.addWidget(self.lbl_duration_badge); card_l.addWidget(self.btn_lang)
        header.addWidget(card)
        root.addLayout(header)

        # 파일열기
        file_box = QHBoxLayout()
        self.lbl_input = QLabel("")
        self.le_video = QLineEdit(); self.le_video.setPlaceholderText("")
        self.btn_browse = QPushButton(""); self.btn_browse.clicked.connect(self._browse_video)
        file_box.addWidget(self.lbl_input); file_box.addWidget(self.le_video, 1); file_box.addWidget(self.btn_browse)
        root.addLayout(file_box)

        # 구간
        self.trim_group = QGroupBox(""); tg = QGridLayout(self.trim_group)

        self.range = RangeSlider(); self.range.setRange(0.0, 0.1)
        self.range.changed.connect(self._on_range_changed)

        self.le_start = QLineEdit("00:00.000")
        self.le_end   = QLineEdit("00:03.000")
        for le in (self.le_start, self.le_end):
            le.setPlaceholderText("")
            le.editingFinished.connect(self._apply_edits_to_range)

        self.btn_prev_start = QPushButton("")
        self.btn_prev_end   = QPushButton("")
        self.btn_prev_start.clicked.connect(self._update_split_preview)
        self.btn_prev_end.clicked.connect(self._update_split_preview)

        # ▼ 선택 구간 재생
        self.btn_play = QPushButton("")
        self.btn_play.clicked.connect(self._play_range)

        self.timeline_area = QScrollArea(); self.timeline_area.setWidgetResizable(True)
        self.timeline_inner = QWidget(); self.timeline_layout = QHBoxLayout(self.timeline_inner)
        self.timeline_layout.setContentsMargins(4,4,4,4); self.timeline_layout.setSpacing(4)
        self.timeline_area.setWidget(self.timeline_inner)

        self.lbl_prev_start = QLabel("start"); self.lbl_prev_start.setObjectName("PreviewPane"); self.lbl_prev_start.setAlignment(Qt.AlignCenter)
        self.lbl_prev_end   = QLabel("end");   self.lbl_prev_end.setObjectName("PreviewPane");   self.lbl_prev_end.setAlignment(Qt.AlignCenter)
        for lb in (self.lbl_prev_start, self.lbl_prev_end):
            lb.setMinimumHeight(420)
            lb.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        tg.addWidget(self.range, 0, 0, 1, 7)
        tg.addWidget(self.timeline_area, 1, 0, 1, 7)
        tg.addWidget(self._mk_lbl("start_label"), 2, 0); tg.addWidget(self.le_start, 2, 1)
        tg.addWidget(self._mk_lbl("end_label"),   2, 2); tg.addWidget(self.le_end,   2, 3)
        tg.addWidget(self.btn_prev_start, 2, 4)
        tg.addWidget(self.btn_prev_end,   2, 5)
        tg.addWidget(self.btn_play,       2, 6)

        split = QHBoxLayout(); split.addWidget(self.lbl_prev_start); split.addWidget(self.lbl_prev_end)
        tg.addLayout(split, 3, 0, 1, 7)
        root.addWidget(self.trim_group)

        # 옵션
        self.opt_group = QGroupBox(""); og = QGridLayout(self.opt_group)
        self.lbl_mode = QLabel(""); self.combo_mode = QComboBox()
        self.lbl_fps  = QLabel(""); self.spin_fps   = QSpinBox();  self.spin_fps.setRange(1, 60); self.spin_fps.setValue(DEFAULT_FPS)
        self.lbl_w    = QLabel(""); self.spin_w     = QSpinBox();  self.spin_w.setRange(8, 1024); self.spin_w.setValue(DEFAULT_WIDTH)
        self.lbl_h    = QLabel(""); self.spin_h     = QSpinBox();  self.spin_h.setRange(8, 1024); self.spin_h.setValue(DEFAULT_HEIGHT)
        self.lbl_scale= QLabel(""); self.combo_scale= QComboBox()
        self.lbl_dith = QLabel(""); self.combo_dither= QComboBox()

        og.addWidget(self.lbl_mode, 0,0); og.addWidget(self.combo_mode, 0,1)
        og.addWidget(self.lbl_fps,  0,2); og.addWidget(self.spin_fps,   0,3)
        og.addWidget(self.lbl_w,    0,4); og.addWidget(self.spin_w,     0,5)
        og.addWidget(self.lbl_h,    0,6); og.addWidget(self.spin_h,     0,7)
        og.addWidget(self.lbl_scale,1,0); og.addWidget(self.combo_scale,1,1,1,3)
        og.addWidget(self.lbl_dith, 1,4); og.addWidget(self.combo_dither,1,5)
        root.addWidget(self.opt_group)

        # 수동 선택
        self.manual_group = QGroupBox("")
        mg = QVBoxLayout(self.manual_group)
        top_bar = QHBoxLayout()
        self.lbl_scan_fps = QLabel("")
        self.spin_scan_fps = QSpinBox(); self.spin_scan_fps.setRange(1, 30); self.spin_scan_fps.setValue(10)
        self.btn_scan = QPushButton(""); self.btn_scan.clicked.connect(self._scan_frames)
        self.btn_all  = QPushButton(""); self.btn_all.clicked.connect(self._toggle_all_frames)
        top_bar.addWidget(self.lbl_scan_fps); top_bar.addWidget(self.spin_scan_fps)
        top_bar.addStretch(1); top_bar.addWidget(self.btn_scan); top_bar.addWidget(self.btn_all)
        self.list_frames = QListWidget()
        self.list_frames.setViewMode(QListView.IconMode)
        self.list_frames.setIconSize(QSize(192,108))
        self.list_frames.setResizeMode(QListView.Adjust)
        self.list_frames.setSpacing(6)
        self.list_frames.setMinimumHeight(220)
        mg.addLayout(top_bar); mg.addWidget(self.list_frames)
        root.addWidget(self.manual_group)
        self.manual_group.setVisible(False)

        self.combo_mode.currentIndexChanged.connect(lambda i: self.manual_group.setVisible(i==2))

        # 출력/실행
        out_box = QHBoxLayout()
        self.lbl_output = QLabel("")
        self.le_out = QLineEdit(); self.le_out.setPlaceholderText("")
        self.btn_out = QPushButton(""); self.btn_out.clicked.connect(self._choose_output)
        out_box.addWidget(self.lbl_output); out_box.addWidget(self.le_out, 1); out_box.addWidget(self.btn_out)
        root.addLayout(out_box)

        run_box = QHBoxLayout()
        self.btn_generate = QPushButton(""); self.btn_generate.setObjectName("PrimaryButton")
        self.btn_generate.clicked.connect(self._generate_gif)
        run_box.addStretch(1); run_box.addWidget(self.btn_generate)
        root.addLayout(run_box)

        self.log = QTextEdit(); self.log.setReadOnly(True); self.log.setPlaceholderText("log")
        root.addWidget(self.log, 1)

        self._apply_language()  # 초기 언어 적용
        self._update_duration_badge()

    def _mk_lbl(self, name):
        lbl = QLabel("")
        setattr(self, name, lbl)
        return lbl

    def _toggle_lang(self):
        self.lang = "en" if self.lang == "ko" else "ko"
        self._apply_language()

    def _apply_language(self):
        tr = lambda k: t(self.lang, k)

        self.menu_settings.setTitle(tr("menu_settings"))
        self.act_paths.setText(tr("act_paths"))
        self.act_dl.setText(tr("act_dl"))
        self.act_clean.setText(tr("act_clean"))
        self.act_update.setText(tr("act_update"))

        self.lbl_duration_badge.setText(f"{tr('badge_reco')}")
        self.lbl_input.setText(tr("input"))
        self.le_video.setPlaceholderText(tr("ph_video"))
        self.btn_browse.setText(tr("open"))

        self.trim_group.setTitle(tr("trim_title"))
        self.start_label.setText(tr("start"))
        self.end_label.setText(tr("end"))
        self.btn_prev_start.setText(tr("start_frame"))
        self.btn_prev_end.setText(tr("end_frame"))
        self.btn_play.setText(tr("play_range"))

        self.opt_group.setTitle(tr("opt_title"))
        self.lbl_mode.setText(tr("mode")); self.lbl_fps.setText(tr("fps"))
        self.lbl_w.setText(tr("w")); self.lbl_h.setText(tr("h"))
        self.lbl_scale.setText(tr("scale")); self.lbl_dith.setText(tr("dither"))

        self.combo_mode.clear();  self.combo_mode.addItems(tr("modes"))
        self.combo_scale.clear(); self.combo_scale.addItems(tr("scales")); self.combo_scale.setCurrentIndex(1)
        self.combo_dither.clear();self.combo_dither.addItems(tr("dithers"))

        self.manual_group.setTitle(tr("manual_title"))
        self.lbl_scan_fps.setText(tr("scan_fps"))
        self.btn_scan.setText(tr("scan_btn"))
        self.btn_all.setText(tr("toggle_all"))

        self.lbl_output.setText(tr("output"))
        self.le_out.setPlaceholderText(tr("ph_output"))
        self.btn_out.setText(tr("save_as"))
        self.btn_generate.setText(tr("gen_gif"))

        self.btn_lang.setText("ENG" if self.lang=="ko" else "KOR")
        self.btn_lang.setToolTip("Switch to English" if self.lang=="ko" else "한국어로 전환")

    # ── 도구/설정 ─────────────────────────────────────
    def _append_log(self, t: str): self.log.append(t)

    def _select_tools(self):
        ffmpeg, _ = QFileDialog.getOpenFileName(self, "ffmpeg", "", "Executable (*)")
        if ffmpeg: self.ffmpeg_path = ffmpeg
        ffprobe, _ = QFileDialog.getOpenFileName(self, "ffprobe", "", "Executable (*)")
        if ffprobe: self.ffprobe_path = ffprobe

    def _download(self, url: str, dest_path: Path) -> bool:
        try:
            with urllib.request.urlopen(url) as resp, open(dest_path, "wb") as out:
                total = int(resp.headers.get("Content-Length", "0") or 0); read = 0
                while True:
                    chunk = resp.read(1024*256)
                    if not chunk: break
                    out.write(chunk); read += len(chunk)
                    if total: self._append_log(f"[DL] {int(read*100/total)}%")
            self._append_log("[DL] done"); return True
        except Exception as e:
            self._append_log(f"[DL] err: {e}"); return False

    def _auto_setup_tools(self):
        self.ffmpeg_path = find_executable("ffmpeg")
        self.ffprobe_path = find_executable("ffprobe")
        if self.ffmpeg_path and self.ffprobe_path:
            self._append_log("[INFO] ffmpeg/ffprobe ready"); return
        os_name = platform.system().lower()
        if "windows" in os_name: self._setup_windows_ffmpeg()
        elif "darwin" in os_name or "mac" in os_name: self._setup_macos_ffmpeg()
        elif "linux" in os_name: self._setup_linux_ffmpeg()
        else: self._append_log("[WARN] unsupported OS")
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
                ffmpeg = ffprobe = None
                for p in FFMPEG_DIR.rglob("*"):
                    if p.name.lower()=="ffmpeg.exe": ffmpeg=str(p.resolve())
                    elif p.name.lower()=="ffprobe.exe": ffprobe=str(p.resolve())
                if ffmpeg and ffprobe:
                    shutil.copy2(ffmpeg, FFMPEG_DIR/"ffmpeg.exe")
                    shutil.copy2(ffprobe, FFMPEG_DIR/"ffprobe.exe")
                    self._tidy_ffmpeg_dir(); return
            except Exception as e:
                self._append_log(f"[ERR] zip: {e}")
        self._append_log("[ERR] ffmpeg prepare failed")

    def _setup_macos_ffmpeg(self):
        brew = shutil.which("brew")
        if brew:
            try: run_quiet([brew, "install", "ffmpeg"])
            except Exception as e: self._append_log(f"[ERR] brew: {e}")
        else: self._append_log("[WARN] install Homebrew")

    def _setup_linux_ffmpeg(self):
        apt = shutil.which("apt-get")
        if apt:
            try: run_quiet(["sudo","apt-get","update"]); run_quiet(["sudo","apt-get","-y","install","ffmpeg"])
            except Exception as e: self._append_log(f"[ERR] apt: {e}")
        if not find_executable("ffmpeg") or not find_executable("ffprobe"):
            arch = platform.machine().lower()
            if arch in ("x86_64","amd64"):
                url = "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"
            elif arch in ("aarch64","arm64"):
                url = "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-arm64-static.tar.xz"
            else:
                self._append_log(f"[WARN] arch {arch}"); return
            tar_path = FFMPEG_DIR / Path(url).name
            if self._download(url, tar_path):
                try:
                    with tarfile.open(tar_path, 'r:*') as tf: tf.extractall(FFMPEG_DIR)
                    ffmpeg = ffprobe = None
                    for p in FFMPEG_DIR.rglob("*"):
                        if p.name=="ffmpeg": ffmpeg=str(p.resolve())
                        elif p.name=="ffprobe": ffprobe=str(p.resolve())
                    if ffmpeg and ffprobe:
                        shutil.copy2(ffmpeg, FFMPEG_DIR/"ffmpeg")
                        shutil.copy2(ffprobe, FFMPEG_DIR/"ffprobe")
                        os.chmod(FFMPEG_DIR/"ffmpeg", 0o755); os.chmod(FFMPEG_DIR/"ffprobe", 0o755)
                        self._tidy_ffmpeg_dir()
                except Exception as e:
                    self._append_log(f"[ERR] tar: {e}")

    def _tidy_ffmpeg_dir(self):
        try:
            keep = {"ffmpeg.exe","ffprobe.exe"} if os.name=="nt" else {"ffmpeg","ffprobe"}
            if not all((FFMPEG_DIR/k).exists() for k in keep):
                self._append_log("[WARN] tidy skipped (missing exe)"); return
            for p in FFMPEG_DIR.iterdir():
                if p.name in keep: continue
                try:
                    if p.is_dir(): shutil.rmtree(p, onerror=_onerror_chmod)
                    else: p.unlink()
                except Exception as e:
                    self._append_log(f"[WARN] rm {p.name}: {e}")
            self._append_log("[OK] ffmpeg-bin tidy")
        except Exception as e:
            self._append_log(f"[ERR] tidy: {e}")

    # ── 업데이트 ───────────────────────────────────────
    def _normalize_version(self, v: str) -> tuple:
        try:
            v=v.strip(); v=v[1:] if v[:1].lower()=="v" else v
            nums=[int(''.join(ch for ch in p if ch.isdigit()) or 0) for p in v.split(".")]
            while len(nums)<3: nums.append(0)
            return tuple(nums[:3])
        except Exception:
            return tuple()

    def _check_for_updates(self, manual=False):
        try:
            req = urllib.request.Request(GITHUB_API_LATEST, headers={"User-Agent": f"ApexGIFMaker/{APP_VERSION}","Accept":"application/vnd.github+json"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8","ignore"))
            tag = str(data.get("tag_name","")).strip()
            if not tag:
                if manual: self.info(t(self.lang,"update_title"), t(self.lang,"update_fail").format("no tag")); return
            cur = self._normalize_version(APP_VERSION); new = self._normalize_version(tag)
            if new and cur and new>cur:
                if self.ask_yes_no(t(self.lang,"update_title"), t(self.lang,"update_new"), f"(current v{APP_VERSION} / latest {tag})"):
                    QDesktopServices.openUrl(QUrl(GITHUB_HTML_LATEST))
            else:
                if manual: self.info(t(self.lang,"update_title"), t(self.lang,"update_now"))
        except Exception as e:
            if manual: self.warn(t(self.lang,"update_title"), t(self.lang,"update_fail").format(e))

    # ── 로드/트림/프리뷰 ───────────────────────────────
    def _browse_video(self):
        cap = "Videos (*.mp4 *.mov *.mkv *.webm *.avi);;All files (*.*)"
        path, _ = QFileDialog.getOpenFileName(self, "Open Video" if self.lang=="en" else "비디오 파일 선택", "", cap)
        if path:
            self.le_video.setText(path); self._load_video(path)

    def _load_video(self, path: str):
        if not Path(path).is_file():
            self.warn(t(self.lang,"msg_warn"), "File not found" if self.lang=="en" else "파일이 존재하지 않습니다."); return
        if not self.ffprobe_path:
            self.warn(t(self.lang,"msg_warn"), t(self.lang,"msg_need_ff")); return
        try:
            self.duration_sec = probe_duration_sec(self.ffprobe_path, path); self.video_path = path

            # ▶ 최초 기본 선택 길이를 3초로 시도(영상/제약에 맞게 자동 조정)
            init_span = min(DEFAULT_INIT_SEC, TRIM_MAX_SEC, self.duration_sec)
            if init_span < TRIM_MIN_SEC:
                init_span = min(self.duration_sec, TRIM_MIN_SEC)
            hi = init_span / max(1e-9, self.duration_sec)
            self.range.setRange(0.0, hi)

            # 텍스트 편집 시에만 제약 강제, 드래그는 고정 길이 팬으로 처리
            self._update_time_edits()
            self._build_timeline_thumbs()
            self._update_split_preview()
            self._update_duration_badge()
            self._append_log(f"[OK] loaded: {path}")
        except Exception as e:
            self.error(t(self.lang,"msg_warn"), f"{'Failed to probe' if self.lang=='en' else '동영상 정보를 읽는 중 문제 발생'}:\n{e}")

    def _on_range_changed(self, lo_norm: float, hi_norm: float):
        """드래그 시 고정 길이 팬 동작(끌고 있는 쪽과 반대쪽을 같은 길이만큼 이동)"""
        if self.duration_sec <= 0:
            return

        active = self.range.active_handle()  # 'l' / 'u' / None
        lo = self.range.lower() * self.duration_sec
        hi = self.range.upper() * self.duration_sec

        # 드래그 시작: 현재 길이를 기억(제약 범위 내로 클램프)
        if active and self._drag_active != active:
            self._drag_active = active
            base_span = (self._prev_hi_sec - self._prev_lo_sec) or (hi - lo)
            self._drag_span_sec = max(TRIM_MIN_SEC, min(TRIM_MAX_SEC, base_span))

        # 드래그 중: 반대쪽 핸들도 이동(고정 길이)
        if active and self._drag_span_sec:
            span = self._drag_span_sec
            if active == 'l':
                new_hi = lo + span
                if new_hi > self.duration_sec:
                    new_hi = self.duration_sec
                    lo = max(0.0, new_hi - span)
                self.range.setRange(lo / self.duration_sec, new_hi / self.duration_sec, emit_signal=False)
            elif active == 'u':
                new_lo = hi - span
                if new_lo < 0.0:
                    new_lo = 0.0
                    hi = min(self.duration_sec, new_lo + span)
                self.range.setRange(new_lo / self.duration_sec, hi / self.duration_sec, emit_signal=False)
            # 최신값 재반영
            lo = self.range.lower() * self.duration_sec
            hi = self.range.upper() * self.duration_sec

        # 표시 갱신
        self._update_time_edits()
        self._update_duration_badge()
        self.preview_timer.start()

        # 다음 이벤트 대비 상태 저장
        self._prev_lo_sec = lo
        self._prev_hi_sec = hi

        # 드래그 종료: 상태 초기화
        if not active:
            self._drag_active = None
            self._drag_span_sec = None

    def _apply_trim_constraints(self, adjust='auto'):
        """텍스트로 시간을 직접 입력했을 때만 길이 제약(1~15초) 강제"""
        if self.duration_sec <= 0: return
        lo = self.range.lower()*self.duration_sec
        hi = self.range.upper()*self.duration_sec
        span = hi-lo
        if span < TRIM_MIN_SEC:
            need = TRIM_MIN_SEC - span
            if adjust=='end' or (adjust=='auto' and hi+need<=self.duration_sec): hi=min(self.duration_sec, hi + need)
            else: lo=max(0.0, lo - need)
        if span > TRIM_MAX_SEC:
            cut = span-TRIM_MAX_SEC
            if adjust=='end' or (adjust=='auto' and hi-cut>=0): hi -= cut
            else: lo += cut
        self.range.setRange(lo/max(1e-9,self.duration_sec), hi/max(1e-9,self.duration_sec), emit_signal=False)

    def _update_time_edits(self):
        lo = self.range.lower()*self.duration_sec; hi = self.range.upper()*self.duration_sec
        self.le_start.setText(seconds_to_hhmmss(lo)); self.le_end.setText(seconds_to_hhmmss(hi))

    def _apply_edits_to_range(self):
        if self.duration_sec <= 0: return
        try:
            lo = hhmmss_to_seconds(self.le_start.text()); hi = hhmmss_to_seconds(self.le_end.text())
        except Exception:
            self._update_time_edits(); return
        lo = max(0.0, min(lo, self.duration_sec)); hi = max(0.0, min(hi, self.duration_sec))
        if hi <= lo: hi = min(self.duration_sec, lo + TRIM_MIN_SEC)
        span = hi - lo
        if span < TRIM_MIN_SEC: hi = min(self.duration_sec, lo + TRIM_MIN_SEC)
        if span > TRIM_MAX_SEC:
            if lo + TRIM_MAX_SEC <= self.duration_sec: hi = lo + TRIM_MAX_SEC
            else: hi = self.duration_sec; lo = max(0.0, hi - TRIM_MAX_SEC)
        self.range.setRange(lo/max(1e-9,self.duration_sec), hi/max(1e-9,self.duration_sec))
        self._update_duration_badge(); self.preview_timer.start()

    def _update_duration_badge(self):
        if self.duration_sec <= 0:
            self.lbl_duration_badge.setText(f"{t(self.lang,'badge_reco')}")
            self.lbl_duration_badge.setStyleSheet(""); return
        lo = self.range.lower()*self.duration_sec; hi = self.range.upper()*self.duration_sec
        span = hi - lo
        txt = (f"Length: {span:.3f}s  • {t(self.lang,'badge_reco')}"
               if self.lang=="en" else f"선택 길이: {span:.3f}초  • {t(self.lang,'badge_reco')}")
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
            self._append_log(f"[ERR] preview: {e}")

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
        self._append_log("[RUN] thumbs: " + " ".join(map(str, cmd))); run_quiet(cmd)
        while self.timeline_layout.count():
            item = self.timeline_layout.takeAt(0); w = item.widget(); w and w.setParent(None)
        for fp in sorted(thumbs_dir.glob("thumb_*.png")):
            lb = QLabel(); lb.setObjectName("PreviewPane")
            lb.setPixmap(QPixmap(str(fp)).scaled(96,54, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            lb.setToolTip(fp.name); self.timeline_layout.addWidget(lb)
        self.timeline_layout.addStretch(1)

    # ── 선택 구간 재생 ──────────────────────────────────
    def _play_range(self):
        if not self.video_path or not self.ffmpeg_path:
            self.warn(t(self.lang,"msg_warn"), t(self.lang,"msg_load_first")); return
        lo = self.range.lower()*self.duration_sec; hi = self.range.upper()*self.duration_sec
        dur = max(0.0, hi-lo)
        try:
            out = CACHE_DIR / "preview_play.mp4"
            # 빠른 미리보기: 키프레임 이슈 감수하고 copy 시도, 실패 시 재인코딩
            cmd_copy = [self.ffmpeg_path, "-hide_banner", "-loglevel", "error",
                        "-ss", f"{lo:.3f}", "-t", f"{dur:.3f}", "-i", self.video_path,
                        "-c", "copy", "-movflags", "faststart", "-y", str(out)]
            p = run_quiet(cmd_copy)
            if p.returncode != 0 or not out.exists():
                cmd_enc = [self.ffmpeg_path, "-hide_banner", "-loglevel", "error",
                           "-ss", f"{lo:.3f}", "-t", f"{dur:.3f}", "-i", self.video_path,
                           "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
                           "-c:a", "aac", "-b:a", "128k", "-movflags", "faststart", "-y", str(out)]
                p = run_quiet(cmd_enc)
                if p.returncode != 0: raise RuntimeError(p.stderr)
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(out)))
        except Exception as e:
            self.error(t(self.lang,"play_fail"), str(e))

    # ── 수동 프레임 ────────────────────────────────────
    def _clear_frames_dir(self, d: Path):
        if d.exists():
            for p in d.glob("*.png"):
                try: p.unlink()
                except Exception: pass
        else:
            d.mkdir(parents=True, exist_ok=True)

    def _scan_frames(self):
        if not self.video_path or not self.ffmpeg_path:
            self.warn(t(self.lang,"msg_warn"), t(self.lang,"msg_need_ff")); return
        if self.combo_mode.currentIndex()!=2:
            self.info("Info" if self.lang=="en" else "안내", "Use in manual mode." if self.lang=="en" else "수동 선택 모드에서 사용하세요."); return
        scan_fps = self.spin_scan_fps.value()
        lo = self.range.lower()*self.duration_sec; hi = self.range.upper()*self.duration_sec
        duration = max(0.0, hi-lo)
        if duration <= 0:
            self.warn(t(self.lang,"msg_warn"), "Invalid range" if self.lang=="en" else "구간이 올바르지 않습니다."); return
        frames_dir = CACHE_DIR / "frames"; self._clear_frames_dir(frames_dir)
        cmd = [self.ffmpeg_path, "-hide_banner", "-loglevel", "error",
               "-ss", f"{lo:.3f}", "-t", f"{duration:.3f}", "-i", self.video_path,
               "-vf", f"fps={scan_fps},scale=384:216:flags=lanczos",
               str(frames_dir / "frame_%04d.png")]
        self._append_log("[RUN] scan: " + " ".join(map(str, cmd)))
        p = run_quiet(cmd)
        if p.returncode != 0:
            self._append_log(p.stderr.strip()); self.error(t(self.lang,"msg_warn"), "Scan failed" if self.lang=="en" else "프레임 추출 실패"); return
        self.list_frames.clear()
        for fp in sorted(frames_dir.glob("frame_*.png")):
            item = QListWidgetItem(); item.setText(fp.name)
            pix = QPixmap(str(fp)).scaled(self.list_frames.iconSize(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            item.setIcon(pix); item.setCheckState(Qt.Checked); self.list_frames.addItem(item)
        self._append_log(f"[OK] scanned: {self.list_frames.count()} frames")

    def _toggle_all_frames(self):
        any_unchecked = any(self.list_frames.item(i).checkState()==Qt.Unchecked for i in range(self.list_frames.count()))
        new_state = Qt.Checked if any_unchecked else Qt.Unchecked
        for i in range(self.list_frames.count()):
            self.list_frames.item(i).setCheckState(new_state)

    # ── 출력/생성 ─────────────────────────────────────
    def _choose_output(self):
        default_name = str(APP_DIR / "output.gif")
        cap = "GIF (*.gif)"
        path, _ = QFileDialog.getSaveFileName(self, "Save GIF" if self.lang=="en" else "출력 GIF 저장", default_name, cap)
        if path:
            if not path.lower().endswith(".gif"): path += ".gif"
            self.le_out.setText(path)

    def _ensure_tools(self) -> bool:
        if not self.ffmpeg_path or not Path(self.ffmpeg_path).exists():
            self._append_log("[ERR] ffmpeg not found"); return False
        if not self.ffprobe_path or not Path(self.ffprobe_path).exists():
            self._append_log("[ERR] ffprobe not found"); return False
        return True

    def _generate_gif(self):
        if not self._ensure_tools():
            self.warn(t(self.lang,"msg_warn"), t(self.lang,"msg_need_ff")); return
        if not self.video_path:
            self.warn(t(self.lang,"msg_warn"), t(self.lang,"msg_load_first")); return

        lo = self.range.lower()*self.duration_sec; hi = self.range.upper()*self.duration_sec
        duration = max(0.0, hi-lo)
        if duration < TRIM_MIN_SEC or duration > TRIM_MAX_SEC:
            self.warn(t(self.lang,"msg_warn"), t(self.lang,"msg_range_bad")); return

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
            if not frames_dir.exists(): frames_dir.mkdir(parents=True, exist_ok=True)
            for p in frames_dir.glob("*.png"):
                try: p.unlink()
                except: pass
            src_dir = CACHE_DIR / "frames"
            files = [src_dir / self.list_frames.item(i).text() for i in range(self.list_frames.count())
                     if self.list_frames.item(i).checkState()==Qt.Checked]
            if not files:
                self.warn(t(self.lang,"msg_warn"), t(self.lang,"msg_no_frames")); return
            for idx, fp in enumerate(files, start=1): shutil.copy2(fp, frames_dir / f"frame_{idx:04d}.png")
            cmds = build_gif_commands_manual(self.ffmpeg_path, frames_dir, fps, w, h, mode, dither, out_path)

        self.btn_generate.setEnabled(False)
        self._append_log("[RUN] gif start")
        for i, cmd in enumerate(cmds, start=1):
            self._append_log(f"[RUN] pass{i}: {' '.join(map(str, cmd))}")
            p = run_quiet(cmd)
            if p.stdout.strip(): self._append_log(p.stdout.strip())
            if p.stderr.strip(): self._append_log(p.stderr.strip())
            if p.returncode != 0:
                self.error(t(self.lang,"msg_warn"), f"ffmpeg failed (pass {i})")
                self.btn_generate.setEnabled(True); return

        if Path(out_path).is_file():
            self._append_log(f"[OK] saved: {out_path}")
            self.info(t(self.lang,"msg_done"), t(self.lang,"msg_gif_ok").format(out_path))
        else:
            self._append_log("[ERR] no output")
            self.warn(t(self.lang,"msg_warn"), "Output not found" if self.lang=="en" else "출력 파일을 찾을 수 없습니다.")

        self._tidy_ffmpeg_dir()
        self.btn_generate.setEnabled(True)

    # ── 종료 확인 ─────────────────────────────────────
    def closeEvent(self, event):
        if self.ask_yes_no(t(self.lang,"exit"), t(self.lang,"exit_ask")): event.accept()
        else: event.ignore()

# ──────────────────────────────
# 엔트리포인트
# ──────────────────────────────
def main():
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    pal = QPalette()
    pal.setColor(QPalette.Window, QColor("#f8fafc"))
    pal.setColor(QPalette.WindowText, QColor("#0f172a"))
    pal.setColor(QPalette.Base, QColor("#ffffff"))
    pal.setColor(QPalette.AlternateBase, QColor("#f1f5f9"))
    pal.setColor(QPalette.ToolTipBase, QColor("#ffffff"))
    pal.setColor(QPalette.ToolTipText, QColor("#0f172a"))
    pal.setColor(QPalette.Text, QColor("#0f172a"))
    pal.setColor(QPalette.Button, QColor("#ffffff"))
    pal.setColor(QPalette.ButtonText, QColor("#0f172a"))
    pal.setColor(QPalette.Highlight, QColor(0x25, 0x63, 0xEB))
    pal.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    app.setPalette(pal)

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
