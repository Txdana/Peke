"""Local model adapter tests; never require real weights or network access."""
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from peke.config import ConfigError, Settings
from peke.extract import ExtractionError, Extractor
from peke.schemas import Article


def test_llama_cpp_is_loaded_lazily_with_local_model_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("PEKE_ALLOW_LEGACY_LLAMA_CPP_PYTHON", "1")
    monkeypatch.setenv("LLAMA_SERVER_PATH", str(tmp_path / "no-server"))
    model_path = tmp_path / "tiny.gguf"
    model_path.write_bytes(b"test fixture is not a real model")
    fake_instance = MagicMock()
    constructor = MagicMock(return_value=fake_instance)
    monkeypatch.setitem(sys.modules, "llama_cpp", SimpleNamespace(Llama=constructor))
    settings = Settings(model_path=model_path, n_ctx=1024, n_gpu_layers=2, n_threads=3)
    extractor = Extractor(settings)

    assert constructor.call_count == 0
    assert extractor._model() is fake_instance
    constructor.assert_called_once_with(
        model_path=str(model_path), n_ctx=1024, n_gpu_layers=2, n_threads=3, verbose=False
    )
    assert extractor._model() is fake_instance
    constructor.assert_called_once()


def test_missing_local_model_fails_before_importing_backend(tmp_path):
    extractor = Extractor(Settings(model_path=tmp_path / "missing.gguf"))
    with pytest.raises(ConfigError, match="MODEL_PATH"):
        extractor._model()


def test_missing_llama_cpp_dependency_has_actionable_error(tmp_path, monkeypatch):
    monkeypatch.setenv("PEKE_ALLOW_LEGACY_LLAMA_CPP_PYTHON", "1")
    monkeypatch.setenv("LLAMA_SERVER_PATH", str(tmp_path / "no-server"))
    model_path = tmp_path / "present.gguf"
    model_path.write_bytes(b"fixture")
    monkeypatch.setitem(sys.modules, "llama_cpp", None)
    extractor = Extractor(Settings(model_path=model_path))
    with pytest.raises(ExtractionError, match="llama-cpp-python is not installed"):
        extractor._model()


def test_end_to_end_extractor_uses_fake_local_runtime(tmp_path, monkeypatch):
    monkeypatch.setenv("PEKE_ALLOW_LEGACY_LLAMA_CPP_PYTHON", "1")
    monkeypatch.setenv("LLAMA_SERVER_PATH", str(tmp_path / "no-server"))
    model_path = tmp_path / "tiny.gguf"
    model_path.write_bytes(b"test fixture is not a real model")

    class FakeLlama:
        def __init__(self, model_path, **kwargs):
            self.model_path = model_path

        def create_chat_completion(self, **kwargs):
            return {
                "choices": [{"message": {"content": '{"title":"Local test","summary":"fixture"}'}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 8},
            }

    monkeypatch.setitem(sys.modules, "llama_cpp", SimpleNamespace(Llama=FakeLlama))
    result = Extractor(Settings(model_path=model_path)).run("A source page.", Article)
    assert result.model.title == "Local test"
    assert result.model.summary == "fixture"
    assert result.attempts == 1
    assert result.model_name == str(model_path)
