"""Deterministic validation with a lazy, pluggable provider fallback."""
import json
import logging
import time
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError

from peke.config import Settings
from peke.providers import Provider, ProviderError, get_provider

logger = logging.getLogger(__name__)


class ExtractionError(Exception):
    """Extraction failed after bounded validation retries."""


@dataclass
class ExtractionResult:
    model: BaseModel
    raw: str
    attempts: int
    prompt_tokens: int
    completion_tokens: int
    tokens_per_second: float
    model_name: str
    used_llm: bool = True


def validate_json(payload: Any, schema: type[BaseModel]) -> BaseModel | None:
    try:
        return schema.model_validate(payload)
    except (ValidationError, TypeError, ValueError):
        return None


class Extractor:
    def __init__(self, settings: Settings, provider: Provider | None = None) -> None:
        self.settings = settings
        self.provider = provider or get_provider(settings=settings)

    @property
    def _llm(self) -> Any:
        if hasattr(self.provider, "_get_llm"):
            return self.provider._get_llm()
        return None

    @_llm.setter
    def _llm(self, value: Any) -> None:
        if hasattr(self.provider, "_llm"):
            self.provider._llm = value

    def _model(self) -> Any:
        return self._llm

    def run(self, text: str, schema: type[BaseModel]) -> ExtractionResult:
        schema_json = schema.model_json_schema()
        chunks = [text]
        if len(text) > self.settings.max_input_chars:
            paragraphs = text.splitlines()
            chunks, current = [], ""
            limit = max(1, self.settings.max_input_chars)
            for paragraph in paragraphs:
                segments = [paragraph[index:index + limit] for index in range(0, len(paragraph), limit)] or [""]
                for segment in segments:
                    if current and len(current) + len(segment) + 1 > limit:
                        chunks.append(current)
                        current = ""
                    current = f"{current}\n{segment}" if current else segment
            if current:
                chunks.append(current)

        models: list[BaseModel] = []
        raws: list[str] = []
        attempts = prompt_tokens = completion_tokens = 0
        start = time.perf_counter()

        system_prompt = (
            "You are an extraction engine. Return only a JSON object matching the supplied schema. "
            "Use null for missing information. Never invent data."
        )

        for chunk in chunks:
            user_prompt = f"Schema:\n{json.dumps(schema_json)}\n\nExtract from this source:\n{chunk}"
            last_error = ""
            for attempt in range(1, 3):
                attempts += 1
                if last_error:
                    user_prompt_attempt = f"{user_prompt}\n\nYour previous JSON failed validation: {last_error}. Correct it; do not invent missing values."
                else:
                    user_prompt_attempt = user_prompt

                try:
                    res = self.provider.complete_json(
                        system=system_prompt,
                        user=user_prompt_attempt,
                        json_schema=schema_json,
                        temperature=self.settings.temperature,
                    )
                    prompt_tokens += res.prompt_tokens
                    completion_tokens += res.completion_tokens
                    raw = res.raw_text
                    if res.parsed is not None:
                        model = schema.model_validate(res.parsed)
                    else:
                        model = schema.model_validate_json(raw)
                    models.append(model)
                    raws.append(raw)
                    break
                except (ValidationError, json.JSONDecodeError, KeyError, TypeError, IndexError, ProviderError) as exc:
                    last_error = str(exc)
                    logger.warning("Extraction validation failed on attempt %d: %s", attempt, exc)
            else:
                raise ExtractionError(f"Could not produce schema-valid output after 2 attempts: {last_error}")

        merged = models[0].model_dump()
        for field_name, field_info in schema.model_fields.items():
            values = [item.model_dump().get(field_name) for item in models]
            if getattr(field_info.annotation, "__origin__", None) is list or any(isinstance(v, list) for v in values if v is not None):
                merged[field_name] = [entry for value in values if isinstance(value, list) for entry in value] or None
            elif merged.get(field_name) is None:
                merged[field_name] = next((value for value in values if value is not None), None)

        final_model = schema.model_validate(merged)
        elapsed = max(time.perf_counter() - start, 0.000001)
        model_name = getattr(self.provider, "model_name", str(self.settings.model_path))
        return ExtractionResult(
            final_model,
            "\n".join(raws),
            attempts,
            prompt_tokens,
            completion_tokens,
            completion_tokens / elapsed,
            model_name,
            True,
        )
