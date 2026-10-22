"""Pipeline orchestration module for Peke.

Orchestrates REA discovery, Scrapling fetching, LLM extraction/validation,
and emits structured log events during execution.
"""

from collections.abc import Callable
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from peke.config import get_settings
from peke.discover import discover_target_profile
from peke.extract import ExtractionResult, extract_data
from peke.fetch import FetchResult, fetch_target
from peke.profile import TargetProfile, load_profile


class PipelineEvent(BaseModel):
    """Structured log event emitted during pipeline execution."""

    timestamp: str
    stage: str
    level: str  # "INFO", "WARNING", "ERROR", "SUCCESS"
    message: str
    details: dict[str, Any] | None = None


class PipelineResult(BaseModel):
    """Data object containing the final output of a pipeline run."""

    profile: TargetProfile
    fetch_result: FetchResult | None = None
    extraction_result: ExtractionResult | None = None
    events: list[PipelineEvent] = []


class Pipeline:
    """Orchestrates the data extraction pipeline: discover -> fetch -> extract -> validate."""

    def __init__(
        self,
        event_callback: Callable[[PipelineEvent], None] | None = None,
        extractor_override: Any | None = None,
    ) -> None:
        """Initialize Pipeline.

        :param event_callback: Optional callback function invoked for each emitted PipelineEvent.
        :param extractor_override: Optional custom extractor instance (used in testing).
        """
        self.event_callback = event_callback
        self.extractor_override = extractor_override
        self.events: list[PipelineEvent] = []

    def _emit(
        self,
        stage: str,
        level: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> PipelineEvent:
        """Emit a structured PipelineEvent."""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        event = PipelineEvent(
            timestamp=now_str,
            stage=stage,
            level=level,
            message=message,
            details=details,
        )
        self.events.append(event)
        if self.event_callback:
            try:
                self.event_callback(event)
            except Exception:
                pass
        return event

    def run(self, profile_input: Any) -> PipelineResult:
        """Run the full extraction pipeline for a given profile or URL.

        :param profile_input: TargetProfile, path to YAML file, or dictionary.
        :return: PipelineResult containing profile, fetch results, extracted data, and events.
        """
        self.events.clear()
        settings = get_settings()

        # 1. DISCOVERY STAGE
        self._emit("DISCOVER", "INFO", "Initializing profile and discovery stage...")
        if isinstance(profile_input, TargetProfile):
            profile = profile_input
        elif isinstance(profile_input, str) and profile_input.startswith(("http://", "https://")):
            self._emit("DISCOVER", "INFO", f"Discovering target profile for URL: {profile_input}")
            profile = discover_target_profile(profile_input, rea_url=settings.rea_server_url)
        else:
            self._emit("DISCOVER", "INFO", "Loading target profile from file/dict...")
            profile = load_profile(profile_input)

        if profile.endpoint_hints:
            self._emit(
                "DISCOVER",
                "SUCCESS",
                f"Loaded profile '{profile.name}' with {len(profile.endpoint_hints)} endpoint hints.",
                details={"endpoints": profile.endpoint_hints},
            )
        else:
            self._emit("DISCOVER", "INFO", f"Loaded target profile '{profile.name}'.")

        # 2. FETCH STAGE
        self._emit(
            "FETCH",
            "INFO",
            f"Fetching URL '{profile.url}' using {profile.fetcher}...",
        )
        fetch_res: FetchResult | None = None
        try:
            fetch_res = fetch_target(
                url=profile.url,
                fetcher_type=profile.fetcher,
                headers=profile.headers,
                params=profile.params,
                timeout=settings.fetch_timeout,
            )

            if fetch_res.cloudflare_bypassed:
                self._emit("FETCH", "SUCCESS", "[CLOUDFLARE BYPASSED] Stealth fetch complete.")

            self._emit(
                "FETCH",
                "SUCCESS",
                f"[{fetch_res.status_code} OK] Fetched {len(fetch_res.text)} characters. JSON payload: {fetch_res.is_json}",
                details={"status_code": fetch_res.status_code, "is_json": fetch_res.is_json},
            )
        except Exception as e:
            self._emit("FETCH", "ERROR", f"Fetch failed: {e}")
            return PipelineResult(profile=profile, fetch_result=None, extraction_result=None, events=self.events)

        # 3. EXTRACTION & VALIDATION STAGE
        self._emit("EXTRACT", "INFO", f"Processing payload with schema '{profile.schema_name}'...")
        payload_to_extract = fetch_res.json_data if fetch_res.is_json else fetch_res.text

        try:
            extraction_res = extract_data(
                raw_content=payload_to_extract,
                schema_name=profile.schema_name,
                is_json_payload=fetch_res.is_json,
                extractor_override=self.extractor_override,
            )

            if extraction_res.used_llm:
                self._emit(
                    "EXTRACT",
                    "SUCCESS",
                    f"[VALID] LLM extraction successful using {extraction_res.model_name} "
                    f"({extraction_res.tokens_per_second} tok/s, retries: {extraction_res.retries}).",
                )
            else:
                self._emit(
                    "EXTRACT",
                    "SUCCESS",
                    "[VALID] Direct JSON endpoint validated with Pydantic (LLM skipped).",
                )

            return PipelineResult(
                profile=profile,
                fetch_result=fetch_res,
                extraction_result=extraction_res,
                events=self.events,
            )

        except Exception as e:
            self._emit("EXTRACT", "ERROR", f"Extraction / Validation failed: {e}")
            return PipelineResult(
                profile=profile,
                fetch_result=fetch_res,
                extraction_result=None,
                events=self.events,
            )
