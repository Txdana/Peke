"""Scrapling fetch adapters. Scrapling remains a normal runtime dependency."""
import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Any

from peke.config import Settings
from peke.profile import Profile, redact_url

logger = logging.getLogger(__name__)
MAX_RESPONSE_BYTES = 50 * 1024 * 1024


class FetchError(Exception):
    """Fetching failed or returned unusable content."""


@dataclass
class FetchResult:
    url: str
    status: int
    content_type: str
    text: str
    json: Any | None
    elapsed_ms: float
    bypass_detected: bool = False
    raw_html: str | None = None


def _clean_html(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style|noscript)\b[^>]*>.*?</\1\s*>", " ", raw)
    raw = re.sub(r"(?s)<[^>]+>", " ", raw)
    return re.sub(r"\s+", " ", raw).strip()


def fetch(profile: Profile, settings: Settings) -> FetchResult:
    """Fetch one profile URL using the current Scrapling fetcher API."""
    try:
        from scrapling.fetchers import Fetcher, StealthyFetcher
    except ImportError as exc:
        raise FetchError("Scrapling is not installed. Install with: pip install 'scrapling[fetchers]'") from exc
    start = time.perf_counter()
    try:
        if profile.fetcher == "stealthy":
            kwargs: dict[str, Any] = {"headers": profile.headers, "timeout": int(settings.fetch_timeout * 1000)}
            if profile.method == "POST":
                raise FetchError("StealthyFetcher currently supports GET only in Peke Phase 1.")
            response = StealthyFetcher.fetch(profile.url, **kwargs, **({"params": profile.params} if profile.params else {}))
        else:
            fetcher = Fetcher()
            method = profile.method.lower()
            request = getattr(fetcher, method, None)
            if request is None:
                raise FetchError(f"Scrapling Fetcher does not support method {profile.method}")
            kwargs = {"headers": profile.headers, "params": profile.params, "timeout": settings.fetch_timeout}
            if profile.body is not None:
                kwargs["json"] = profile.body
            response = request(profile.url, **kwargs)
    except FetchError:
        raise
    except Exception as exc:
        logger.exception("Scrapling request failed for %s", redact_url(profile.url))
        raise FetchError(f"Fetch failed for {redact_url(profile.url)}: {type(exc).__name__}") from exc
    status = int(getattr(response, "status", 0) or 0)
    headers = {str(k).lower(): str(v) for k, v in dict(getattr(response, "headers", {}) or {}).items()}
    content_type = headers.get("content-type", "")
    body = getattr(response, "body", b"")
    if isinstance(body, bytes):
        if len(body) > MAX_RESPONSE_BYTES:
            raise FetchError(f"Response from {redact_url(profile.url)} exceeds the 50 MiB safety limit")
        raw = body.decode("utf-8", errors="replace")
    else:
        raw = str(getattr(response, "text", "") or "")
        if len(raw.encode("utf-8", errors="replace")) > MAX_RESPONSE_BYTES:
            raise FetchError(f"Response from {redact_url(profile.url)} exceeds the 50 MiB safety limit")
    if not raw.strip():
        raise FetchError(f"Empty response body from {redact_url(profile.url)}")
    if status < 200 or status >= 300:
        raise FetchError(f"HTTP {status} from {redact_url(profile.url)}")
    parsed = None
    is_json = "json" in content_type.lower()
    if is_json or raw.lstrip().startswith(("{", "[")):
        try:
            parsed = json.loads(raw)
            is_json = True
        except json.JSONDecodeError:
            is_json = False
    challenge = bool(re.search(r"(?i)(checking your browser|verify you are human|just a moment\.\.\.|cf-challenge|challenge-platform)", raw))
    text = raw if is_json else _clean_html(raw)
    return FetchResult(profile.url, status, content_type, text, parsed if is_json else None,
                       (time.perf_counter() - start) * 1000, not challenge and profile.fetcher == "stealthy", raw if not is_json else None)
