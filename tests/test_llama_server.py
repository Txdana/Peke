"""Tests for standalone llama.cpp runtime discovery and API validation."""
import json
from pathlib import Path
from urllib.error import URLError

import pytest

from peke.llama_server import LlamaServer, LlamaServerError


def test_runtime_resolves_explicit_path(tmp_path, monkeypatch):
    binary = tmp_path / ("llama-server.exe" if __import__("os").name == "nt" else "llama-server")
    binary.write_text("fixture", encoding="utf-8")
    monkeypatch.setenv("LLAMA_SERVER_PATH", str(binary))
    assert LlamaServer._resolve_executable(None) == binary.resolve()


def test_runtime_does_not_accept_missing_explicit_path(tmp_path, monkeypatch):
    monkeypatch.setenv("LLAMA_SERVER_PATH", str(tmp_path / "missing-server"))
    assert LlamaServer._resolve_executable(None) is None


def test_complete_rejects_unexpected_api_shape(monkeypatch):
    class FakeResponse:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self):
            return json.dumps({"unexpected": True}).encode()

    monkeypatch.setattr("peke.llama_server.urlopen", lambda *args, **kwargs: FakeResponse())
    server = LlamaServer(executable="missing", model="missing.gguf")
    with pytest.raises(LlamaServerError, match="unexpected completion response"):
        server.complete("system", "user", {})
