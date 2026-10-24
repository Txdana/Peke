"""SearXNG client (JSON API). Standard library only; failures carry an actionable reason."""
import json
import logging
import math
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from peke import __version__

logger = logging.getLogger(__name__)
DEFAULT_LOCAL_CANDIDATES = ("http://127.0.0.1:8888", "http://127.0.0.1:8080")
MAX_BYTES = 5 * 1024 * 1024
MAX_URL_LENGTH = 8192
_TRACKING = re.compile(r"^(utm_|fbclid|gclid|ref$|ref_)")


class SearchError(Exception):
    """Search could not be performed; the message says why and how to fix it."""


@dataclass
class SearchHit:
    url: str
    title: str
    snippet: str
    engine: str = ""

    def to_dict(self) -> dict[str, str]:
        return dict(self.__dict__)


def clean_url(url: str) -> str:
    """Drop tracking parameters and fragments, keep everything else as written."""
    p = urllib.parse.urlsplit(url)
    q = [(k, v) for k, v in urllib.parse.parse_qsl(p.query, max_num_fields=500) if not _TRACKING.match(k)]
    return urllib.parse.urlunsplit((p.scheme, p.netloc, p.path, urllib.parse.urlencode(q), ""))


def normalize_url(url: str) -> str:
    p = urllib.parse.urlsplit(url)
    q = [(k, v) for k, v in urllib.parse.parse_qsl(p.query, max_num_fields=500) if not _TRACKING.match(k)]
    path = p.path.rstrip("/") or "/"
    return urllib.parse.urlunsplit((p.scheme.lower(), p.netloc.lower(), path, urllib.parse.urlencode(q), ""))


class SearxngClient:
    def __init__(self, base_url: str, timeout: float = 10.0) -> None:
        raw_url = base_url.strip()
        try:
            parts = urllib.parse.urlsplit(raw_url)
            # Accessing .port validates malformed/out-of-range ports as well.
            _ = parts.port
        except ValueError as exc:
            raise SearchError("SEARXNG_URL has an invalid URL or port") from exc
        if parts.scheme.lower() not in {"http", "https"} or not parts.hostname or not parts.netloc:
            raise SearchError("SEARXNG_URL must be an http(s):// URL")
        if parts.username is not None or parts.password is not None:
            raise SearchError("SEARXNG_URL must not contain a username or password")
        if parts.query or parts.fragment:
            raise SearchError("SEARXNG_URL must be a base URL without a query string or fragment")
        if any(char.isspace() or ord(char) < 32 for char in raw_url):
            raise SearchError("SEARXNG_URL contains whitespace or an invalid control character")
        if "?" in raw_url or "#" in raw_url:
            raise SearchError("SEARXNG_URL must be a base URL without a query string or fragment")
        self.base_url = urllib.parse.urlunsplit((parts.scheme.lower(), parts.netloc, parts.path.rstrip("/"), "", ""))
        if isinstance(timeout, bool):
            raise SearchError("SearXNG timeout must be a positive finite number")
        try:
            parsed_timeout = float(timeout)
        except (TypeError, ValueError) as exc:
            raise SearchError("SearXNG timeout must be a positive finite number") from exc
        if not math.isfinite(parsed_timeout) or parsed_timeout <= 0:
            raise SearchError("SearXNG timeout must be a positive finite number")
        self.timeout = min(120.0, max(0.1, parsed_timeout))
        # (engine, reason) pairs SearXNG reported as unresponsive for the most recent query, so callers
        # can tell "no matches" apart from "every upstream engine failed" (e.g. no internet).
        self.last_unresponsive: list[tuple[str, str]] = []

    def _get(self, params: dict[str, str]) -> dict[str, Any]:
        url = f"{self.base_url}/search?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(
            url, headers={"Accept": "application/json", "User-Agent": f"Peke/{__version__}"}
        )
        try:
            # Scheme validated in __init__ to only allow http and https
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:  # nosec B310
                body = resp.read(MAX_BYTES + 1)
        except urllib.error.HTTPError as exc:
            if exc.code == 403:
                raise SearchError("SearXNG refused JSON (403): add 'json' under search.formats in settings.yml") from exc
            if exc.code == 429:
                raise SearchError("SearXNG rate-limited this request (429)") from exc
            raise SearchError(f"SearXNG returned HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise SearchError(f"SearXNG not reachable at {self.base_url}") from exc
        if len(body) > MAX_BYTES:
            raise SearchError("SearXNG response too large")
        try:
            data = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError, RecursionError) as exc:
            raise SearchError("SearXNG did not return JSON (is the json format enabled?)") from exc
        if not isinstance(data, dict):
            raise SearchError("Unexpected SearXNG response shape: expected a JSON object")
        return data

    def search(self, query: str, time_range: str | None = None, pages: int = 1, max_results: int = 0,
               per_domain: int = 2) -> list[SearchHit]:
        query = query.strip()
        if not query:
            raise SearchError("Search query cannot be empty")
        if len(query) > 500:
            raise SearchError("Search query must be 500 characters or fewer")
        if time_range not in {None, "day", "month", "year"}:
            raise SearchError("time_range must be day, month, year, or None")
        if isinstance(pages, bool) or not isinstance(pages, int) or pages < 1:
            raise SearchError("pages must be a positive integer")
        if isinstance(max_results, bool) or not isinstance(max_results, int) or max_results < 0:
            raise SearchError("max_results must be a non-negative integer")
        if isinstance(per_domain, bool) or not isinstance(per_domain, int) or per_domain < 0:
            raise SearchError("per_domain must be a non-negative integer")
        # Bound pagination and network work even for programmatic callers.
        pages = min(pages, 10)
        hits: list[SearchHit] = []
        seen: set[str] = set()
        domains: dict[str, int] = {}
        for page in range(1, pages + 1):
            params = {"q": query, "format": "json", "pageno": str(page), "safesearch": "1"}
            if time_range:
                params["time_range"] = time_range
            response = self._get(params)
            self.last_unresponsive = self._unresponsive(response)
            results = response.get("results")
            if not isinstance(results, list):
                raise SearchError("SearXNG returned JSON without a valid 'results' list; enable the JSON format")
            if not results:
                break
            for item in results:
                url = item.get("url") if isinstance(item, dict) else None
                if (
                    not isinstance(url, str)
                    or len(url) > MAX_URL_LENGTH
                    or not url.lower().startswith(("http://", "https://"))
                ):
                    continue
                try:
                    parsed_url = urllib.parse.urlsplit(url)
                    _ = parsed_url.port
                except ValueError:
                    continue
                if (
                    parsed_url.scheme.lower() not in {"http", "https"}
                    or not parsed_url.hostname
                    or not parsed_url.netloc
                    or parsed_url.username is not None
                    or parsed_url.password is not None
                    or any(char.isspace() or ord(char) < 32 for char in url)
                ):
                    continue
                try:
                    key = normalize_url(url)
                    cleaned_url = clean_url(url)
                except ValueError:
                    # An excessive number of query fields is not a useful result.
                    continue
                host = parsed_url.netloc.lower()
                if key in seen or (per_domain and domains.get(host, 0) >= per_domain):
                    continue
                seen.add(key)
                domains[host] = domains.get(host, 0) + 1
                hits.append(SearchHit(cleaned_url, str(item.get("title", ""))[:200], str(item.get("content", ""))[:400],
                                      str(item.get("engine", ""))))
                if max_results and len(hits) >= max_results:
                    return hits
        return hits

    @staticmethod
    def _unresponsive(response: dict[str, Any]) -> list[tuple[str, str]]:
        raw = response.get("unresponsive_engines")
        out: list[tuple[str, str]] = []
        if isinstance(raw, list):
            for item in raw[:100]:
                if isinstance(item, (list, tuple)) and len(item) >= 2:
                    out.append((str(item[0])[:80], str(item[1])[:200]))
        return out

    def status(self) -> dict[str, Any]:
        """Check the actual JSON search API, not merely whether a host returns JSON."""
        try:
            data = self._get({"q": "peke", "format": "json"})
            if not isinstance(data.get("results"), list):
                raise SearchError("SearXNG is reachable, but its JSON results format is disabled or misconfigured")
            self.last_unresponsive = self._unresponsive(data)
            status: dict[str, Any] = {"available": True, "url": self.base_url, "reason": "ok"}
            if self.last_unresponsive:
                # The local API works; this says nothing about whether upstream engines do.
                status["engines_unresponsive"] = len(self.last_unresponsive)
                status["upstream_note"] = (
                    f"{len(self.last_unresponsive)} upstream engine(s) did not respond for the health query; "
                    "check your internet connection if searches return nothing."
                )
            return status
        except SearchError as exc:
            return {"available": False, "url": self.base_url, "reason": str(exc)}


def detect(configured_url: str | None, timeout: float = 1.5) -> tuple[SearxngClient | None, dict[str, Any]]:
    """Use the configured instance, else look for a local one. Never raises."""
    candidates = [configured_url] if configured_url else list(DEFAULT_LOCAL_CANDIDATES)
    last: dict[str, Any] = {"available": False, "url": None, "reason": "SEARXNG_URL not set and no local instance found"}
    for url in candidates:
        try:
            client = SearxngClient(url, timeout=timeout if not configured_url else max(timeout, 5.0))
        except SearchError as exc:
            last = {"available": False, "url": url, "reason": str(exc)}
            continue
        status = client.status()
        if status["available"]:
            client.timeout = 10.0
            return client, status
        last = status
    return None, last
