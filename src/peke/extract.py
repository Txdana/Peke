"""Local LLM extraction and Pydantic validation module for Peke."""

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from peke.config import ConfigError, get_settings
from peke.schemas import get_schema


class ExtractionError(Exception):
    """Raised when extraction or validation fails after retries."""



@dataclass
class ExtractionResult:
    """Dataclass holding extracted data, metrics, and output formats."""

    data: BaseModel
    json_output: dict[str, Any]
    markdown_output: str
    used_llm: bool
    tokens_per_second: float = 0.0
    model_name: str = "N/A (Direct Parsing)"
    temperature: float = 0.1
    retries: int = 0


def model_to_markdown(model_instance: BaseModel) -> str:
    """Convert a Pydantic model instance into a clean Markdown string.

    :param model_instance: Validated Pydantic model instance.
    :return: Markdown formatted representation.
    """
    lines = [f"# {model_instance.__class__.__name__}\n"]
    data = model_instance.model_dump()
    for key, val in data.items():
        title = key.replace("_", " ").title()
        if isinstance(val, list):
            lines.append(f"### {title}")
            for item in val:
                if isinstance(item, dict):
                    item_str = ", ".join(f"{k}: {v}" for k, v in item.items())
                    lines.append(f"- {item_str}")
                else:
                    lines.append(f"- {item}")
            lines.append("")
        elif isinstance(val, dict):
            lines.append(f"### {title}")
            for k, v in val.items():
                lines.append(f"- **{k}**: {v}")
            lines.append("")
        elif val is not None:
            lines.append(f"**{title}**: {val}\n")
    return "\n".join(lines).strip()


def direct_validate_json(
    raw_json: dict[str, Any] | list | str, schema_model: type[BaseModel]
) -> BaseModel | None:
    """Attempt deterministic direct validation using Pydantic without LLM.

    :param raw_json: Parsed JSON dict/list or raw JSON string.
    :param schema_model: Target Pydantic model class.
    :return: Validated BaseModel instance if successful, None otherwise.
    """
    if isinstance(raw_json, str):
        try:
            return schema_model.model_validate_json(raw_json)
        except Exception:
            try:
                raw_json = json.loads(raw_json)
            except Exception:
                return None

    if isinstance(raw_json, dict):
        try:
            return schema_model.model_validate(raw_json)
        except Exception:
            pass

        # Smart fallback for common listing JSON structures (e.g. {"quotes": [...], "page": 1})
        if schema_model.__name__ == "Listing":
            items_list = None
            for key in ("items", "quotes", "results", "data", "articles", "products"):
                if key in raw_json and isinstance(raw_json[key], list):
                    items_list = raw_json[key]
                    break
            if items_list is not None:
                formatted_items = []
                for elem in items_list:
                    if isinstance(elem, dict):
                        formatted_items.append({str(k): str(v) for k, v in elem.items()})
                    else:
                        formatted_items.append({"value": str(elem)})
                try:
                    return schema_model.model_validate(
                        {
                            "title": str(raw_json.get("title") or "JSON Listing Data"),
                            "items": formatted_items,
                            "total_count": len(items_list),
                            "page_number": raw_json.get("page") or raw_json.get("page_number"),
                        }
                    )
                except Exception:
                    pass

    elif isinstance(raw_json, list):
        if schema_model.__name__ == "Listing":
            formatted_items = [
                {str(k): str(v) for k, v in elem.items()} if isinstance(elem, dict) else {"value": str(elem)}
                for elem in raw_json
            ]
            try:
                return schema_model.model_validate(
                    {
                        "title": "JSON Listing Data",
                        "items": formatted_items,
                        "total_count": len(raw_json),
                    }
                )
            except Exception:
                pass

        if hasattr(schema_model, "items"):
            try:
                return schema_model.model_validate({"items": raw_json})
            except Exception:
                pass

    return None


class LocalExtractor:
    """In-process LLM extractor utilizing llama-cpp-python."""

    def __init__(self, model_path: Path | None = None, temperature: float = 0.1) -> None:
        """Initialize LocalExtractor.

        :param model_path: Path to .gguf model file.
        :param temperature: LLM sampling temperature (0.0 to 0.1).
        """
        self.model_path = model_path
        self.temperature = max(0.0, min(0.1, temperature))
        self._llm = None

    def _get_llm(self) -> Any:
        """Lazy loader for llama_cpp.Llama instance."""
        if self._llm is not None:
            return self._llm

        if not self.model_path or not self.model_path.exists():
            raise ConfigError(
                f"Cannot perform LLM extraction: MODEL_PATH is missing or file does not exist.\n"
                f"Path provided: {self.model_path}\n"
                "Action required: Set MODEL_PATH env var to a valid .gguf model file path."
            )

        try:
            from llama_cpp import Llama

            self._llm = Llama(
                model_path=str(self.model_path),
                n_ctx=2048,
                verbose=False,
            )
            return self._llm
        except Exception as e:
            raise ExtractionError(f"Failed to load llama.cpp model from {self.model_path}: {e}")

    def extract(
        self,
        content: str,
        schema_model: type[BaseModel],
        max_retries: int = 2,
    ) -> ExtractionResult:
        """Perform LLM extraction on content constrained by schema_model's JSON schema.

        Retries up to max_retries times on validation failure.

        :param content: Raw input text/HTML.
        :param schema_model: Target Pydantic model class.
        :param max_retries: Number of retries on validation failure (default 2).
        :return: ExtractionResult containing validated data and metrics.
        :raises ExtractionError: If extraction fails after retries.
        """
        llm = self._get_llm()
        json_schema = schema_model.model_json_schema()

        system_prompt = (
            "You are a precise data extraction assistant. Extract structured data from the provided text "
            "matching the target JSON schema exactly. Return only valid JSON object."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Extract structured data from the following text:\n\n{content}"},
        ]

        response_format = {
            "type": "json_object",
            "schema": json_schema,
        }

        retries_done = 0
        last_error = ""

        for attempt in range(max_retries + 1):
            start_time = time.time()
            try:
                response = llm.create_chat_completion(
                    messages=messages,
                    temperature=self.temperature,
                    response_format=response_format,
                )

                elapsed = time.time() - start_time
                choice = response["choices"][0]
                completion_text = choice["message"]["content"]

                # Calculate tokens per second metrics
                usage = response.get("usage", {})
                completion_tokens = usage.get("completion_tokens", 0)
                tok_per_sec = (completion_tokens / elapsed) if elapsed > 0 else 0.0

                # Validate with Pydantic model
                validated_data = schema_model.model_validate_json(completion_text)
                json_dict = validated_data.model_dump()
                md_output = model_to_markdown(validated_data)

                return ExtractionResult(
                    data=validated_data,
                    json_output=json_dict,
                    markdown_output=md_output,
                    used_llm=True,
                    tokens_per_second=round(tok_per_sec, 2),
                    model_name=self.model_path.name if self.model_path else "llama.cpp",
                    temperature=self.temperature,
                    retries=retries_done,
                )

            except ValidationError as ve:
                last_error = f"Pydantic Validation Error: {ve}"
            except Exception as e:
                last_error = f"LLM Generation Error: {e}"

            retries_done += 1
            if attempt < max_retries:
                # Add validation error hint to message prompt for retry
                messages.append(
                    {
                        "role": "user",
                        "content": f"Your previous JSON output failed validation with error:\n{last_error}\n"
                        "Please fix the format and output valid JSON matching the schema.",
                    }
                )

        raise ExtractionError(
            f"Extraction failed after {max_retries + 1} attempts. Last error: {last_error}"
        )


def extract_data(
    raw_content: str | dict[str, Any] | list,
    schema_name: str = "Article",
    is_json_payload: bool = False,
    extractor_override: Any | None = None,
) -> ExtractionResult:
    """Main extraction entrypoint. Attempts direct validation first, falling back to LLM.

    :param raw_content: Raw payload content (string HTML/text or dict/list).
    :param schema_name: Name of target Pydantic schema model.
    :param is_json_payload: Flag indicating if input is already clean JSON.
    :param extractor_override: Optional custom extractor instance (e.g. for testing).
    :return: ExtractionResult instance.
    """
    settings = get_settings()
    schema_cls = get_schema(schema_name)

    # 1. Deterministic direct JSON parsing check
    if is_json_payload or isinstance(raw_content, (dict, list)):
        validated = direct_validate_json(raw_content, schema_cls)
        if validated is not None:
            return ExtractionResult(
                data=validated,
                json_output=validated.model_dump(),
                markdown_output=model_to_markdown(validated),
                used_llm=False,
                tokens_per_second=0.0,
                model_name="N/A (Direct JSON)",
                temperature=0.0,
                retries=0,
            )

    # If raw content is string, try direct JSON validation once more
    if isinstance(raw_content, str) and raw_content.strip().startswith(("{", "[")):
        validated = direct_validate_json(raw_content, schema_cls)
        if validated is not None:
            return ExtractionResult(
                data=validated,
                json_output=validated.model_dump(),
                markdown_output=model_to_markdown(validated),
                used_llm=False,
                tokens_per_second=0.0,
                model_name="N/A (Direct JSON)",
                temperature=0.0,
                retries=0,
            )

    # 2. LLM Extraction fallback
    if extractor_override is not None:
        extractor = extractor_override
    else:
        try:
            model_path = settings.get_model_path(require_exists=True)
        except ConfigError as ce:
            raise ExtractionError(
                f"Direct JSON parsing failed and LLM extraction cannot proceed: {ce}"
            )
        extractor = LocalExtractor(
            model_path=model_path,
            temperature=settings.llm_temperature,
        )

    content_str = (
        json.dumps(raw_content) if isinstance(raw_content, (dict, list)) else str(raw_content)
    )
    return extractor.extract(content_str, schema_cls)
