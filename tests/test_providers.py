"""Unit tests for pluggable AI model providers."""
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel

from peke.config import Settings
from peke.extract import Extractor
from peke.providers import (
    CustomOpenAIProvider,
    LocalLlamaCppProvider,
    OllamaProvider,
    OpenRouterProvider,
    ProviderError,
    ProviderResult,
    get_provider,
    get_secret,
    set_secret,
    validate_provider_url,
)


class DummySchema(BaseModel):
    title: str
    count: int


def test_validate_provider_url():
    assert validate_provider_url("http://localhost:11434") == "http://localhost:11434"
    assert validate_provider_url("https://api.openai.com/v1/") == "https://api.openai.com/v1"
    with pytest.raises(ValueError):
        validate_provider_url("ftp://example.com")
    with pytest.raises(ValueError):
        validate_provider_url("")


def test_secrets_fallback(tmp_path, monkeypatch):
    import json
    import sys
    import types

    monkeypatch.setattr("platformdirs.user_config_dir", lambda app, org: str(tmp_path))
    fake_keyring = types.ModuleType("keyring")
    fake_keyring.set_password = MagicMock(side_effect=Exception("No keyring"))
    fake_keyring.get_password = MagicMock(return_value=None)
    fake_keyring.get_keyring = MagicMock(side_effect=Exception("No keyring"))
    monkeypatch.setitem(sys.modules, "keyring", fake_keyring)
    fake_tomli_w = types.ModuleType("tomli_w")
    fake_tomli_w.dumps = lambda data: "\n".join(
        f"{key} = {json.dumps(value)}" for key, value in data.items()
    ) + "\n"
    monkeypatch.setitem(sys.modules, "tomli_w", fake_tomli_w)

    set_secret("test_key", "secret123")
    val = get_secret("test_key")
    assert val == "secret123"

    secrets_file = tmp_path / "secrets.toml"
    assert secrets_file.is_file()
    assert "secret123" in secrets_file.read_text()


def test_local_llamacpp_health_check(tmp_path):
    model_file = tmp_path / "model.gguf"
    model_file.write_text("fake model content")
    settings = Settings(model_path=model_file)
    provider = LocalLlamaCppProvider(settings)

    health = provider.health_check()
    assert health.ok is True
    assert "model.gguf" in health.message


def test_ollama_provider_health_check():
    provider = OllamaProvider(base_url="http://127.0.0.1:11434")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"models": [{"name": "qwen2.5:7b"}]}

    with patch("httpx.Client.get", return_value=mock_resp):
        health = provider.health_check()
        assert health.ok is True
        assert "qwen2.5:7b" in str(health.details.get("models"))


def test_ollama_provider_complete_json():
    provider = OllamaProvider(base_url="http://127.0.0.1:11434", model_name="qwen2.5:7b")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "message": {"content": '{"title": "Test", "count": 5}'},
        "prompt_eval_count": 10,
        "eval_count": 20,
        "eval_duration": 1000000000,
    }

    with patch("httpx.Client.post", return_value=mock_resp):
        res = provider.complete_json(
            system="System prompt",
            user="User prompt",
            json_schema=DummySchema.model_json_schema(),
        )
        assert res.parsed == {"title": "Test", "count": 5}
        assert res.completion_tokens == 20
        assert res.provider_name == "ollama"


def test_openrouter_provider_complete_json():
    provider = OpenRouterProvider(api_key="sk-or-testkey", model_name="test/model")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": '{"title": "OpenRouter", "count": 10}'}}],
        "usage": {"prompt_tokens": 15, "completion_tokens": 25},
    }

    with patch("httpx.Client.post", return_value=mock_resp):
        res = provider.complete_json("System", "User", DummySchema.model_json_schema())
        assert res.parsed == {"title": "OpenRouter", "count": 10}
        assert res.prompt_tokens == 15


def test_openrouter_auth_failure():
    provider = OpenRouterProvider(api_key="bad-key")
    mock_resp = MagicMock()
    mock_resp.status_code = 401

    with patch("httpx.Client.post", return_value=mock_resp):
        with pytest.raises(ProviderError) as exc_info:
            provider.complete_json("System", "User", DummySchema.model_json_schema())
        assert exc_info.value.retryable is False
        assert "HTTP 401" in str(exc_info.value)


def test_custom_openai_provider():
    provider = CustomOpenAIProvider(
        base_url="http://127.0.0.1:8000/v1",
        model_name="my-custom-model",
        display_name="vLLM Server",
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": '{"title": "vLLM", "count": 42}'}}],
        "usage": {"prompt_tokens": 8, "completion_tokens": 12},
    }

    with patch("httpx.Client.post", return_value=mock_resp):
        res = provider.complete_json("System", "User", DummySchema.model_json_schema())
        assert res.parsed == {"title": "vLLM", "count": 42}


def test_extractor_with_mock_provider():
    mock_provider = MagicMock()
    mock_provider.complete_json.return_value = ProviderResult(
        raw_text='{"title": "Extracted", "count": 100}',
        parsed={"title": "Extracted", "count": 100},
        model_name="mock-model",
        prompt_tokens=10,
        completion_tokens=20,
        tokens_per_second=10.0,
        latency_ms=2000.0,
        provider_name="mock",
    )

    settings = Settings(model_path=None)
    extractor = Extractor(settings=settings, provider=mock_provider)
    res = extractor.run("Source text", DummySchema)

    assert res.model.title == "Extracted"
    assert res.model.count == 100
    assert res.prompt_tokens == 10


def test_get_provider_registry(tmp_path):
    settings = Settings(model_path=tmp_path / "model.gguf")
    p1 = get_provider("local_builtin", settings=settings)
    assert isinstance(p1, LocalLlamaCppProvider)

    p2 = get_provider("ollama", settings=settings, provider_config={"base_url": "http://localhost:11434"})
    assert isinstance(p2, OllamaProvider)

    p3 = get_provider("openrouter", settings=settings, provider_config={"model_name": "test/model"})
    assert isinstance(p3, OpenRouterProvider)

    p4 = get_provider("custom_openai", settings=settings, provider_config={"base_url": "http://127.0.0.1:8000"})
    assert isinstance(p4, CustomOpenAIProvider)


def test_secret_file_fallback_is_private_and_atomic(tmp_path, monkeypatch):
    import json
    import os
    import sys
    import types

    import peke.providers.secrets as secrets_module

    config_dir = tmp_path / "config"
    victim = tmp_path / "victim.txt"
    victim.write_text("do not overwrite", encoding="utf-8")
    legacy_temp = config_dir / "secrets.toml.tmp"
    config_dir.mkdir()
    try:
        legacy_temp.symlink_to(victim)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is unavailable on this platform")
    monkeypatch.setattr(secrets_module, "_secrets_toml_path", lambda: config_dir / "secrets.toml")

    fake_keyring = types.ModuleType("keyring")
    fake_keyring.get_keyring = MagicMock(side_effect=Exception("No keyring"))
    monkeypatch.setitem(sys.modules, "keyring", fake_keyring)
    fake_tomli_w = types.ModuleType("tomli_w")
    fake_tomli_w.dumps = lambda data: "\n".join(
        f"{key} = {json.dumps(value)}" for key, value in data.items()
    ) + "\n"
    monkeypatch.setitem(sys.modules, "tomli_w", fake_tomli_w)

    set_secret("token", "private-value")
    secret_path = config_dir / "secrets.toml"

    assert victim.read_text(encoding="utf-8") == "do not overwrite"
    assert secret_path.read_text(encoding="utf-8").strip() == 'token = "private-value"'
    if os.name != "nt":
        assert config_dir.stat().st_mode & 0o777 == 0o700
        assert secret_path.stat().st_mode & 0o777 == 0o600


def test_secret_file_fallback_refuses_destination_symlink(tmp_path, monkeypatch):
    import sys
    import types

    import peke.providers.secrets as secrets_module

    config_dir = tmp_path / "config"
    config_dir.mkdir(mode=0o700)
    victim = tmp_path / "victim.txt"
    victim.write_text("keep safe", encoding="utf-8")
    secret_path = config_dir / "secrets.toml"
    try:
        secret_path.symlink_to(victim)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is unavailable on this platform")
    monkeypatch.setattr(secrets_module, "_secrets_toml_path", lambda: secret_path)

    fake_keyring = types.ModuleType("keyring")
    fake_keyring.get_keyring = MagicMock(side_effect=Exception("No keyring"))
    monkeypatch.setitem(sys.modules, "keyring", fake_keyring)
    fake_tomli_w = types.ModuleType("tomli_w")
    fake_tomli_w.dumps = lambda _data: 'token = "secret"\n'
    monkeypatch.setitem(sys.modules, "tomli_w", fake_tomli_w)

    with pytest.raises(OSError, match="symbolic link"):
        set_secret("token", "secret")
    assert victim.read_text(encoding="utf-8") == "keep safe"
