"""Official REA CLI integration and portable endpoint-findings helpers.

Peke calls REA's documented browser-target and web-bundle commands through a
local loopback Chrome DevTools Protocol endpoint. REA remains optional; a missing
or incompatible installation never prevents profile-based extraction.
"""
import ipaddress
import json
import logging
import shlex
import subprocess
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse, urlsplit, urlunsplit

import yaml

from peke.config import Settings
from peke.profile import EndpointHint, Profile, redact_url

logger = logging.getLogger(__name__)


def _as_hint(item: Any) -> EndpointHint | None:
    if isinstance(item, str):
        item = {"path": item, "discovered_by": "rea"}
    if not isinstance(item, dict):
        return None
    path = (item.get("path") or item.get("url") or item.get("endpoint")
            or item.get("value") or item.get("candidate"))
    if not isinstance(path, str) or not path.strip():
        return None
    parsed = urlparse(path)
    if parsed.scheme and parsed.netloc:
        path = parsed.path or "/"
    if parsed.query:
        from urllib.parse import parse_qsl
        existing_params = item.get("params", item.get("parameters", {}))
        if not isinstance(existing_params, dict):
            existing_params = {}
        item = {**item, "params": {**dict(parse_qsl(parsed.query)), **existing_params}}
        path = parsed.path or path.split("?", 1)[0] or "/"
    method = str(item.get("method", "GET")).upper()
    if method not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
        method = "GET"
    params = item.get("params", item.get("parameters", {}))
    if isinstance(params, list):
        params = {str(x.get("name", x)) if isinstance(x, dict) else str(x): (x.get("value") if isinstance(x, dict) else "") for x in params}
    if not isinstance(params, dict):
        params = {}
    headers = item.get("headers", {})
    if not isinstance(headers, dict):
        headers = {}
    hidden = bool(item.get("hidden", item.get("not_referenced_in_html", item.get("referenced_in_html") is False)))
    return EndpointHint(method=method, path=path, size=item.get("size", item.get("response_size")),
                        params=params, headers={str(k): str(v) for k, v in headers.items()},
                        note=str(item.get("note", "")) or None, discovered_by="rea", hidden=hidden)


def _endpoint_candidates(data: Any) -> tuple[list[Any], dict[str, Any]]:
    """Read either Peke's compact fixture format or REA's Evidence JSON envelope."""
    if isinstance(data, list):
        return data, {}
    if not isinstance(data, dict):
        raise ValueError("REA output must be a JSON object or list")

    for key in ("endpoints", "findings", "routes"):
        value = data.get(key)
        if isinstance(value, list):
            headers = data.get("headers", {})
            return value, headers if isinstance(headers, dict) else {}

    normalized = data.get("normalized_result")
    if isinstance(normalized, dict):
        observations = normalized.get("observations")
        if isinstance(observations, dict):
            value = observations.get("endpoints", [])
            if isinstance(value, dict):
                value = value.get("items", value.get("candidates", value.get("findings", [])))
            if isinstance(value, list):
                return value, observations.get("headers", {}) if isinstance(observations.get("headers", {}), dict) else {}

    # Be tolerant of a future REA envelope that nests normalized_result or observations.
    for key in ("result", "evidence", "data"):
        nested = data.get(key)
        if isinstance(nested, dict):
            try:
                candidates, headers = _endpoint_candidates(nested)
                if candidates:
                    return candidates, headers
            except ValueError:
                pass
    raise ValueError("REA output contains no recognized endpoint observations")


def parse_rea_output(raw: str) -> list[EndpointHint]:
    """Parse compact fixtures or REA Evidence JSON into normalized endpoint hints."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"REA did not return valid JSON on stdout: {exc}") from exc
    candidates, global_headers = _endpoint_candidates(data)
    hints = []
    for item in candidates:
        hint = _as_hint(item)
        if hint is None:
            continue
        # REA can report method-like strings and other low-confidence inferences.
        # Keep only route-like paths, not arbitrary identifiers such as "GET" or "token".
        route = hint.path.strip()
        if not (route.startswith("/") or route.startswith("./") or "/" in route):
            continue
        merged_headers = {str(k): str(v) for k, v in global_headers.items()} if isinstance(global_headers, dict) else {}
        merged_headers.update(hint.headers)
        hint.headers = merged_headers
        if not hint.note:
            confidence = item.get("confidence") if isinstance(item, dict) else None
            mechanism = item.get("mechanism") if isinstance(item, dict) else None
            if confidence or mechanism:
                hint.note = "; ".join(str(part) for part in (mechanism, f"confidence: {confidence}" if confidence else None) if part)
        hints.append(hint)
    return hints


def load_findings(path: str | Path) -> list[EndpointHint]:
    file_path = Path(path)
    try:
        raw = yaml.safe_load(file_path.read_text(encoding="utf-8")) if file_path.suffix.lower() in {".yaml", ".yml"} else json.loads(file_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError, json.JSONDecodeError) as exc:
        raise ValueError(f"Could not read REA findings from {file_path}: {exc}") from exc
    if isinstance(raw, dict):
        raw = raw.get("endpoints", raw.get("findings", raw.get("routes", [])))
    if not isinstance(raw, list):
        raise ValueError("REA findings must be a list or a mapping with an endpoints list")
    hints = []
    for item in raw:
        hint = _as_hint(item)
        if hint is not None:
            hints.append(hint)
    return hints


def merge_findings(profile: Profile, hints: list[EndpointHint]) -> Profile:
    existing = {(item.method, item.path) for item in profile.endpoints}
    additions = [item for item in hints if (item.method, item.path) not in existing]
    return profile.model_copy(update={"endpoints": [*profile.endpoints, *additions]})


def _validate_cdp_endpoint(value: str) -> str:
    """Validate the loopback-only endpoint accepted by REA's browser tools."""
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "ws"} or not parsed.hostname or parsed.port is None:
        raise ValueError("REA_CDP_ENDPOINT must be an explicit-port http:// or ws:// loopback endpoint")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("REA_CDP_ENDPOINT must not contain credentials, a query, or a fragment")
    try:
        address = ipaddress.ip_address(parsed.hostname)
    except ValueError as exc:
        raise ValueError("REA_CDP_ENDPOINT must use a literal loopback IP (127.0.0.1 or ::1)") from exc
    if not address.is_loopback:
        raise ValueError("REA_CDP_ENDPOINT must be loopback-only; do not expose browser debugging remotely")
    if parsed.scheme == "http" and parsed.path not in {"", "/"}:
        raise ValueError("HTTP REA_CDP_ENDPOINT must be an origin only, e.g. http://127.0.0.1:9222")
    if parsed.scheme == "ws" and not parsed.path.startswith("/devtools/browser/"):
        raise ValueError("WebSocket REA_CDP_ENDPOINT must use the browser /devtools/browser/<id> path")
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", ""))


def _walk_dicts(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_dicts(child)


def _target_match_rank(target_url: str, observed_url: str) -> int:
    """Prefer exact page URLs; only fall back to a unique path match when query is omitted."""
    target = urlsplit(target_url)
    observed = urlsplit(observed_url)
    if (target.scheme.lower(), target.netloc.lower(), target.path or "/", target.query) == (
        observed.scheme.lower(), observed.netloc.lower(), observed.path or "/", observed.query
    ):
        return 2
    if not target.query and (target.scheme.lower(), target.netloc.lower(), target.path or "/") == (
        observed.scheme.lower(), observed.netloc.lower(), observed.path or "/"
    ):
        return 1
    return 0


def _run_cli_json(command: list[str], timeout: float) -> Any:
    completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    if completed.returncode != 0:
        detail = completed.stderr.strip()[-1000:]
        raise RuntimeError(f"REA command exited with status {completed.returncode}. {detail}")
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(f"REA command did not return JSON on stdout: {exc}") from exc


def run_rea(target_url: str, settings: Settings, on_event: Callable[[Any], None] | None = None,
            timeout: float = 60.0) -> list[EndpointHint]:
    """Use REA's documented CLI to inspect an already-open page via local Chrome CDP.

    The configured command is an installed executable prefix (normally ``rea``).
    Peke first lists browser targets, selects an exact URL match, then runs analyze-web-bundle.
    It never launches, navigates, or controls the browser.
    """
    def emit(message: str, level: str = "warn") -> None:
        if on_event:
            from datetime import datetime, timezone
            from peke.pipeline import Event
            on_event(Event(datetime.now(timezone.utc).isoformat(), "discover", level, message, "REA"))

    if not settings.rea_command:
        emit("REA CLI not configured; continuing with profile endpoint hints.")
        return []
    try:
        endpoint = _validate_cdp_endpoint(settings.rea_cdp_endpoint)
        command_prefix = shlex.split(settings.rea_command)
        if not command_prefix:
            emit("REA CLI command is empty; continuing with profile endpoint hints.")
            return []
        targets_result = _run_cli_json([*command_prefix, "list-browser-targets", endpoint, "--json"], timeout)
        ranked_targets = []
        for item in _walk_dicts(targets_result):
            target_id = item.get("target_id", item.get("targetId"))
            observed_url = item.get("url")
            target_type = item.get("type", "page")
            if isinstance(target_id, str) and isinstance(observed_url, str) and target_type == "page":
                rank = _target_match_rank(target_url, observed_url)
                if rank:
                    ranked_targets.append((rank, target_id, observed_url))
        best_rank = max((item[0] for item in ranked_targets), default=0)
        unique_targets = list(dict.fromkeys((target_id, url) for rank, target_id, url in ranked_targets if rank == best_rank))
        if not unique_targets:
            emit(f"REA found no open browser page matching {redact_url(target_url)}; open it in the configured debug browser.")
            return []
        if len(unique_targets) > 1:
            emit(f"REA found multiple browser targets matching {target_url}; refusing ambiguous selection.")
            return []
        target_id, observed_url = unique_targets[0]
        result = _run_cli_json([*command_prefix, "analyze-web-bundle", endpoint, target_id, "--json"], timeout)
        hints = parse_rea_output(json.dumps(result))
        emit(f"REA analyzed the open page and returned {len(hints)} endpoint candidate(s). Review before use.", "ok")
        return hints
    except (OSError, subprocess.TimeoutExpired, ValueError, RuntimeError) as exc:
        logger.warning("Optional REA discovery failed: %s", type(exc).__name__)
        emit(f"REA unavailable or failed ({type(exc).__name__}); continuing with profile endpoint hints.")
        return []


def run_rea_stub(*args: Any, **kwargs: Any) -> None:
    """Compatibility stub retained for callers from early Phase 1."""
    raise NotImplementedError("Use run_rea(target_url, settings, on_event) for optional discovery.")
