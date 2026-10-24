"""Ollama local provider implementation."""
import json
import logging
import time
from typing import Any

import httpx

from peke.providers.base import HealthResult, Provider, ProviderError, ProviderResult

logger = logging.getLogger(__name__)


class OllamaProvider(Provider):
    name: str = "ollama"

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:11434",
        model_name: str = "qwen2.5:7b",
        timeout: float = 60.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self.timeout = timeout

    def health_check(self) -> HealthResult:
        try:
            url = f"{self.base_url}/api/tags"
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    models = [m.get("name") for m in data.get("models", [])]
                    return HealthResult(
                        ok=True,
                        message=f"Ollama connected ({len(models)} model(s) available)",
                        details={"models": models, "base_url": self.base_url},
                    )
                return HealthResult(
                    ok=False,
                    message=f"Ollama returned HTTP {resp.status_code}",
                    details={"status_code": resp.status_code},
                )
        except Exception as exc:
            return HealthResult(
                ok=False,
                message=f"Ollama server not reachable at {self.base_url}: {exc}",
                details={"hint": "Ensure Ollama server is running on the target port."},
            )

    def list_models(self) -> list[str]:
        """Return list of available Ollama models."""
        try:
            url = f"{self.base_url}/api/tags"
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    return [m.get("name") for m in data.get("models", []) if m.get("name")]
        except Exception as exc:
            logger.debug("Failed to list Ollama models: %s", exc)
        return []

    def complete_json(
        self,
        system: str,
        user: str,
        json_schema: dict[str, Any],
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> ProviderResult:
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": f"{system}\nReturn valid JSON matching schema:\n{json.dumps(json_schema)}"},
                {"role": "user", "content": user},
            ],
            "format": json_schema,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
            "stream": False,
        }

        start_time = time.perf_counter()
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(url, json=payload)
                elapsed = max(time.perf_counter() - start_time, 0.000001)

                if resp.status_code == 404:
                    raise ProviderError(
                        f"Ollama model {self.model_name!r} not found.",
                        retryable=False,
                        hint=f"Run 'ollama pull {self.model_name}' to download the model.",
                    )
                if resp.status_code != 200:
                    raise ProviderError(
                        f"Ollama error HTTP {resp.status_code}: {resp.text[:200]}",
                        retryable=True,
                    )

                data = resp.json()
                content = data.get("message", {}).get("content", "")
                prompt_eval_count = data.get("prompt_eval_count", 0)
                eval_count = data.get("eval_count", 0)
                eval_duration_ns = data.get("eval_duration", 0)
                tps = (eval_count / (eval_duration_ns / 1e9)) if eval_duration_ns > 0 else (eval_count / elapsed)

                parsed: Any | None = None
                try:
                    parsed = json.loads(content)
                except json.JSONDecodeError:
                    parsed = None

                return ProviderResult(
                    raw_text=content,
                    parsed=parsed,
                    model_name=self.model_name,
                    prompt_tokens=prompt_eval_count,
                    completion_tokens=eval_count,
                    tokens_per_second=tps,
                    latency_ms=elapsed * 1000.0,
                    provider_name=self.name,
                )
        except httpx.ConnectError as exc:
            raise ProviderError(
                f"Could not connect to Ollama at {self.base_url}: {exc}",
                retryable=True,
                hint="Verify Ollama is installed and running.",
            ) from exc
        except httpx.TimeoutException as exc:
            raise ProviderError(
                f"Ollama request timed out after {self.timeout}s: {exc}",
                retryable=True,
            ) from exc
        except Exception as exc:
            if isinstance(exc, ProviderError):
                raise
            raise ProviderError(f"Ollama request failed: {exc}", retryable=True) from exc
