# constants.py
# Apex GIF Maker 공용 상수 + 라이트 테마(QSS)

from pathlib import Path
import sys

# ──────────────────────────────────────────────────────────────────────────────
# 앱 메타
APP_TITLE   = "Apex GIF Maker (MP4 → GIF)"
APP_VERSION = "2.5.0"

def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent

APP_DIR   = app_root()
CACHE_DIR = APP_DIR / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ★ ffmpeg 보관 디렉터리(필수)
FFMPEG_DIR = APP_DIR / "ffmpeg-bin"
FFMPEG_DIR.mkdir(parents=True, exist_ok=True)

# ──────────────────────────────────────────────────────────────────────────────
# 기본 옵션
DEFAULT_WIDTH  = 160
DEFAULT_HEIGHT = 80
DEFAULT_FPS    = 12

# 선택 구간(초)
TRIM_MIN_SEC = 1.0
TRIM_MAX_SEC = 15.0

# 권장 구간(초)
RECO_MIN = 3.0
RECO_MAX = 6.0

# 초기 선택 길이(초)
DEFAULT_INIT_SEC = 3.0

# ──────────────────────────────────────────────────────────────────────────────
# 색상 팔레트
ACCENT_MAIN = "#2563eb"  # 파랑
ACCENT_SUB  = "#93c5fd"  # 연파랑
GOOD_GREEN  = "#10b981"
WARN_AMBER  = "#f59e0b"
DANGER_RED  = "#ef4444"
FG_PRIMARY  = "#0f172a"  # 다크 네이비(글자)
BG_MAIN     = "#ffffff"
BG_SOFT     = "#f1f5f9"  # 밝은 회색
BORDER_SOFT = "#e2e8f0"

# ──────────────────────────────────────────────────────────────────────────────
# 라이트 테마(QSS) — ComboBox 팝업/PreviewView/버튼 스타일 포함
LIGHT_QSS = f"""
/* 전역 */
QWidget {{
    background: {BG_MAIN};
    color: {FG_PRIMARY};
    font-family: "Segoe UI", "Apple SD Gothic Neo", "Malgun Gothic", sans-serif;
    font-size: 12pt;
}}
QToolTip {{
    background: {BG_SOFT};
    color: {FG_PRIMARY};
    border: 1px solid {BORDER_SOFT};
    padding: 4px 6px;
    border-radius: 6px;
}}

/* 배지 */
QLabel#DurationBadge {{
    background: {BG_MAIN};
    color: {GOOD_GREEN};
    border: 1px solid {ACCENT_SUB};
    border-radius: 999px;
    padding: 4px 10px;
    font-weight: 600;
}}

/* 입력류 */
QLineEdit, QSpinBox, QComboBox, QTextEdit {{
    background: {BG_MAIN};
    border: 1px solid {BORDER_SOFT};
    border-radius: 10px;
    padding: 6px 10px;
}}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus, QTextEdit:focus {{
    border: 1px solid {ACCENT_MAIN};
    outline: none;
}}
/* 콤보박스 팝업(검은 배경 방지) */
QComboBox QAbstractItemView {{
    background: {BG_MAIN};
    color: {FG_PRIMARY};
    selection-background-color: {BG_SOFT};
    selection-color: {FG_PRIMARY};
    border: 1px solid {BORDER_SOFT};
}}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox::down-arrow {{ width: 10px; height: 10px; }}

/* 버튼 — 기본 */
QPushButton {{
    background: {BG_MAIN};
    color: {FG_PRIMARY};
    border: 1px solid {BORDER_SOFT};
    border-radius: 10px;
    padding: 8px 14px;
    font-weight: 600;
}}
QPushButton:hover {{ background: {BG_SOFT}; }}

/* 버튼 — 개별 ID 색상 */
QPushButton#OpenButton {{
    background: #3b82f6;           /* 파랑 */
    color: #ffffff;
    border: 1px solid #3b82f6;
}}
QPushButton#OpenButton:hover {{ filter: brightness(0.95); }}

QPushButton#PlayButton {{
    background: {WARN_AMBER};      /* 주황 */
    color: #ffffff;
    border: 1px solid {WARN_AMBER};
}}
QPushButton#PlayButton:hover {{ filter: brightness(0.95); }}

QPushButton#GenerateButton {{
    background: {GOOD_GREEN};      /* 초록 */
    color: #ffffff;
    border: 1px solid {GOOD_GREEN};
}}
QPushButton#GenerateButton:hover {{ filter: brightness(0.95); }}

/* 그룹박스 */
QGroupBox {{
    border: 1px solid {BORDER_SOFT};
    border-radius: 12px;
    margin-top: 14px;
    padding-top: 10px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #334155;
    background: {BG_MAIN};
}}

/* 스크롤영역 */
QScrollArea {{ background: transparent; border: none; }}

/* 프리뷰 (QWidget 기반) */
QWidget#PreviewView {{
    background: {BG_SOFT};
    border: 1px solid {BORDER_SOFT};
    border-radius: 12px;
}}

/* 로그창 */
QTextEdit {{
    background: {BG_MAIN};
    border: 1px solid {BORDER_SOFT};
    border-radius: 10px;
    padding: 8px 10px;
}}

/* 스크롤바(라이트) */
QScrollBar:vertical {{
    background: transparent; width: 10px; margin: 4px 2px 4px 2px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER_SOFT}; border-radius: 5px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px; background: transparent; border: none;
}}
QScrollBar:horizontal {{
    background: transparent; height: 10px; margin: 2px 4px 2px 4px;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER_SOFT}; border-radius: 5px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px; background: transparent; border: none;
}}
"""
