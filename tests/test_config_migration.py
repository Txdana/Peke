"""Unit tests for configuration migration and structured settings."""
import json

import pytest

from peke.config import ConfigError, load_settings


def test_legacy_flat_settings_migration(tmp_path, monkeypatch):
    monkeypatch.setattr("platformdirs.user_config_dir", lambda app, org: str(tmp_path))

    model_file = tmp_path / "legacy.gguf"
    model_file.write_text("dummy model")

    settings_json = tmp_path / "settings.json"
    settings_json.write_text(json.dumps({
        "MODEL_PATH": str(model_file),
        "N_CTX": 4096,
        "N_GPU_LAYERS": 10,
    }))

    s = load_settings()
    assert s.model_path == model_file
    assert s.n_ctx == 4096
    assert s.n_gpu_layers == 10
    assert s.provider_main_kind == "local_builtin"
    assert s.provider_main_auto_download is True


def test_toml_config_support(tmp_path, monkeypatch):
    monkeypatch.setattr("platformdirs.user_config_dir", lambda app, org: str(tmp_path))

    config_toml = tmp_path / "config.toml"
    config_toml.write_text("""
[providers.main]
kind = "ollama"
auto_download = false
repo = "my-repo"
file = "my-file.gguf"

[subagents]
enabled = true
step_timeout_seconds = 20.0

[updates]
auto_check = false
channel = "stable"
""")

    s = load_settings()
    assert s.provider_main_kind == "ollama"
    assert s.provider_main_auto_download is False
    assert s.provider_main_repo == "my-repo"
    assert s.subagents_step_timeout_seconds == 20.0
    assert s.updates_auto_check is False


def test_environment_variable_precedence(tmp_path, monkeypatch):
    monkeypatch.setattr("platformdirs.user_config_dir", lambda app, org: str(tmp_path))
    monkeypatch.setenv("PROVIDER_MAIN_KIND", "openrouter")
    monkeypatch.setenv("UPDATES_CHANNEL", "stable")

    s = load_settings()
    assert s.provider_main_kind == "openrouter"
    assert s.updates_channel == "stable"


def test_invalid_settings_validation(tmp_path, monkeypatch):
    monkeypatch.setattr("platformdirs.user_config_dir", lambda app, org: str(tmp_path))
    monkeypatch.setenv("PROVIDER_SUBAGENTS_MODE", "invalid_mode")

    with pytest.raises(ConfigError, match="PROVIDER_SUBAGENTS_MODE must be 'auto' or 'per_role'"):
        load_settings()
