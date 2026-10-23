"""Deterministic validation with a lazy, in-process llama.cpp fallback."""
import json
import logging
import time
from dataclasses import dataclass
from typing import Any
from pydantic import BaseModel, ValidationError
from peke.config import ConfigError, Settings

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
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._llm: Any | None = None

    def _model(self) -> Any:
        if self._llm is None:
            path = self.settings.require_model()
            try:
                from llama_cpp import Llama
            except ImportError as exc:
                raise ExtractionError("llama-cpp-python is not installed; install Peke dependencies.") from exc
            self._llm = Llama(model_path=str(path), n_ctx=self.settings.n_ctx,
                             n_gpu_layers=self.settings.n_gpu_layers,
                             n_threads=self.settings.n_threads or None, verbose=False)
        return self._llm

    def run(self, text: str, schema: type[BaseModel]) -> ExtractionResult:
        llm = self._model()
        schema_json = schema.model_json_schema()
        # Keep whole paragraphs together when chunking long sources. Merge list fields and
        # retain the first non-null scalar value, avoiding invented cross-chunk synthesis.
        chunks = [text]
        if len(text) > self.settings.max_input_chars:
            paragraphs = text.splitlines()
            chunks, current = [], ""
            limit = max(1, self.settings.max_input_chars)
            for paragraph in paragraphs:
                # Split unusually long individual paragraphs as well as paragraph groups.
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
        for chunk in chunks:
            messages = [
                {"role": "system", "content": "You are an extraction engine. Return only a JSON object matching the supplied schema. Use null for missing information. Never invent data."},
                {"role": "user", "content": f"Schema:\n{json.dumps(schema_json)}\n\nExtract from this source:\n{chunk}"},
            ]
            last_error = ""
            for attempt in range(1, 3):
                attempts += 1
                if last_error:
                    messages.append({"role": "user", "content": f"Your previous JSON failed validation: {last_error}. Correct it; do not invent missing values."})
                try:
                    response = llm.create_chat_completion(messages=messages, temperature=self.settings.temperature,
                        response_format={"type": "json_object", "schema": schema_json})
                    raw = response["choices"][0]["message"]["content"]
                    usage = response.get("usage", {})
                    prompt_tokens += int(usage.get("prompt_tokens", 0))
                    completion_tokens += int(usage.get("completion_tokens", 0))
                    model = schema.model_validate_json(raw)
                    models.append(model)
                    raws.append(raw)
                    break
                except (ValidationError, json.JSONDecodeError, KeyError, TypeError, IndexError) as exc:
                    last_error = str(exc)
                    logger.warning("LLM output validation failed on attempt %d: %s", attempt, exc)
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
        return ExtractionResult(final_model, "\n".join(raws), attempts, prompt_tokens, completion_tokens,
            completion_tokens / elapsed, str(getattr(llm, "model_path", self.settings.model_path)), True)
