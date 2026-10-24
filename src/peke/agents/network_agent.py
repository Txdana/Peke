"""Network agent using Scrapling GET/HEAD fetchers with strict SSRF validation."""
from dataclasses import dataclass
from typing import Any

from peke.fetch import FetchError, fetch
from peke.profile import Profile


@dataclass
class NetworkAgentResult:
    routes: list[dict[str, Any]]
    notes: list[str]


class NetworkAgent:
    def analyze(self, url: str, endpoints: list[dict[str, Any]], settings: Any) -> NetworkAgentResult:
        routes: list[dict[str, Any]] = []
        notes: list[str] = []

        try:
            profile = Profile(name="network_agent_probe", url=url, fetcher="basic", method="GET")
            res = fetch(profile, settings)
            routes.append({
                "url": url,
                "status_code": res.status,
                "content_type": res.content_type,
                "sample": res.text[:200] if res.text else "",
            })
            notes.append(f"Primary URL probed: HTTP {res.status}")
        except FetchError as exc:
            notes.append(f"Primary URL probe failed: {exc}")

        return NetworkAgentResult(routes=routes, notes=notes)
