"""OpenRouter cloud provider implementation."""
import json
import logging
import time
from typing import Any

import httpx

from peke.providers.base import HealthResult, Provider, ProviderError, ProviderResult
from peke.providers.secrets import get_secret

logger = logging.getLogger(__name__)

_MODEL_CACHE: dict[str, Any] = {"timestamp": 0.0, "models": []}
CACHE_TTL_SECONDS = 3600.0


class OpenRouterProvider(Provider):
    name: str = "openrouter"

    def __init__(
        self,
        model_name: str = "meta-llama/llama-3.3-70b-instruct",
        api_key: str | None = None,
        referer: str | None = "https://github.com/Txdana/Peke",
        timeout: float = 60.0,
    ) -> None:
        self.base_url = "https://openrouter.ai/api/v1"
        self.model_name = model_name
        self._api_key = api_key
        self.referer = referer
        self.timeout = timeout

    def _get_key(self) -> str | None:
        return self._api_key or get_secret("openrouter_api_key")

    def health_check(self) -> HealthResult:
        key = self._get_key()
        if not key:
            return HealthResult(
                ok=False,
                message="OpenRouter API key is missing.",
                details={"hint": "Set OpenRouter API key in settings or keyring."},
            )
        try:
            models = self.list_models()
            return HealthResult(
                ok=True,
                message=f"OpenRouter connected ({len(models)} model(s) available)",
                details={"cached_models_count": len(models)},
            )
        except Exception as exc:
            return HealthResult(
                ok=False,
                message=f"OpenRouter health check failed: {exc}",
            )

    def list_models(self, force_refresh: bool = False) -> list[dict[str, Any]]:
        """Return list of available models from OpenRouter with pricing if available."""
        now = time.time()
        if not force_refresh and _MODEL_CACHE["models"] and (now - _MODEL_CACHE["timestamp"] < CACHE_TTL_SECONDS):
            return _MODEL_CACHE["models"]

        headers = {"X-Title": "Peke"}
        if self.referer:
            headers["HTTP-Referer"] = self.referer
        key = self._get_key()
        if key:
            headers["Authorization"] = f"Bearer {key}"

        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(f"{self.base_url}/models", headers=headers)
                if resp.status_code == 200:
                    data = resp.json().get("data", [])
                    result = []
                    for m in data:
                        pricing = m.get("pricing", {})
                        prompt_cost = float(pricing.get("prompt", 0) or 0) * 1e6
                        completion_cost = float(pricing.get("completion", 0) or 0) * 1e6
                        result.append({
                            "id": m.get("id"),
                            "name": m.get("name", m.get("id")),
                            "prompt_cost_per_m": prompt_cost,
                            "completion_cost_per_m": completion_cost,
                            "context_length": m.get("context_length", 0),
                        })
                    _MODEL_CACHE["timestamp"] = now
                    _MODEL_CACHE["models"] = result
                    return result
        except Exception as exc:
            logger.debug("Failed to list OpenRouter models: %s", exc)

        return _MODEL_CACHE["models"]

    def complete_json(
        self,
        system: str,
        user: str,
        json_schema: dict[str, Any],
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> ProviderResult:
        key = self._get_key()
        if not key:
            raise ProviderError(
                "OpenRouter API key is missing.",
                retryable=False,
                hint="Save your OpenRouter API key in Peke settings.",
            )

        headers = {
            "Authorization": f"Bearer {key}",
            "X-Title": "Peke",
            "Content-Type": "application/json",
        }
        if self.referer:
            headers["HTTP-Referer"] = self.referer

        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": f"{system}\nReturn JSON matching schema:\n{json.dumps(json_schema)}"},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        url = f"{self.base_url}/chat/completions"
        start_time = time.perf_counter()
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(url, json=payload, headers=headers)
                elapsed = max(time.perf_counter() - start_time, 0.000001)

                if resp.status_code == 401:
                    raise ProviderError(
                        "OpenRouter authentication failed (HTTP 401). Invalid API key.",
                        retryable=False,
                        hint="Check your OpenRouter API key.",
                    )
                if resp.status_code == 402:
                    raise ProviderError(
                        "OpenRouter payment required (HTTP 402). Insufficient credits.",
                        retryable=False,
                        hint="Add credits to your OpenRouter account.",
                    )
                if resp.status_code == 429:
                    raise ProviderError(
                        "OpenRouter rate limit exceeded (HTTP 429).",
                        retryable=True,
                        hint="Wait a moment before retrying or check your quota.",
                    )
                if resp.status_code != 200:
                    raise ProviderError(
                        f"OpenRouter returned HTTP {resp.status_code}: {resp.text[:200]}",
                        retryable=True,
                    )

                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                usage = data.get("usage", {})
                prompt_tokens = int(usage.get("prompt_tokens", 0))
                completion_tokens = int(usage.get("completion_tokens", 0))
                tps = completion_tokens / elapsed if elapsed > 0 else 0.0

                parsed: Any | None = None
                try:
                    parsed = json.loads(content)
                except json.JSONDecodeError:
                    parsed = None

                return ProviderResult(
                    raw_text=content,
                    parsed=parsed,
                    model_name=self.model_name,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    tokens_per_second=tps,
                    latency_ms=elapsed * 1000.0,
                    provider_name=self.name,
                )
        except httpx.TimeoutException as exc:
            raise ProviderError(f"OpenRouter request timed out after {self.timeout}s: {exc}", retryable=True) from exc
        except Exception as exc:
            if isinstance(exc, ProviderError):
                raise
            raise ProviderError(f"OpenRouter request failed: {exc}", retryable=True) from exc
