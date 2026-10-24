"""Provider registry and factory functions."""
import logging
from pathlib import Path
from typing import Any

from peke.config import Settings
from peke.providers.base import Provider
from peke.providers.custom_openai import CustomOpenAIProvider
from peke.providers.local_llamacpp import LocalLlamaCppProvider
from peke.providers.ollama import OllamaProvider
from peke.providers.openrouter import OpenRouterProvider

logger = logging.getLogger(__name__)


def get_provider(
    kind_or_role: str = "local_builtin",
    settings: Settings | None = None,
    model_path: Path | None = None,
    provider_config: dict[str, Any] | None = None,
) -> Provider:
    """Return an instantiated Provider for the requested kind or role."""
    if settings is None:
        from peke.config import load_settings

        settings = load_settings()

    config = provider_config or {}
    kind = config.get("kind", kind_or_role)

    if kind in {"local_builtin", "local_llamacpp", "local"}:
        return LocalLlamaCppProvider(settings=settings, model_path=model_path)

    if kind in {"local_custom_path", "custom_path"}:
        path = model_path or (Path(config["path"]) if "path" in config else settings.model_path)
        return LocalLlamaCppProvider(settings=settings, model_path=path)

    if kind == "ollama":
        base_url = config.get("base_url", "http://127.0.0.1:11434")
        model_name = config.get("model_name", "qwen2.5:7b")
        return OllamaProvider(base_url=base_url, model_name=model_name)

    if kind == "openrouter":
        model_name = config.get("model_name", "meta-llama/llama-3.3-70b-instruct")
        api_key = config.get("api_key")
        referer = config.get("referer", "https://github.com/Txdana/Peke")
        return OpenRouterProvider(model_name=model_name, api_key=api_key, referer=referer)

    if kind == "custom_openai":
        base_url = config.get("base_url", "http://127.0.0.1:8000/v1")
        model_name = config.get("model_name", "default-model")
        display_name = config.get("display_name", "Custom OpenAI")
        api_key = config.get("api_key")
        headers = config.get("headers")
        return CustomOpenAIProvider(
            base_url=base_url,
            model_name=model_name,
            display_name=display_name,
            api_key=api_key,
            extra_headers=headers,
        )

    logger.warning("Unknown provider kind %r; falling back to local_builtin", kind)
    return LocalLlamaCppProvider(settings=settings, model_path=model_path)
