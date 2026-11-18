# src/i18n
"""다국어 문자열 조회를 담당합니다.

지원 언어: 한국어, 영어, 스페인어, 일본어, 중국어 간체·번체. 그 밖의 언어 환경은 영어로 표시합니다.
언어 파일마다 `STRINGS` 사전을 두며, 영어(en.py)가 기준입니다. 번역이 빠진 키는 영어로 대체됩니다.
tools/check.py가 모든 언어의 키와 자리표시자가 영어와 일치하는지 검사합니다.
"""
from __future__ import annotations

import re

from . import en, es, ja, ko, zh_hans, zh_hant

DEFAULT_LANGUAGE = "en"

_TABLES: dict[str, dict[str, str]] = {
    "ko": ko.STRINGS,
    "en": en.STRINGS,
    "es": es.STRINGS,
    "ja": ja.STRINGS,
    "zh-Hans": zh_hans.STRINGS,
    "zh-Hant": zh_hant.STRINGS,
}

# 언어 선택 메뉴에 표시할 자국어 이름
LANGUAGE_NAMES: dict[str, str] = {
    "ko": "한국어",
    "en": "English",
    "es": "Español",
    "ja": "日本語",
    "zh-Hans": "简体中文",
    "zh-Hant": "繁體中文",
}
LANGUAGES: tuple[str, ...] = tuple(LANGUAGE_NAMES)

_TRADITIONAL_REGIONS = {"tw", "hk", "mo"}
_PLACEHOLDER = re.compile(r"\{(\w+)\}")

_language = DEFAULT_LANGUAGE


def detect_language(locale_name: str | None) -> str:
    """`ko-KR`, `zh-Hant-TW`, `zh_CN`, `es-419` 같은 로캘 이름을 지원 언어 코드로 바꿉니다.

    중국어는 스크립트(Hant/Hans)를 우선하고, 스크립트가 없으면 대만·홍콩·마카오 지역을 번체로 봅니다.
    """
    parts = [p for p in re.split(r"[-_.@]", (locale_name or "").lower()) if p]
    if not parts:
        return DEFAULT_LANGUAGE
    lang = parts[0]
    if lang in ("ko", "en", "es", "ja"):
        return lang
    if lang == "zh":
        rest = set(parts[1:])
        if "hant" in rest:
            return "zh-Hant"
        if "hans" in rest:
            return "zh-Hans"
        return "zh-Hant" if rest & _TRADITIONAL_REGIONS else "zh-Hans"
    return DEFAULT_LANGUAGE


def set_language(code: str) -> str:
    """언어 코드(또는 로캘 이름)를 적용하고, 실제로 적용된 코드를 반환합니다."""
    global _language
    _language = code if code in _TABLES else detect_language(code)
    return _language


def language() -> str:
    return _language


def tr(key: str, **kwargs: object) -> str:
    """현재 언어의 문자열을 반환합니다. 등록되지 않은 키는 키 이름을 그대로 반환합니다."""
    text = _TABLES[_language].get(key) or en.STRINGS.get(key)
    if text is None:
        return key
    return text.format(**kwargs) if kwargs else text


def keys() -> frozenset[str]:
    return frozenset(en.STRINGS)


def placeholders(text: str) -> set[str]:
    return set(_PLACEHOLDER.findall(text))


def validate() -> list[str]:
    """모든 언어가 영어와 같은 키와 자리표시자를 갖는지 검사해서 문제 목록을 반환합니다."""
    problems: list[str] = []
    reference = en.STRINGS
    for code, table in _TABLES.items():
        for key in sorted(reference.keys() - table.keys()):
            problems.append(f"[{code}] missing key: {key}")
        for key in sorted(table.keys() - reference.keys()):
            problems.append(f"[{code}] unknown key: {key}")
        for key in sorted(reference.keys() & table.keys()):
            text = table[key]
            if not text.strip():
                problems.append(f"[{code}] empty text: {key}")
            elif placeholders(text) != placeholders(reference[key]):
                problems.append(f"[{code}] placeholder mismatch: {key}")
    return problems
