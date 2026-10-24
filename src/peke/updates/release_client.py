"""GitHub Releases API client for discovering Peke updates."""
import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx
from packaging.version import InvalidVersion, Version

from peke import __version__

logger = logging.getLogger(__name__)

REPO = "Txdana/Peke"
API_URL = f"https://api.github.com/repos/{REPO}/releases"
CACHE_TTL_SECONDS = 300.0

_RELEASE_CACHE: dict[str, Any] = {"timestamp": 0.0, "releases": []}


@dataclass
class ReleaseInfo:
    version: str
    tag_name: str
    prerelease: bool
    draft: bool
    html_url: str
    body: str
    published_at: str
    wheel_name: str
    wheel_url: str
    sums_url: str
    requirements_url: str


class ReleaseClientError(Exception):
    """GitHub Release API operation failed."""


class ReleaseClient:
    def __init__(self, repo: str = REPO, timeout: float = 10.0) -> None:
        self.repo = repo
        self.timeout = timeout

    def fetch_releases(self, force_refresh: bool = False) -> list[ReleaseInfo]:
        now = time.time()
        if not force_refresh and _RELEASE_CACHE["releases"] and (now - _RELEASE_CACHE["timestamp"] < CACHE_TTL_SECONDS):
            return _RELEASE_CACHE["releases"]

        url = f"https://api.github.com/repos/{self.repo}/releases"
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28", "User-Agent": f"Peke/{__version__}"}

        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(url, headers=headers)
                if resp.status_code != 200:
                    raise ReleaseClientError(f"GitHub Releases API returned HTTP {resp.status_code}")

                data = resp.json()
                releases = []
                for item in data:
                    if item.get("draft"):
                        continue

                    tag = item.get("tag_name", "")
                    ver_str = tag.lstrip("v")
                    try:
                        Version(ver_str)
                    except InvalidVersion:
                        continue

                    assets = {a["name"]: a.get("browser_download_url", "") for a in item.get("assets", [])}
                    wheels = [name for name in assets if name.startswith("peke-") and name.endswith(".whl")]
                    if len(wheels) != 1 or "SHA256SUMS" not in assets or "requirements-hashed.txt" not in assets:
                        continue

                    wheel_name = wheels[0]
                    releases.append(
                        ReleaseInfo(
                            version=ver_str,
                            tag_name=tag,
                            prerelease=bool(item.get("prerelease")),
                            draft=False,
                            html_url=item.get("html_url", ""),
                            body=item.get("body", ""),
                            published_at=item.get("published_at", ""),
                            wheel_name=wheel_name,
                            wheel_url=assets[wheel_name],
                            sums_url=assets["SHA256SUMS"],
                            requirements_url=assets["requirements-hashed.txt"],
                        )
                    )

                _RELEASE_CACHE["timestamp"] = now
                _RELEASE_CACHE["releases"] = releases
                return releases
        except Exception as exc:
            if isinstance(exc, ReleaseClientError):
                raise
            raise ReleaseClientError(f"Failed to fetch release metadata: {exc}") from exc

    def get_latest_release(self, channel: str = "stable") -> ReleaseInfo | None:
        releases = self.fetch_releases()
        for r in releases:
            if channel == "stable" and r.prerelease:
                continue
            return r
        return None
