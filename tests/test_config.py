"""Tests for config settings and MODEL_PATH validation."""


import pytest

from peke.config import ConfigError, Settings


def test_config_defaults(monkeypatch):
    monkeypatch.delenv("MODEL_PATH", raising=False)
    monkeypatch.setenv("FETCH_TIMEOUT", "45")
    monkeypatch.setenv("LLM_TEMPERATURE", "0.05")

    settings = Settings()
    assert settings.fetch_timeout == 45
    assert settings.llm_temperature == 0.05


def test_temperature_clamping(monkeypatch):
    monkeypatch.setenv("LLM_TEMPERATURE", "0.8")
    settings = Settings()
    # Should clamp temperature to max 0.1 per constraints
    assert settings.llm_temperature == 0.1


def test_missing_model_path_raises_error(monkeypatch):
    monkeypatch.delenv("MODEL_PATH", raising=False)
    settings = Settings()
    with pytest.raises(ConfigError) as exc_info:
        settings.get_model_path(require_exists=True)
    assert "MODEL_PATH is not set" in str(exc_info.value)


def test_nonexistent_model_path_raises_error(monkeypatch, tmp_path):
    fake_path = tmp_path / "nonexistent.gguf"
    monkeypatch.setenv("MODEL_PATH", str(fake_path))
    settings = Settings()
    with pytest.raises(ConfigError) as exc_info:
        settings.get_model_path(require_exists=True)
    assert "GGUF model file not found" in str(exc_info.value)


def test_valid_model_path(monkeypatch, tmp_path):
    model_file = tmp_path / "test_model.gguf"
    model_file.write_text("dummy gguf content")
    monkeypatch.setenv("MODEL_PATH", str(model_file))
    settings = Settings()
    path = settings.get_model_path(require_exists=True)
    assert path == model_file
