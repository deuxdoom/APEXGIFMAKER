# updater.py
"""GitHub 최신 릴리즈를 확인하고, 자동 업데이트에 쓸 ZIP 자산을 고릅니다.

3.0.0부터 자동 업데이트는 SHA-256 검증을 전제로 합니다.
- GitHub가 자산마다 계산해 주는 `digest`(sha256:...)가 있어야 자동 업데이트 대상이 됩니다.
- 릴리즈 본문(RELEASE.md)에 적힌 SHA-256이 있으면 digest와도 대조해서, 다르면 거부합니다.
조건을 채우지 못한 릴리즈는 자산을 비워서(asset=None) 다운로드 페이지 안내로만 이어집니다.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from . import config

API_URL = f"https://api.github.com/repos/{config.REPO_OWNER}/{config.REPO_NAME}/releases/latest"
DOWNLOAD_PREFIX = f"https://github.com/{config.REPO_OWNER}/{config.REPO_NAME}/releases/download/"
CHECK_TIMEOUT = 8.0
MAX_ASSET_SIZE = 500 * 1024 * 1024
MAX_HIGHLIGHTS = 5

_VERSION_RE = re.compile(r"v?(\d+)\.(\d+)\.(\d+)")
_DIGEST_RE = re.compile(r"sha256:([0-9a-fA-F]{64})")
_HEX64_RE = re.compile(r"(?<![0-9a-fA-F])([0-9a-fA-F]{64})(?![0-9a-fA-F])")
_ASSET_NAME_RE = re.compile(rf"{config.APP_ID}_v?\d+\.zip", re.IGNORECASE)
_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]*\)")


class UpdateCheckError(RuntimeError):
    """조회 자체가 실패했을 때. reason: network | http | rate_limited | invalid"""

    def __init__(self, reason: str, detail: str = ""):
        super().__init__(detail or reason)
        self.reason = reason
        self.detail = detail


@dataclass(frozen=True)
class UpdateAsset:
    name: str
    url: str
    size: int
    sha256: str


@dataclass(frozen=True)
class ReleaseInfo:
    tag: str
    version: tuple[int, int, int]
    name: str
    html_url: str
    body: str
    published_at: str
    asset: UpdateAsset | None
    problem: str = ""     # asset이 없는 이유: no_asset | no_digest | digest_mismatch

    @property
    def version_text(self) -> str:
        return ".".join(str(part) for part in self.version)


def parse_version(text: str) -> tuple[int, int, int] | None:
    """`v2.5.2` 또는 `2.5.2`만 받습니다. 세 자리가 아니면 None입니다."""
    match = _VERSION_RE.fullmatch((text or "").strip())
    if not match:
        return None
    major, minor, patch = (int(group) for group in match.groups())
    return major, minor, patch


def is_newer(latest: str, current: str) -> bool:
    new, cur = parse_version(latest), parse_version(current)
    return bool(new and cur and new > cur)


def asset_name(version: str) -> str:
    """릴리즈 ZIP 이름: `ApexGIFMaker_v300.zip` (TVerDownloader와 같은 규칙)"""
    return f"{config.APP_ID}_v{version.replace('.', '')}.zip"


def body_sha256(body: str, name: str) -> str:
    """릴리즈 본문에서 해당 ZIP 이름 근처(같은 줄 또는 아래 네 줄)에 적힌 SHA-256을 찾습니다."""
    lines = (body or "").splitlines()
    for index, line in enumerate(lines):
        if name.lower() not in line.lower():
            continue
        for candidate in lines[index:index + 5]:
            match = _HEX64_RE.search(candidate)
            if match:
                return match.group(1).lower()
    return ""


def _select_asset(tag: str, assets: Any, body: str) -> tuple[UpdateAsset | None, str]:
    if not isinstance(assets, list):
        return None, "no_asset"
    problem = "no_asset"
    for item in assets:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if not isinstance(name, str) or not _ASSET_NAME_RE.fullmatch(name):
            continue
        size = item.get("size")
        url = f"{DOWNLOAD_PREFIX}{tag}/{name}"
        if (item.get("state") != "uploaded" or isinstance(size, bool) or not isinstance(size, int)
                or not 0 < size <= MAX_ASSET_SIZE or item.get("browser_download_url") != url):
            continue
        digest = item.get("digest")
        match = _DIGEST_RE.fullmatch(digest) if isinstance(digest, str) else None
        if match is None:
            problem = "no_digest"
            continue
        sha256 = match.group(1).lower()
        written = body_sha256(body, name)
        if written and written != sha256:
            problem = "digest_mismatch"
            continue
        return UpdateAsset(name, url, size, sha256), ""
    return None, problem


def parse_release(payload: Any) -> ReleaseInfo | None:
    """API 응답에서 정식 릴리즈 정보를 뽑습니다. 초안·사전 릴리즈·버전 형식이 틀린 태그는 None입니다."""
    if not isinstance(payload, dict) or payload.get("draft") or payload.get("prerelease"):
        return None
    tag = payload.get("tag_name")
    version = parse_version(tag) if isinstance(tag, str) else None
    if not isinstance(tag, str) or version is None:
        return None
    body = payload.get("body")
    body = body if isinstance(body, str) else ""
    asset, problem = _select_asset(tag, payload.get("assets"), body)
    html_url = payload.get("html_url")
    return ReleaseInfo(
        tag=tag, version=version,
        name=str(payload.get("name") or tag),
        html_url=html_url if isinstance(html_url, str) and html_url else config.RELEASES_URL,
        body=body, published_at=str(payload.get("published_at") or ""),
        asset=asset, problem=problem,
    )


def fetch_latest_release(timeout: float = CHECK_TIMEOUT) -> ReleaseInfo:
    request = urllib.request.Request(API_URL, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": config.USER_AGENT,
    })
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        if exc.code in (403, 429) and exc.headers.get("X-RateLimit-Remaining") == "0":
            raise UpdateCheckError("rate_limited", str(exc.headers.get("X-RateLimit-Reset") or "")) from None
        raise UpdateCheckError("http", f"HTTP {exc.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise UpdateCheckError("network", str(exc)) from None
    except ValueError as exc:
        raise UpdateCheckError("invalid", str(exc)) from None

    release = parse_release(payload)
    if release is None:
        raise UpdateCheckError("invalid", "no stable release")
    return release


def release_highlights(body: str, limit: int = MAX_HIGHLIGHTS) -> list[str]:
    """릴리즈 본문의 글머리 항목을 앞에서부터 limit개 뽑아 서식을 걷어 냅니다."""
    items: list[str] = []
    for raw in (body or "").splitlines():
        line = raw.strip()
        if not line.startswith(("- ", "* ")):
            continue
        text = _LINK_RE.sub(r"\1", line[2:])
        text = re.sub(r"[*_`]+", "", text).strip()
        if text:
            items.append(text)
        if len(items) >= limit:
            break
    return items
