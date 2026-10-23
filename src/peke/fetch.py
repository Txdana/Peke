"""Scrapling wrapper module for fetching target URLs in Peke."""

import json
from dataclasses import dataclass, field
from typing import Any

from scrapling import Fetcher, StealthyFetcher

SENSITIVE_HEADER_KEYS = {
    "authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
    "api-key",
    "secret",
    "token",
    "access-token",
    "bearer",
}


def sanitize_headers(headers: dict[str, str]) -> dict[str, str]:
    """Return a copy of headers with sensitive values redacted for safe logging."""
    sanitized = {}
    for key, value in headers.items():
        if key.lower() in SENSITIVE_HEADER_KEYS:
            sanitized[key] = "[REDACTED]"
        else:
            sanitized[key] = value
    return sanitized


class FetchError(Exception):
    """Raised when fetching fails."""


@dataclass
class FetchResult:
    """Class representing the output of a fetch operation."""

    url: str
    status_code: int
    headers: dict[str, str] = field(default_factory=dict)
    text: str = ""
    json_data: dict[str, Any] | list | None = None
    is_json: bool = False
    fetcher_used: str = "Fetcher"
    cloudflare_bypassed: bool = False


def fetch_target(
    url: str,
    fetcher_type: str = "Fetcher",
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
    timeout: int = 30,
) -> FetchResult:
    """Fetch content from the target URL using Scrapling Fetcher or StealthyFetcher.

    :param url: Target URL to fetch.
    :param fetcher_type: "Fetcher" or "StealthyFetcher".
    :param headers: Optional HTTP headers dictionary.
    :param params: Optional query parameters dictionary.
    :param timeout: Request timeout in seconds.
    :return: FetchResult object containing response data and metadata.
    :raises FetchError: If fetching fails.
    """
    raw_headers = headers or {}
    params = params or {}

    try:
        if fetcher_type.lower() in ("stealthyfetcher", "stealthy", "stealth"):
            stealth_fetcher = StealthyFetcher()
            response = stealth_fetcher.fetch(
                url,
                headers=raw_headers,
                params=params,
                timeout=timeout * 1000 if timeout else 30000,
            )
            used_name = "StealthyFetcher"
            cf_bypassed = True
        else:
            response = Fetcher.get(
                url,
                headers=raw_headers,
                params=params,
                timeout=timeout,
            )
            used_name = "Fetcher"
            cf_bypassed = False

    except Exception as e:
        raise FetchError(f"Fetch failed for '{url}' using {fetcher_type}: {e}")

    if response is None:
        raise FetchError(f"No response returned for URL '{url}'")

    status_code = getattr(response, "status", 200)
    resp_headers = dict(getattr(response, "headers", {}) or {})
    sanitized_resp_headers = sanitize_headers(resp_headers)

    # Retrieve raw text body from response
    body_bytes = getattr(response, "body", b"")
    if isinstance(body_bytes, bytes) and body_bytes:
        text_content = body_bytes.decode("utf-8", errors="ignore")
    elif getattr(response, "text", None):
        text_content = str(response.text)
    else:
        text_content = getattr(response, "html_content", "") or ""

    is_json = False
    json_data = None

    # Check if response is clean JSON directly or via content-type / response.json()
    content_type = str(resp_headers.get("content-type", "")).lower()
    if ("application/json" in content_type or not content_type) and callable(
        getattr(response, "json", None)
    ):
        try:
            json_data = response.json()
            if json_data is not None:
                is_json = True
        except Exception:
            pass

    if not is_json and text_content.strip().startswith(("{", "[")):
        try:
            json_data = json.loads(text_content)
            is_json = True
        except Exception:
            pass

    return FetchResult(
        url=url,
        status_code=status_code,
        headers=sanitized_resp_headers,
        text=text_content,
        json_data=json_data,
        is_json=is_json,
        fetcher_used=used_name,
        cloudflare_bypassed=cf_bypassed,
    )
