"""Custom OpenAI-compatible provider implementation."""
import json
import logging
import time
from typing import Any
from urllib.parse import urlparse

import httpx

from peke.providers.base import HealthResult, Provider, ProviderError, ProviderResult
from peke.providers.secrets import get_secret

logger = logging.getLogger(__name__)


def validate_provider_url(url: str) -> str:
    """Validate and normalize a custom OpenAI provider URL."""
    if not url or not url.strip():
        raise ValueError("URL cannot be empty")
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"}:
        raise ValueError(f"Invalid URL scheme {parsed.scheme!r}; must be http or https.")
    if not parsed.netloc:
        raise ValueError("Invalid URL: missing host/netloc.")
    return url.strip().rstrip("/")


class CustomOpenAIProvider(Provider):
    name: str = "custom_openai"

    def __init__(
        self,
        base_url: str,
        model_name: str,
        display_name: str = "Custom OpenAI",
        api_key: str | None = None,
        extra_headers: dict[str, str] | None = None,
        timeout: float = 60.0,
    ) -> None:
        self.base_url = validate_provider_url(base_url)
        self.model_name = model_name
        self.display_name = display_name
        self._api_key = api_key
        self.extra_headers = extra_headers or {}
        self.timeout = timeout

    def _get_key(self) -> str | None:
        if self._api_key:
            return self._api_key
        return get_secret(f"custom_openai_{self.display_name}_api_key")

    def health_check(self) -> HealthResult:
        endpoint = f"{self.base_url}/models" if not self.base_url.endswith("/models") else self.base_url
        headers = dict(self.extra_headers)
        key = self._get_key()
        if key:
            headers["Authorization"] = f"Bearer {key}"
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(endpoint, headers=headers)
                if resp.status_code in {200, 401, 403, 404}:
                    return HealthResult(
                        ok=resp.status_code == 200,
                        message=f"{self.display_name} endpoint responsive (HTTP {resp.status_code})",
                        details={"base_url": self.base_url, "status_code": resp.status_code},
                    )
                return HealthResult(
                    ok=False,
                    message=f"{self.display_name} returned HTTP {resp.status_code}",
                    details={"base_url": self.base_url},
                )
        except Exception as exc:
            return HealthResult(
                ok=False,
                message=f"Could not reach {self.display_name} at {self.base_url}: {exc}",
            )

    def complete_json(
        self,
        system: str,
        user: str,
        json_schema: dict[str, Any],
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> ProviderResult:
        headers = {"Content-Type": "application/json"}
        headers.update(self.extra_headers)
        key = self._get_key()
        if key:
            headers["Authorization"] = f"Bearer {key}"

        chat_url = self.base_url
        if not chat_url.endswith("/chat/completions"):
            if not chat_url.endswith("/v1"):
                chat_url = f"{chat_url}/chat/completions"
            else:
                chat_url = f"{chat_url}/completions"

        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": f"{system}\nReturn valid JSON matching schema:\n{json.dumps(json_schema)}"},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        start_time = time.perf_counter()
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(chat_url, json=payload, headers=headers)
                elapsed = max(time.perf_counter() - start_time, 0.000001)

                if resp.status_code == 401:
                    raise ProviderError(
                        f"Authentication failed for {self.display_name} (HTTP 401).",
                        retryable=False,
                        hint="Check the configured API key.",
                    )
                if resp.status_code != 200:
                    raise ProviderError(
                        f"{self.display_name} returned HTTP {resp.status_code}: {resp.text[:200]}",
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
            raise ProviderError(f"{self.display_name} timed out after {self.timeout}s: {exc}", retryable=True) from exc
        except Exception as exc:
            if isinstance(exc, ProviderError):
                raise
            raise ProviderError(f"{self.display_name} request failed: {exc}", retryable=True) from exc
