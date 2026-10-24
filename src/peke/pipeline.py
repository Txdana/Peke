"""Headless extraction pipeline."""
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal
from urllib.parse import urljoin, urlsplit

from pydantic import BaseModel

from peke.config import ConfigError, Settings, load_settings
from peke.discover import merge_findings, run_rea
from peke.extract import ExtractionError, ExtractionResult, Extractor, validate_json
from peke.fetch import FetchError, FetchResult, fetch
from peke.profile import Profile, redact_url
from peke.schemas import get_schema

logger = logging.getLogger(__name__)
Stage = str  # research and subagent events also use this event channel
Level = Literal["info", "ok", "warn", "error"]


@dataclass
class Event:
    ts: str
    stage: Stage
    level: Level
    message: str
    tag: str | None = None
    data: dict[str, Any] | None = None


@dataclass
class PipelineResult:
    records: list[BaseModel] = field(default_factory=list)
    markdown_summary: str = ""
    metrics: dict[str, Any] = field(default_factory=dict)
    events: list[Event] = field(default_factory=list)
    fetch_result: FetchResult | None = None
    extraction_result: ExtractionResult | None = None
    endpoints: list[Any] = field(default_factory=list)


def to_markdown(records: list[BaseModel], schema: type[BaseModel]) -> str:
    if not records:
        return f"# {schema.__name__}\n\nNo records extracted."
    dumped = [record.model_dump() for record in records]  # once per record, not once per cell
    fields = list(dumped[0].keys())
    lines = [f"# {schema.__name__} extraction", "", "| " + " | ".join(fields) + " |",
             "| " + " | ".join(["---"] * len(fields)) + " |"]
    for row in dumped:
        cells = ("" if row.get(f) is None else str(row[f]) for f in fields)
        lines.append("| " + " | ".join(c.replace("|", "\\|").replace("\n", " ") for c in cells) + " |")
    return "\n".join(lines)


def select_path(payload: Any, path: str | None) -> Any:
    """Follow a dotted item_path through dicts and list indexes; None when it does not resolve."""
    if not path:
        return payload
    for part in path.split("."):
        if isinstance(payload, dict):
            payload = payload.get(part)
        elif isinstance(payload, list) and part.isdigit() and int(part) < len(payload):
            payload = payload[int(part)]
        else:
            return None
    return payload


def validate_all(payload: Any, schema: type[BaseModel]) -> list[BaseModel]:
    """Validate one object or every object in a list (lists used to yield no records)."""
    if isinstance(payload, list):
        return [m for m in (validate_json(item, schema) for item in payload) if m is not None]
    model = validate_json(payload, schema) if payload is not None else None
    return [model] if model is not None else []


def next_profile(profile: Profile, raw: Any, seen: set[str]) -> Profile | None:
    """Work out the next page request from the response (next link, page number or offset)."""
    if isinstance(raw, dict):
        for key in ("next", "next_page", "nextPage", "next_url"):
            link = raw.get(key)
            if isinstance(link, str) and link.strip():
                target = urljoin(profile.url, link.strip())
                same = urlsplit(target)[:2] == urlsplit(profile.url)[:2]
                if same and target not in seen:
                    return profile.model_copy(update={"url": target, "params": {}})
                return None
    params = dict(profile.params)
    try:
        if "page" in params:
            params["page"] = int(params["page"]) + 1
        elif "offset" in params and "limit" in params:
            params["offset"] = int(params["offset"]) + int(params["limit"])
        else:
            return None
    except (TypeError, ValueError):
        return None
    return profile.model_copy(update={"params": params})


class Pipeline:
    def __init__(self, settings: Settings | None = None, on_event: Callable[[Event], None] | None = None,
                 extractor: Extractor | None = None, cancel_check: Callable[[], bool] | None = None, **legacy: Any) -> None:
        self.settings = settings or load_settings()
        self.on_event = on_event or legacy.get("event_callback")
        self.extractor = extractor or legacy.get("extractor_override") or Extractor(self.settings)
        self.events: list[Event] = []
        self.cancel_check = cancel_check or (lambda: False)

    def _emit(self, stage: Stage, level: Level, message: str, tag: str | None = None,
              data: dict[str, Any] | None = None) -> None:
        event = Event(datetime.now(timezone.utc).isoformat(), stage, level, message, tag, data)
        self.events.append(event)
        if self.on_event:
            try:
                self.on_event(event)
            except Exception:
                logger.exception("Pipeline event callback failed")

    def _accept_event(self, event: Event) -> None:
        self.events.append(event)
        if self.on_event:
            try:
                self.on_event(event)
            except Exception:
                logger.exception("Pipeline event callback failed")

    def _collect_json(self, profile: Profile, first: FetchResult, schema: type[BaseModel]) -> tuple[list[BaseModel], int]:
        """Validate JSON directly and follow pagination up to ``profile.max_pages`` (JSON responses only)."""
        records: list[BaseModel] = []
        seen = {profile.url}
        current, fr, pages = profile, first, 0
        while True:
            pages += 1
            batch = validate_all(select_path(fr.json, current.item_path), schema) if fr.json is not None else []
            records.extend(batch)
            if not batch or pages >= profile.max_pages or self.cancel_check():
                break
            nxt = next_profile(current, fr.json, seen)
            if nxt is None:
                break
            seen.add(nxt.url)
            self._emit("fetch", "info", f"Fetching page {pages + 1} of up to {profile.max_pages}")
            try:
                fr = fetch(nxt, self.settings)
            except FetchError as exc:
                self._emit("fetch", "warn", f"Pagination stopped: {exc}")
                break
            current = nxt
        return records, pages

    def run(self, profile: Profile) -> PipelineResult:
        self.events = []
        result = PipelineResult()
        started = time.perf_counter()
        self._emit("discover", "info", f"Using profile: {profile.name}")
        try:
            hints = run_rea(profile.url, self.settings, self._accept_event)
            profile = merge_findings(profile, hints)
            result.endpoints = list(profile.endpoints)
            if self.cancel_check():
                raise ExtractionError("Pipeline cancelled after discovery.")
            self._emit("discover", "ok" if hints else "info",
                       f"Endpoint hints available: {len(profile.endpoints)}",
                       data={"endpoints": [hint.model_dump(mode="json") for hint in profile.endpoints]})
            self._emit("fetch", "info", f"Fetching {redact_url(profile.url)}")
            result.fetch_result = fetch(profile, self.settings)
            fr = result.fetch_result
            if self.cancel_check():
                raise ExtractionError("Pipeline cancelled after fetch.")
            self._emit("fetch", "ok", f"Fetched HTTP {fr.status}; {len(fr.text)} characters", f"{fr.status} OK")
            schema = get_schema(profile.schema_name)
            records, pages = self._collect_json(profile, fr, schema)
            if records:
                result.records = records
                self._emit("validate", "ok", f"JSON validated directly ({pages} page(s)); LLM skipped", "VALID")
            elif profile.mode == "api":
                raise ExtractionError("API mode requires a JSON response that validates against the selected schema")
            else:
                if self.cancel_check():
                    raise ExtractionError("Pipeline cancelled before extraction.")
                self._emit("extract", "info", "Deterministic parsing did not match; using local LLM")
                extracted = self.extractor.run(fr.text, schema)
                result.extraction_result = extracted
                result.records = [extracted.model]
                self._emit("validate", "ok", "LLM output validated", "VALID")
            result.markdown_summary = to_markdown(result.records, schema) + f"\n\n## Run summary\n\n- Valid records: {len(result.records)}\n- Fetch time: {fr.elapsed_ms} ms\n"
            if result.extraction_result is not None:
                er = result.extraction_result
                result.metrics.update({"model_name": er.model_name, "temperature": self.settings.temperature,
                                       "prompt_tokens": er.prompt_tokens,
                                       "completion_tokens": er.completion_tokens,
                                       "tokens_per_second": er.tokens_per_second,
                                       "retries": max(0, er.attempts - 1)})
            else:
                result.metrics.update({"model_name": "no model (direct validation)",
                                       "temperature": self.settings.temperature, "prompt_tokens": 0,
                                       "completion_tokens": 0, "tokens_per_second": 0, "retries": 0})
            result.metrics.update({"fetch_ms": result.fetch_result.elapsed_ms if result.fetch_result else 0,
                                   "records_valid": len(result.records), "records_invalid": 0,
                                   "n_ctx": self.settings.n_ctx, "n_gpu_layers": self.settings.n_gpu_layers,
                                   "model_size_bytes": self.settings.model_path.stat().st_size if self.settings.model_path and self.settings.model_path.is_file() else 0})
        except (ConfigError, FetchError, ExtractionError, ValueError) as exc:
            logger.warning("Pipeline ended with partial result: %s", exc)
            self._emit("fetch" if isinstance(exc, FetchError) else "extract", "error", str(exc))
        finally:
            result.events = list(self.events)
            result.metrics.update({"elapsed_ms": round((time.perf_counter() - started) * 1000, 2), "records": len(result.records)})
            self._emit("done", "ok" if result.records else "warn", "Pipeline finished" if result.records else "Pipeline finished with no records")
            result.events = list(self.events)
        return result
