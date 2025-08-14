# updater.py
import json, urllib.request
from typing import Tuple

def normalize_version(v: str) -> tuple:
    try:
        v=v.strip(); v=v[1:] if v[:1].lower()=="v" else v
        nums=[int(''.join(ch for ch in p if ch.isdigit()) or 0) for p in v.split(".")]
        while len(nums)<3: nums.append(0)
        return tuple(nums[:3])
    except Exception:
        return tuple()

def check_latest(owner: str, repo: str, current_version: str, timeout=5) -> Tuple[str, bool, str | None]:
    """GitHub latest tag, is_newer, error_message"""
    api = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
    try:
        req = urllib.request.Request(api, headers={
            "User-Agent": f"{repo}/{current_version}",
            "Accept": "application/vnd.github+json",
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8","ignore"))
        tag = str(data.get("tag_name","")).strip()
        if not tag:
            return "", False, "no tag_name"
        cur = normalize_version(current_version)
        new = normalize_version(tag)
        return tag, (new and cur and new > cur), None
    except Exception as e:
        return "", False, str(e)
