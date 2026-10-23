"""Headless extraction pipeline."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
import time
from typing import Any, Callable, Literal
from pydantic import BaseModel
from peke.config import ConfigError, Settings, load_settings
from peke.extract import ExtractionError, ExtractionResult, Extractor, validate_json
from peke.fetch import FetchError, FetchResult, fetch
from peke.discover import run_rea, merge_findings
from peke.profile import Profile, redact_url
from peke.schemas import get_schema

logger = logging.getLogger(__name__)
Stage = Literal["discover", "fetch", "extract", "validate", "done"]
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
    fields = list(records[0].model_dump().keys())
    lines = [f"# {schema.__name__} extraction", "", "| " + " | ".join(fields) + " |",
             "| " + " | ".join(["---"] * len(fields)) + " |"]
    for record in records:
        values = [str(record.model_dump().get(field) if record.model_dump().get(field) is not None else "").replace("|", "\\|").replace("\n", " ") for field in fields]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


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
            payload = fr.json
            if profile.item_path and payload is not None:
                for part in profile.item_path.split("."):
                    payload = payload.get(part) if isinstance(payload, dict) else None
            model = validate_json(payload, schema) if payload is not None else None
            if model is not None:
                result.records = [model]
                self._emit("validate", "ok", "JSON validated directly; LLM skipped", "VALID")
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
