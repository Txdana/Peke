"""Sub-agent orchestrator for deep discovery reconnaissance."""
import json
import logging
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from peke.agents.auth_agent import AuthAgent
from peke.agents.bundle_agent import BundleAgent
from peke.agents.network_agent import NetworkAgent
from peke.config import Settings
from peke.fetch import fetch
from peke.pipeline import Event
from peke.profile import Profile
from peke.providers import Provider, get_provider

logger = logging.getLogger(__name__)


@dataclass
class ReconResult:
    run_id: str
    target_url: str
    ok: bool
    bundle: dict[str, Any]
    network: dict[str, Any]
    auth: dict[str, Any]
    synthesis: dict[str, Any]
    error: str | None = None
    duration_seconds: float = 0.0


class Orchestrator:
    def __init__(
        self,
        settings: Settings,
        provider: Provider | None = None,
        on_event: Callable[[Event], None] | None = None,
    ) -> None:
        self.settings = settings
        self.provider = provider or get_provider(settings=settings)
        self.on_event = on_event

    def _emit(self, stage: str, message: str, level: str = "info", tag: str | None = None) -> None:
        if self.on_event:
            event = Event(
                ts=time.strftime("%H:%M:%S"),
                stage=f"subagent:{stage}",
                level=level,
                message=message,
                tag=tag,
            )
            self.on_event(event)

    def run_reconnaissance(
        self,
        url: str,
        subagent_provider: Provider | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> ReconResult:
        run_id = uuid.uuid4().hex[:12]
        start_time = time.perf_counter()
        active_provider = subagent_provider or self.provider

        bundle_data: dict[str, Any] = {"endpoints": [], "secret_headers": [], "notes": []}
        network_data: dict[str, Any] = {"routes": [], "notes": []}
        auth_data: dict[str, Any] = {"tokens": [], "notes": []}
        synthesis_data: dict[str, Any] = {}
        error_msg: str | None = None

        page_html = ""
        page_headers: dict[str, str] = {}
        try:
            profile = Profile(name="orchestrator_baseline", url=url, fetcher="basic", method="GET")
            res = fetch(profile, self.settings)
            page_html = res.text
            page_headers = {"content-type": res.content_type}
        except Exception as exc:
            self._emit("network", f"Baseline fetch failed: {exc}", level="warn")

        if cancel_check and cancel_check():
            return ReconResult(run_id, url, False, bundle_data, network_data, auth_data, {}, "Cancelled by user")

        self._emit("bundle", "Running Bundle Agent static analysis...")
        try:
            ba = BundleAgent()
            res = ba.analyze(page_html, url, self.settings)
            bundle_data = {"endpoints": res.endpoints, "secret_headers": res.secret_headers, "notes": res.notes}
            self._emit("bundle", f"Bundle Agent completed with {len(res.endpoints)} endpoint hint(s).", level="ok")
        except Exception as exc:
            self._emit("bundle", f"Bundle Agent failed: {exc}", level="warn")

        if cancel_check and cancel_check():
            return ReconResult(run_id, url, False, bundle_data, network_data, auth_data, {}, "Cancelled by user")

        self._emit("network", "Running Network Agent probes...")
        try:
            na = NetworkAgent()
            res = na.analyze(url, bundle_data.get("endpoints", []), self.settings)
            network_data = {"routes": res.routes, "notes": res.notes}
            self._emit("network", f"Network Agent completed with {len(res.routes)} route probe(s).", level="ok")
        except Exception as exc:
            self._emit("network", f"Network Agent failed: {exc}", level="warn")

        if cancel_check and cancel_check():
            return ReconResult(run_id, url, False, bundle_data, network_data, auth_data, {}, "Cancelled by user")

        self._emit("auth", "Running Auth Analysis Agent...")
        try:
            aa = AuthAgent()
            res = aa.analyze(page_headers)
            auth_data = {"tokens": res.tokens, "notes": res.notes}
            self._emit("auth", f"Auth Agent completed with {len(res.tokens)} token(s) identified.", level="ok")
        except Exception as exc:
            self._emit("auth", f"Auth Agent failed: {exc}", level="warn")

        if cancel_check and cancel_check():
            return ReconResult(run_id, url, False, bundle_data, network_data, auth_data, {}, "Cancelled by user")

        self._emit("synthesis", "Running synthesis pass...")
        all_endpoints = bundle_data.get("endpoints", [])
        synthesis_data = {
            "summary": f"Discovered {len(all_endpoints)} endpoint hint(s) across static and network analysis.",
            "endpoints": all_endpoints,
            "tokens_found": len(auth_data.get("tokens", [])),
            "provider": active_provider.name,
        }
        self._emit("synthesis", "Reconnaissance completed.", level="ok")

        elapsed = time.perf_counter() - start_time
        result = ReconResult(
            run_id=run_id,
            target_url=url,
            ok=error_msg is None,
            bundle=bundle_data,
            network=network_data,
            auth=auth_data,
            synthesis=synthesis_data,
            error=error_msg,
            duration_seconds=elapsed,
        )

        self._save_run(result, active_provider.name)

        return result

    def _save_run(self, result: ReconResult, provider_name: str) -> None:
        try:
            runs_dir = Path.home() / ".peke" / "runs" / result.run_id
            runs_dir.mkdir(parents=True, exist_ok=True)
            run_file = runs_dir / "subagents.json"
            data = {
                "run_id": result.run_id,
                "target_url": result.target_url,
                "ok": result.ok,
                "provider": provider_name,
                "duration_seconds": result.duration_seconds,
                "timestamp": time.time(),
                "bundle": result.bundle,
                "network": result.network,
                "auth": result.auth,
                "synthesis": result.synthesis,
                "error": result.error,
            }
            run_file.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        except Exception as exc:
            logger.warning("Could not persist subagent run metadata: %s", exc)
