"""Bundle agent for static JS/HTML analysis and REA findings integration."""
import re
from dataclasses import dataclass
from typing import Any

from peke.discover import run_rea


@dataclass
class BundleAgentResult:
    endpoints: list[dict[str, Any]]
    secret_headers: list[str]
    notes: list[str]


class BundleAgent:
    def analyze(self, html_content: str, url: str, settings: Any) -> BundleAgentResult:
        notes: list[str] = []
        endpoints: list[dict[str, Any]] = []
        secret_headers: list[str] = []

        rea_hints = run_rea(url, settings)
        for hint in rea_hints:
            endpoints.append(hint.model_dump(mode="json"))
        if rea_hints:
            notes.append(f"REA static analysis discovered {len(rea_hints)} endpoint hint(s).")

        api_pattern = re.compile(r'/(?:api|v[0-9]+)/[A-Za-z0-9_\-/]+')
        matches = set(api_pattern.findall(html_content))
        for m in matches:
            if not any(e.get("path") == m for e in endpoints):
                endpoints.append({
                    "method": "GET",
                    "path": m,
                    "discovered_by": "bundle_regex",
                    "confidence": "low",
                    "hidden": False,
                })
        if matches:
            notes.append(f"Regex pattern match found {len(matches)} potential API path(s).")

        call_pattern = re.compile(
            r"""(?:fetch|axios(?:\.\w+)?|\.(?:get|post)|url\s*:)\s*\(?\s*[`"'](/[A-Za-z0-9_\-./]{2,120})(?:[?`"'])""")
        for m in set(call_pattern.findall(html_content)):
            if not any(e.get("path") == m for e in endpoints):
                endpoints.append({"method": "GET", "path": m, "discovered_by": "bundle_call_literal",
                                  "confidence": "low", "hidden": False})
        header_patterns = ["authorization", "x-api-key", "x-auth-token", "bearer"]
        for hp in header_patterns:
            if hp in html_content.lower():
                secret_headers.append(hp)
        if secret_headers:
            notes.append(f"Found static references to header(s): {', '.join(secret_headers)}")

        return BundleAgentResult(endpoints=endpoints, secret_headers=secret_headers, notes=notes)
