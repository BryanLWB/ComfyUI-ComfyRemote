"""Cached, read-only checks against the official stable GitHub release."""
import asyncio
import re
import time

import aiohttp

from . import __version__

RELEASE_API = "https://api.github.com/repos/BryanLWB/ComfyUI-ComfyRemote/releases/latest"
RELEASE_PAGE = "https://github.com/BryanLWB/ComfyUI-ComfyRemote/releases/tag/"


def release_update(release, current):
    tag = release.get("tag_name", "")
    if release.get("draft") or release.get("prerelease"):
        return None
    if not isinstance(tag, str) or not re.fullmatch(r"v\d{1,6}\.\d{1,6}\.\d{1,6}", tag):
        return None
    version = tag[1:]
    if tuple(map(int, version.split("."))) <= tuple(map(int, current.split("."))):
        return None
    return {"version": version, "url": RELEASE_PAGE + tag}


class UpdateChecker:
    def __init__(self):
        self.lock = asyncio.Lock()
        self.next_check = 0.0
        self.update = None

    async def check(self):
        async with self.lock:
            if time.monotonic() >= self.next_check:
                self.next_check = time.monotonic() + 15 * 60
                try:
                    async with aiohttp.ClientSession(
                        timeout=aiohttp.ClientTimeout(total=8), trust_env=False,
                        headers={"Accept": "application/vnd.github+json",
                                 "User-Agent": "ComfyRemote-update-check"},
                    ) as session, session.get(RELEASE_API, allow_redirects=False) as response:
                        response.raise_for_status()
                        release = await response.json()
                        if not isinstance(release, dict):
                            raise TypeError("Invalid release response")
                        self.update = release_update(release, __version__)
                    self.next_check = time.monotonic() + 6 * 60 * 60
                except (aiohttp.ClientError, OSError, ValueError, TypeError, TimeoutError):
                    pass
            return {"current_version": __version__, "update": self.update}
