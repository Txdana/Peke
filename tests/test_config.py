import pytest

from peke.config import ConfigError, Settings, load_settings


def test_temperature_is_clamped(monkeypatch):
    monkeypatch.setenv("TEMPERATURE", "2")
    assert load_settings().temperature == 0.1
    monkeypatch.setenv("TEMPERATURE", "-1")
    assert load_settings().temperature == 0.0


def test_missing_model_has_actionable_error(tmp_path):
    settings = Settings(model_path=tmp_path / "missing.gguf")
    with pytest.raises(ConfigError, match="MODEL_PATH"):
        settings.require_model()


def test_model_path_must_be_gguf(tmp_path):
    model_path = tmp_path / "model.bin"
    model_path.write_bytes(b"not a model")
    with pytest.raises(ConfigError, match="must point to a local .gguf"):
        Settings(model_path=model_path).require_model()
