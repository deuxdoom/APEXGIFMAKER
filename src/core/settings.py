# settings.py
"""settings.json 읽기·쓰기와 이전 버전 파일 정리를 담당합니다."""
from __future__ import annotations

import json
import os
import shutil
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping

from .. import i18n
from . import config
from .gif import GifOptions

SETTINGS_VERSION = 3
THEMES = ("dark", "light", "system")
LANGUAGES = ("auto", *i18n.LANGUAGES)   # auto | ko | en | es | ja | zh-Hans | zh-Hant


@dataclass
class Settings:
    options: GifOptions = field(default_factory=GifOptions)
    output_dir: str = ""          # 비어 있으면 실행 폴더에 저장
    last_open_dir: str = ""
    theme: str = "dark"           # dark(기본, 남색) | light | system
    language: str = "auto"        # auto 또는 i18n.LANGUAGES 중 하나
    confirm_exit: bool = True
    auto_update_tools: bool = True    # 켤 때 ffmpeg 새 버전을 확인해서 자동으로 받기
    log_expanded: bool = False
    window_geometry: str = ""     # 최대화하지 않은 창의 "x,y,w,h"
    window_maximized: bool = False

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["version"] = SETTINGS_VERSION
        return data

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "Settings":
        if not isinstance(data, Mapping):
            return cls()

        def text(key: str) -> str:
            value = data.get(key)
            return value if isinstance(value, str) else ""

        output_dir = text("output_dir")
        legacy_output = text("output_path")          # v2.x: 마지막 출력 파일 경로
        if not output_dir and legacy_output:
            output_dir = str(Path(legacy_output).parent)

        theme = data.get("theme")
        language = data.get("language")
        return cls(
            options=GifOptions.from_dict(data.get("options")),
            output_dir=output_dir,
            last_open_dir=text("last_open_dir"),
            theme=theme if theme in THEMES else "dark",
            language=language if language in LANGUAGES else "auto",
            confirm_exit=bool(data.get("confirm_exit", True)),
            auto_update_tools=bool(data.get("auto_update_tools", True)),
            log_expanded=bool(data.get("log_expanded", False)),
            window_geometry=text("window_geometry"),
            window_maximized=bool(data.get("window_maximized", False)),
        )


def load_settings(path: Path | None = None) -> tuple[Settings, str | None]:
    """설정을 읽습니다. 파일이 깨졌으면 기본값과 오류 메시지를 함께 반환합니다."""
    path = path or config.settings_path()
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return Settings(), None
    except OSError as exc:
        return Settings(), str(exc)
    try:
        return Settings.from_dict(json.loads(raw)), None
    except ValueError as exc:
        return Settings(), str(exc)


def save_settings(settings: Settings, path: Path | None = None) -> None:
    """임시 파일에 쓴 뒤 교체해서, 저장 중에 꺼져도 설정 파일이 깨지지 않게 합니다."""
    path = path or config.settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(settings.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def cleanup_legacy_cache() -> list[str]:
    """v2.x가 실행 폴더의 cache/에 쌓아 둔 프리뷰·썸네일·팔레트 파일을 지웁니다."""
    root = config.legacy_cache_dir()
    if not root.is_dir():
        return []
    removed = []
    for name in ("previews", "timeline", "palette.png", "preview_play.mp4"):
        entry = root / name
        try:
            if entry.is_dir():
                shutil.rmtree(entry)
                removed.append(name)
            elif entry.is_file():
                entry.unlink()
                removed.append(name)
        except OSError:
            pass
    try:
        root.rmdir()   # 비어 있을 때만 지워집니다.
    except OSError:
        pass
    return removed
