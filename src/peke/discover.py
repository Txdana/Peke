"""REA discovery integration module for Peke.

Discovers endpoints, headers, and parameters from REA analysis findings
or falls back gracefully to standard profiles when REA is not active or available.
"""

import json
import logging
import shlex
import subprocess
from collections.abc import Callable
from typing import Any

import httpx
from pydantic import BaseModel, Field

from peke.config import Settings, get_settings
from peke.profile import TargetProfile

logger = logging.getLogger(__name__)


class EndpointHint(BaseModel):
    """Discovered endpoint hint structure."""

    method: str = Field(default="GET", description="HTTP method (e.g. GET, POST)")
    path: str = Field(..., description="Endpoint path or URL")
    size: str | None = Field(default=None, description="Response size string if known")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Query or payload parameters")
    headers: dict[str, str] = Field(default_factory=dict, description="HTTP headers for this endpoint")
    note: str | None = Field(default=None, description="Discovered details or note")
    discovered_by: str = Field(default="rea", description="Discovery source identifier")
    hidden: bool = Field(default=False, description="True if endpoint was not referenced in HTML")


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


def parse_rea_json_output(raw_output: str) -> list[EndpointHint]:
    """Parse JSON output string from REA CLI/MCP into EndpointHint list.

    :param raw_output: Raw JSON output string.
    :return: List of validated EndpointHint models.
    """
    hints: list[EndpointHint] = []
    try:
        data = json.loads(raw_output)
    except Exception as e:
        logger.warning(f"Failed to parse REA JSON output: {e}")
        return hints

    endpoints = []
    if isinstance(data, dict):
        endpoints = data.get("endpoints") or data.get("endpoint_hints") or []
    elif isinstance(data, list):
        endpoints = data

    for ep in endpoints:
        if isinstance(ep, str):
            hints.append(
                EndpointHint(
                    method="GET",
                    path=ep,
                    discovered_by="rea",
                )
            )
        elif isinstance(ep, dict):
            method = ep.get("method", "GET")
            path = ep.get("path") or ep.get("url") or ""
            size = ep.get("size")
            params = ep.get("parameters") or ep.get("params") or {}
            headers = ep.get("headers") or {}
            note = ep.get("note") or ep.get("description")
            disc_by = ep.get("discovered_by") or ep.get("source") or "rea"
            hidden = bool(ep.get("hidden", False))

            if path:
                hints.append(
                    EndpointHint(
                        method=method,
                        path=path,
                        size=size,
                        parameters=params if isinstance(params, dict) else {},
                        headers=headers if isinstance(headers, dict) else {},
                        note=note,
                        discovered_by=disc_by,
                        hidden=hidden,
                    )
                )
    return hints


def run_rea(
    target_url: str,
    settings: Settings | None = None,
    on_event: Callable[[str, str], None] | None = None,
    timeout: float = 30.0,
) -> list[EndpointHint]:
    """Execute REA CLI tool via subprocess (without shell=True) to discover hidden endpoints.

    If REA is missing or fails, emits a warning event and returns an empty list,
    ensuring the pipeline never fails due to REA.

    :param target_url: Target web app URL.
    :param settings: Optional Settings object.
    :param on_event: Callback for emitting pipeline warning/info events (level, message).
    :param timeout: Command execution timeout in seconds.
    :return: List of discovered EndpointHint objects.
    """
    if settings is None:
        settings = get_settings()

    cmd_str = settings.rea_command
    cmd_args = shlex.split(cmd_str)
    if not cmd_args:
        cmd_args = ["rea"]

    cmd_args.append(target_url)

    def emit_warn(msg: str) -> None:
        logger.warning(msg)
        if on_event:
            try:
                on_event("WARNING", msg)
            except Exception:
                pass

    try:
        proc = subprocess.run(
            cmd_args,
            shell=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if proc.returncode != 0:
            stderr_msg = proc.stderr.strip() or f"Process exited with code {proc.returncode}"
            emit_warn(f"REA execution failed or warned: {stderr_msg}. Continuing without REA hints.")
            return []

        hints = parse_rea_json_output(proc.stdout)
        if not hints:
            emit_warn("REA executed successfully but returned no endpoints. Continuing with profile defaults.")
        return hints

    except FileNotFoundError:
        emit_warn(f"REA command executable '{cmd_args[0]}' was not found in PATH. Continuing without REA hints.")
        return []
    except subprocess.TimeoutExpired:
        emit_warn(f"REA execution timed out after {timeout} seconds. Continuing without REA hints.")
        return []
    except Exception as e:
        emit_warn(f"Unexpected error while running REA: {e}. Continuing without REA hints.")
        return []


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
    on_event: Callable[[str, str], None] | None = None,
) -> TargetProfile:
    """Attempt endpoint discovery via REA subprocess or server, falling back to basic profile.

    :param url: Target URL.
    :param rea_url: Optional REA server URL.
    :param schema_name: Name of target Pydantic schema.
    :param on_event: Callback for emitting log events.
    :return: TargetProfile object.
    """
    settings = get_settings()

    # First try subprocess REA
    hints = run_rea(url, settings=settings, on_event=on_event)
    hints_dict = [h.model_dump() for h in hints]

    if rea_url and is_rea_available(rea_url):
        try:
            client = httpx.Client(timeout=5.0)
            res = client.post(
                f"{rea_url.rstrip('/')}/discover",
                json={"url": url},
            )
            if res.status_code == 200 and isinstance(res.json(), dict):
                prof = read_rea_findings(res.json(), fallback_url=url, schema_name=schema_name)
                if hints_dict:
                    prof.endpoint_hints.extend(hints_dict)
                return prof
        except Exception as e:
            logger.warning(f"REA HTTP discovery failed: {e}")

    return TargetProfile(
        name="Hand-written Target Profile" if not hints else "REA Discovered Profile",
        url=url,
        fetcher="Fetcher",
        headers={},
        params={},
        endpoint_hints=hints_dict,
        schema_name=schema_name,
    )
