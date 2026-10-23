"""REA discovery integration module for Peke.

Discovers endpoints, headers, and parameters from REA analysis findings
or falls back gracefully to standard profiles when REA is not active or available.
"""

from typing import Any

import httpx

from peke.profile import TargetProfile


def is_rea_available(rea_url: str | None = None) -> bool:
    """Check if REA server or MCP server is reachable.

    :param rea_url: Base URL of REA server (e.g. http://localhost:8000).
    :return: True if REA responds, False otherwise.
    """
    if not rea_url:
        return False
    try:
        response = httpx.get(f"{rea_url.rstrip('/')}/health", timeout=2.0)
        return response.status_code == 200
    except Exception:
        return False


def read_rea_findings(
    findings_data: dict[str, Any],
    fallback_url: str = "",
    schema_name: str = "Article",
) -> TargetProfile:
    """Read REA findings payload into a TargetProfile.

    :param findings_data: Dictionary containing discovered endpoints, headers, params, etc.
    :param fallback_url: URL to use if findings do not specify a target URL.
    :param schema_name: Target Pydantic schema name.
    :return: Configured TargetProfile instance.
    """
    target_url = findings_data.get("url") or findings_data.get("target_url") or fallback_url
    discovered_endpoints = findings_data.get("endpoints") or findings_data.get("endpoint_hints") or []

    headers = findings_data.get("headers", {})
    params = findings_data.get("params", {})
    fetcher = findings_data.get("fetcher", "Fetcher")

    # Format endpoint hints list into unified structure
    hints: list[dict[str, Any]] = []
    if isinstance(discovered_endpoints, list):
        for ep in discovered_endpoints:
            if isinstance(ep, str):
                hints.append({"method": "GET", "path": ep, "source": "REA Discovered"})
            elif isinstance(ep, dict):
                hints.append(ep)

    return TargetProfile(
        name=findings_data.get("name", "REA Discovered Profile"),
        url=target_url,
        fetcher=fetcher,
        headers=headers,
        params=params,
        endpoint_hints=hints,
        schema_name=findings_data.get("schema_name", schema_name),
    )


def discover_target_profile(
    url: str,
    rea_url: str | None = None,
    schema_name: str = "Article",
) -> TargetProfile:
    """Attempt endpoint discovery via REA server if available, falling back to basic profile.

    :param url: Target URL.
    :param rea_url: Optional REA server URL.
    :param schema_name: Name of target Pydantic schema.
    :return: TargetProfile object.
    """
    if rea_url and is_rea_available(rea_url):
        try:
            client = httpx.Client(timeout=5.0)
            res = client.post(
                f"{rea_url.rstrip('/')}/discover",
                json={"url": url},
            )
            if res.status_code == 200 and isinstance(res.json(), dict):
                return read_rea_findings(res.json(), fallback_url=url, schema_name=schema_name)
        except Exception:
            pass

    # Fallback when REA is not available or reachable
    return TargetProfile(
        name="Hand-written Target Profile",
        url=url,
        fetcher="Fetcher",
        headers={},
        params={},
        endpoint_hints=[],
        schema_name=schema_name,
    )
