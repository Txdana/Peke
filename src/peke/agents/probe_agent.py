"""Probe agent: safely GET REA/bundle endpoint hints with Scrapling and capture response shapes.

Only same-origin, read-only (GET) probes are made. Every URL passes the SSRF policy
check, probes are rate limited by ``REQUEST_DELAY_SECONDS``, and raw bodies are never
persisted; only status, content type and structural shape are kept.
"""
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin, urlsplit

from peke.agents.schema_agent import infer_shape
from peke.fetch import FetchError, fetch
from peke.mcp.security import SecurityError, validate_url_security
from peke.profile import Profile, redact_url

_TEMPLATED = re.compile(r"[{}<>$\[\]*]|/:[A-Za-z_]")


@dataclass
class ProbeAgentResult:
    probes: list[dict[str, Any]] = field(default_factory=list)
    payloads: dict[str, Any] = field(default_factory=dict)  # in-memory only, never persisted
    notes: list[str] = field(default_factory=list)


class ProbeAgent:
    def analyze(
        self,
        base_url: str,
        endpoints: list[dict[str, Any]],
        settings: Any,
        cancel_check: Callable[[], bool] | None = None,
        max_probes: int | None = None,
    ) -> ProbeAgentResult:
        result = ProbeAgentResult()
        limit = max_probes if max_probes is not None else int(getattr(settings, "subagents_max_probes", 0))
        origin = urlsplit(base_url)
        seen: set[str] = set()
        skipped = 0

        for hint in endpoints:
            if (limit and len(result.probes) >= limit) or (cancel_check and cancel_check()):
                break
            path = str(hint.get("path", ""))
            if str(hint.get("method", "GET")).upper() != "GET":
                skipped += 1  # never auto-send mutating requests
                continue
            if not path or _TEMPLATED.search(path):
                skipped += 1
                continue
            target = urljoin(base_url, path)
            parts = urlsplit(target)
            if (parts.scheme, parts.netloc) != (origin.scheme, origin.netloc):
                skipped += 1  # same-origin only
                continue
            params = hint.get("params") if isinstance(hint.get("params"), dict) else {}
            key = f"{parts.path}?{sorted(params.items())}"
            if key in seen:
                continue
            seen.add(key)
            try:
                validate_url_security(target, settings)
            except SecurityError as exc:
                result.probes.append({"url": redact_url(target), "ok": False, "error": f"blocked: {exc}"})
                continue
            if result.probes:
                time.sleep(max(0.0, float(getattr(settings, "request_delay_seconds", 0.0))))
            try:
                res = fetch(Profile(name="probe_agent", url=target, fetcher="basic", method="GET", params=params), settings)
            except (FetchError, ValueError) as exc:
                result.probes.append({"url": redact_url(target), "ok": False, "error": str(exc)[:200]})
                continue
            row: dict[str, Any] = {
                "url": redact_url(target),
                "path": parts.path,
                "params": params,
                "ok": True,
                "status": res.status,
                "content_type": res.content_type,
                "is_json": res.json is not None,
            }
            if res.json is not None:
                row["shape"] = infer_shape(res.json)
                result.payloads[row["url"]] = res.json
            else:
                row["sample"] = (res.text or "")[:120]
            result.probes.append(row)

        ok = sum(1 for p in result.probes if p.get("ok"))
        result.notes.append(f"Probed {len(result.probes)} endpoint(s) with GET only ({ok} OK, {skipped} skipped).")
        return result
