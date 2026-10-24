"""Pluggable AI model provider architecture for Peke."""
from peke.providers.base import HealthResult, Provider, ProviderError, ProviderResult
from peke.providers.custom_openai import CustomOpenAIProvider, validate_provider_url
from peke.providers.local_llamacpp import LocalLlamaCppProvider
from peke.providers.ollama import OllamaProvider
from peke.providers.openrouter import OpenRouterProvider
from peke.providers.registry import get_provider
from peke.providers.secrets import delete_secret, get_secret, set_secret

__all__ = [
    "HealthResult",
    "Provider",
    "ProviderError",
    "ProviderResult",
    "LocalLlamaCppProvider",
    "OllamaProvider",
    "OpenRouterProvider",
    "CustomOpenAIProvider",
    "get_provider",
    "get_secret",
    "set_secret",
    "delete_secret",
    "validate_provider_url",
]
