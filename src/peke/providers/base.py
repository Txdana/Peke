"""Base provider interfaces and result types."""
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class HealthResult:
    ok: bool
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderResult:
    raw_text: str
    parsed: Any | None
    model_name: str
    prompt_tokens: int
    completion_tokens: int
    tokens_per_second: float
    latency_ms: float
    provider_name: str


class ProviderError(Exception):
    """Exception raised when provider completion fails."""

    def __init__(self, message: str, retryable: bool = False, hint: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.retryable = retryable
        self.hint = hint or message


@runtime_checkable
class Provider(Protocol):
    name: str

    def health_check(self) -> HealthResult:
        """Return provider connectivity and health status."""
        ...

    def complete_json(
        self,
        system: str,
        user: str,
        json_schema: dict[str, Any],
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> ProviderResult:
        """Perform a schema-constrained JSON completion."""
        ...
