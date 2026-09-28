# config.py
"""앱 메타 정보, 제한값, 기본값, 파일 경로를 한곳에서 관리합니다.

import 시점에는 파일 시스템을 건드리지 않습니다. 경로가 필요한 곳에서 함수를 호출하면
그때 폴더를 만들고 결과를 캐시합니다.
"""
from __future__ import annotations

import functools
import os
import sys
import tempfile
from pathlib import Path

from versioninfo import APP_VERSION

# --- 앱 메타 정보 ---
APP_NAME = "APEX GIF MAKER"
APP_ID = "ApexGIFMaker"                 # 파일·폴더 이름으로 쓰는 식별자
APP_EXE_NAME = f"{APP_ID}.exe"
USER_AGENT = f"{APP_ID}/{APP_VERSION}"   # GitHub·다운로드 요청에 붙이는 이름 (없으면 GitHub이 403으로 막음)
APP_USER_MODEL_ID = "deuxdoom.ApexGIFMaker"   # Windows 작업 표시줄 그룹/고정용

REPO_OWNER = "deuxdoom"
REPO_NAME = "APEXGIFMAKER"
REPO_URL = f"https://github.com/{REPO_OWNER}/{REPO_NAME}"
RELEASES_URL = f"{REPO_URL}/releases/latest"
CHANGELOG_URL = f"{REPO_URL}/blob/main/CHANGELOG.md"
ISSUES_URL = f"{REPO_URL}/issues"
SPONSOR_URL = f"https://github.com/sponsors/{REPO_OWNER}"
YOUTUBE_URL = "https://www.youtube.com/@LE_SSERAFIM"

# --- 구간 길이 제한 (초) ---
TRIM_MIN_SEC = 1.0
TRIM_MAX_SEC = 30.0
RECO_MAX_SEC = 15.0            # 이보다 길면 경고 색으로 표시 (생성은 가능)
DEFAULT_SELECTION_SEC = 6.0    # 동영상을 열었을 때 처음 선택되는 길이

# --- GIF 기본값 (Flydigi APEX 시리즈 스크린) ---
DEFAULT_WIDTH = 160
DEFAULT_HEIGHT = 80
DEFAULT_FPS = 12
SIZE_MIN, SIZE_MAX = 8, 4096
FPS_MIN, FPS_MAX = 1, 60

VIDEO_EXTENSIONS = (".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".wmv", ".flv", ".ts", ".gif")


def _app_dir() -> Path:
    """실행 파일(.exe) 또는 프로젝트 루트 경로를 반환합니다."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


APP_DIR = _app_dir()
# 배포판은 PyInstaller의 내용물 폴더 이름을 _internal 대신 bin으로 바꿔서 씁니다(apexgifmaker.spec).
# ffmpeg·ffprobe도 같은 bin 폴더에 두므로, 사용자가 보는 폴더는 exe와 bin 두 개뿐입니다.
TOOLS_DIR_NAME = "bin"
BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", APP_DIR))
ASSETS_DIR = BUNDLE_DIR / "assets"


def _is_writable(folder: Path) -> bool:
    try:
        folder.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryFile(dir=folder):
            pass
        return True
    except OSError:
        return False


@functools.lru_cache(maxsize=None)
def data_dir() -> Path:
    """설정과 도구(bin)를 둘 폴더입니다.

    포터블 배포이므로 실행 폴더를 우선 사용하고, 쓸 수 없는 위치(예: Program Files)라면
    사용자 폴더(%LOCALAPPDATA%\\ApexGIFMaker)를 사용합니다.
    """
    if _is_writable(APP_DIR):
        return APP_DIR
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    folder = Path(base) / APP_ID if base else Path.home() / f".{APP_ID.lower()}"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def settings_path() -> Path:
    return data_dir() / "settings.json"


def tools_dir() -> Path:
    """ffmpeg·ffprobe를 두는 폴더. 배포판은 exe 옆 bin(번들 폴더와 같음), 소스 실행은 프로젝트의 bin입니다.
    실행 폴더에 쓸 수 없으면 %LOCALAPPDATA%\\ApexGIFMaker\\bin을 씁니다."""
    return data_dir() / TOOLS_DIR_NAME


def legacy_ffmpeg_dir() -> Path:
    """v2.x가 ffmpeg를 두던 폴더입니다. (처음 실행할 때 bin으로 옮김)"""
    return APP_DIR / "ffmpeg-bin"


@functools.lru_cache(maxsize=None)
def temp_dir() -> Path:
    """팔레트, 구간 재생용 클립 같은 임시 파일을 두는 폴더입니다."""
    folder = Path(tempfile.gettempdir()) / APP_ID
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def asset_path(name: str) -> Path:
    return ASSETS_DIR / name


def legacy_cache_dir() -> Path:
    """v2.x가 실행 폴더에 만들던 캐시 폴더입니다. (시작 시 정리 대상)"""
    return APP_DIR / "cache"
