"""Sub-agent orchestrator for deep discovery reconnaissance."""
import json
import logging
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from peke.agents.auth_agent import AuthAgent
from peke.agents.bundle_agent import BundleAgent
from peke.agents.network_agent import NetworkAgent
from peke.agents.probe_agent import ProbeAgent
from peke.agents.schema_agent import SchemaAgent
from peke.config import Settings
from peke.fetch import fetch
from peke.pipeline import Event, Level
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
    probes: list[dict[str, Any]] = field(default_factory=list)
    schema: list[dict[str, Any]] = field(default_factory=list)


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

    def _emit(self, stage: str, message: str, level: Level = "info", tag: str | None = None) -> None:
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
            raw = getattr(res, "raw_html", None)
            page_html = raw if isinstance(raw, str) and raw else res.text  # raw keeps <script> content
            page_headers = {"content-type": res.content_type}
        except Exception as exc:
            self._emit("network", f"Baseline fetch failed: {exc}", level="warn")

        if cancel_check and cancel_check():
            return ReconResult(run_id, url, False, bundle_data, network_data, auth_data, {}, "Cancelled by user")

        self._emit("bundle", "Running Bundle Agent static analysis...")
        try:
            ba = BundleAgent()
            res = ba.analyze(page_html + "\n" + self._collect_bundles(url, page_html), url, self.settings)
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

        probe_rows: list[dict[str, Any]] = []
        schema_rows: list[dict[str, Any]] = []
        payloads: dict[str, Any] = {}
        self._emit("probe", "Running Probe Agent (GET-only, same-origin)...")
        try:
            pr = ProbeAgent().analyze(url, bundle_data.get("endpoints", []), self.settings, cancel_check)
            probe_rows, payloads = pr.probes, pr.payloads
            self._emit("probe", pr.notes[0] if pr.notes else "Probe Agent completed.", level="ok")
        except Exception as exc:
            self._emit("probe", f"Probe Agent failed: {exc}", level="warn")

        if cancel_check and cancel_check():
            return ReconResult(run_id, url, False, bundle_data, network_data, auth_data, {}, "Cancelled by user")

        self._emit("schema", "Running Schema Agent (shape inference + AI interpretation)...")
        try:
            ai = active_provider if self._provider_ready(active_provider) else None
            if ai is None:
                self._emit("schema", "No ready AI provider; using deterministic inference only.", level="warn")
            sr = SchemaAgent().analyze(payloads, ai)
            schema_rows = sr.findings
            self._emit("schema", sr.notes[0] if sr.notes else "Schema Agent completed.", level="ok")
        except Exception as exc:
            self._emit("schema", f"Schema Agent failed: {exc}", level="warn")

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
            "summary": (
                f"Discovered {len(all_endpoints)} endpoint hint(s); "
                f"{sum(1 for p in probe_rows if p.get('ok'))} responded, "
                f"{len(schema_rows)} returned inspectable JSON."
            ),
            "endpoints": all_endpoints,
            "tokens_found": len(auth_data.get("tokens", [])),
            "provider": active_provider.name,
            "recommended": self._recommend(url, probe_rows, schema_rows),
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
            probes=probe_rows,
            schema=schema_rows,
        )

        self._save_run(result, active_provider.name)

        return result

    def _collect_bundles(self, base_url: str, html: str, limit: int | None = None) -> str:
        """Fetch a few same-origin <script src> files (GET) so endpoints inside JS bundles are visible."""
        import re
        from urllib.parse import urljoin, urlsplit

        limit = limit if limit is not None else int(getattr(self.settings, "subagents_max_scripts", 0))
        origin = urlsplit(base_url)
        chunks: list[str] = []
        for src in dict.fromkeys(re.findall(r"""<script[^>]+src=["']([^"']+)["']""", html, flags=re.I)):
            if limit and len(chunks) >= limit:
                break
            target = urljoin(base_url, src)
            parts = urlsplit(target)
            if (parts.scheme, parts.netloc) != (origin.scheme, origin.netloc) or not parts.path.endswith(".js"):
                continue
            try:
                res = fetch(Profile(name="bundle_fetch", url=target, fetcher="basic", method="GET"), self.settings)
                raw = getattr(res, "raw_html", None)
                if isinstance(raw, str):
                    chunks.append(raw[:2_000_000])
            except Exception as exc:
                self._emit("bundle", f"Skipped script bundle: {type(exc).__name__}", level="warn")
        return "\n".join(chunks)

    @staticmethod
    def _provider_ready(provider: Provider) -> bool:
        try:
            return bool(provider.health_check().ok)
        except Exception:
            return False

    @staticmethod
    def _recommend(base_url: str, probes: list[dict[str, Any]], schema: list[dict[str, Any]]) -> dict[str, Any] | None:
        """Pick the richest JSON endpoint as a *draft* profile suggestion (still needs human review)."""
        from urllib.parse import urljoin

        by_url = {p.get("url"): p for p in probes if p.get("ok")}
        best = max((f for f in schema if f.get("item_count")), key=lambda f: f["item_count"], default=None)
        probe = by_url.get(best["url"]) if best else None
        if not best or not probe:
            return None
        return {
            "url": urljoin(base_url, probe["path"]),
            "params": probe.get("params", {}),
            "item_path": best.get("item_path"),
            "schema_name": best.get("schema_name", "Listing"),
            "fields": best.get("fields", {}),
            "pagination": best.get("pagination", []),
            "mode": "api",
        }

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
                "probes": result.probes,
                "schema": result.schema,
                "error": result.error,
            }
            run_file.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        except Exception as exc:
            logger.warning("Could not persist subagent run metadata: %s", exc)
