"""Local llama.cpp provider implementation."""
import json
import logging
import time
from pathlib import Path
from typing import Any

from filelock import FileLock

from peke.config import Settings
from peke.providers.base import HealthResult, Provider, ProviderError, ProviderResult

logger = logging.getLogger(__name__)


class LocalLlamaCppProvider(Provider):
    name: str = "local_llamacpp"

    def __init__(self, settings: Settings, model_path: Path | None = None) -> None:
        self.settings = settings
        self.custom_model_path = model_path
        self._llm: Any | None = None
        self._lock_path = Path.home() / ".peke" / "model.lock"

    def _get_model_path(self) -> Path:
        if self.custom_model_path and self.custom_model_path.is_file():
            return self.custom_model_path
        return self.settings.require_model()

    def health_check(self) -> HealthResult:
        try:
            path = self._get_model_path()
            if not path.is_file():
                return HealthResult(ok=False, message=f"Model file not found: {path}")
            return HealthResult(
                ok=True,
                message=f"Local model ready: {path.name}",
                details={"path": str(path), "size_bytes": path.stat().st_size},
            )
        except Exception as exc:
            return HealthResult(ok=False, message=f"Local llama.cpp model unavailable: {exc}")

    def _get_llm(self) -> Any:
        if self._llm is None:
            model_path = self._get_model_path()
            try:
                from llama_cpp import Llama
            except ImportError as exc:
                from peke.extract import ExtractionError

                raise ExtractionError("llama-cpp-python is not installed; install Peke dependencies.") from exc
            try:
                self._llm = Llama(
                    model_path=str(model_path),
                    n_ctx=self.settings.n_ctx,
                    n_gpu_layers=self.settings.n_gpu_layers,
                    n_threads=self.settings.n_threads or None,
                    verbose=False,
                )
            except Exception as exc:
                raise ProviderError(
                    f"Failed to load local model {model_path.name}: {exc}",
                    retryable=False,
                    hint="Ensure the GGUF model file is valid and supported by llama-cpp-python.",
                ) from exc
        return self._llm

    def complete_json(
        self,
        system: str,
        user: str,
        json_schema: dict[str, Any],
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> ProviderResult:
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock = FileLock(str(self._lock_path), timeout=60)
        start_time = time.perf_counter()
        with lock:
            llm = self._get_llm()
            messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ]
            try:
                response = llm.create_chat_completion(
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format={"type": "json_object", "schema": json_schema},
                )
                elapsed = max(time.perf_counter() - start_time, 0.000001)
                raw_text = response["choices"][0]["message"]["content"]
                usage = response.get("usage", {})
                prompt_tokens = int(usage.get("prompt_tokens", 0))
                completion_tokens = int(usage.get("completion_tokens", 0))
                tokens_per_second = completion_tokens / elapsed if elapsed > 0 else 0.0

                parsed: Any | None = None
                try:
                    parsed = json.loads(raw_text)
                except json.JSONDecodeError:
                    parsed = None

                return ProviderResult(
                    raw_text=raw_text,
                    parsed=parsed,
                    model_name=str(self._get_model_path().name),
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    tokens_per_second=tokens_per_second,
                    latency_ms=elapsed * 1000.0,
                    provider_name=self.name,
                )
            except Exception as exc:
                raise ProviderError(
                    f"llama.cpp execution failed: {exc}",
                    retryable=True,
                    hint="Check model context window and resource limits.",
                ) from exc
