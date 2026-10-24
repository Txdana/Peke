"""Regression tests for security boundaries and unsafe-input handling."""
import ast
import os
from pathlib import Path

import pytest

from peke.config import ConfigError, Settings, save_user_settings
from peke.profile import ProfileError, load_profile, redact_url


@pytest.mark.parametrize("url", [
    "file:///etc/passwd",
    "ftp://example.com/file",
    "javascript:alert(1)",
    "//example.com/path",
    "https://user:password@example.com/private",
    "https://example.com:99999/path",
    "https://example.com/\nInjected: yes",
    " https://example.com/",
])
def test_profile_rejects_unsafe_or_malformed_urls(url):
    with pytest.raises(ProfileError):
        load_profile({"url": url})


def test_profile_allows_explicit_local_http_targets():
    # Peke is a desktop tool; local development targets are legitimate and intentional.
    assert load_profile({"url": "http://127.0.0.1:8080/api"}).url == "http://127.0.0.1:8080/api"


@pytest.mark.parametrize("kwargs", [
    {"n_ctx": 0}, {"n_ctx": 1_048_577}, {"n_gpu_layers": -1},
    {"n_threads": -1}, {"max_input_chars": 0}, {"max_input_chars": 10_000_001},
    {"temperature": float("nan")}, {"temperature": float("inf")},
    {"request_delay_seconds": -1}, {"fetch_timeout": 0.01}, {"fetch_timeout": 301},
])
def test_settings_reject_invalid_resource_bounds(kwargs):
    with pytest.raises(ConfigError):
        Settings(model_path=None, **kwargs)


def test_url_redaction_removes_credentials_and_query_values():
    safe = redact_url("https://alice:secret@example.com/private?token=abc&key=xyz#frag")
    assert safe == "https://example.com/private?[REDACTED]"
    assert "secret" not in safe and "abc" not in safe and "xyz" not in safe


def test_saved_settings_are_valid_json_and_private_on_posix(tmp_path, monkeypatch):
    target = tmp_path / "settings.json"
    monkeypatch.setattr("peke.config.user_settings_path", lambda: target)
    saved = save_user_settings({"MODEL_PATH": "/models/local.gguf"}, merge=False)
    assert saved.read_text(encoding="utf-8").endswith("\n")
    assert "\\n" not in saved.read_text(encoding="utf-8")
    assert '"MODEL_PATH": "/models/local.gguf"' in saved.read_text(encoding="utf-8")
    if os.name != "nt":
        assert saved.stat().st_mode & 0o777 == 0o600


def test_security_sensitive_subprocess_calls_never_enable_shell():
    source_root = Path(__file__).parents[1] / "src" / "peke"
    for source in source_root.rglob("*.py"):
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            func_name = func.attr if isinstance(func, ast.Attribute) else func.id if isinstance(func, ast.Name) else ""
            if func_name in {"run", "Popen", "call", "check_call", "check_output"}:
                assert not any(keyword.arg == "shell" and isinstance(keyword.value, ast.Constant) and keyword.value.value is True
                               for keyword in node.keywords), f"shell=True found in {source}:{node.lineno}"
            if isinstance(func, ast.Name):
                assert func_name not in {"eval", "exec"}, f"dynamic execution found in {source}:{node.lineno}"

@pytest.mark.parametrize("headers", [
    {"X-Test\r\nInjected": "yes"},
    {"X-Test": "safe\r\nInjected: yes"},
])
def test_profile_rejects_header_injection(headers):
    with pytest.raises(ProfileError):
        load_profile({"url": "https://example.com", "headers": headers})


def test_profile_rejects_oversized_endpoint_path():
    with pytest.raises(ProfileError):
        load_profile({"url": "https://example.com", "endpoints": [{"path": "/" + "a" * 4096}]})


def test_profile_rejects_backslash_url_parser_ambiguity():
    with pytest.raises(ProfileError):
        load_profile({"url": r"https://example.com\@evil.example/path"})


def test_atomic_settings_write_does_not_follow_legacy_tmp_symlink(tmp_path, monkeypatch):
    target = tmp_path / "settings.json"
    victim = tmp_path / "victim.txt"
    victim.write_text("do not overwrite", encoding="utf-8")
    legacy_temp = target.with_suffix(target.suffix + ".tmp")
    try:
        legacy_temp.symlink_to(victim)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is unavailable on this platform")
    monkeypatch.setattr("peke.config.user_settings_path", lambda: target)
    save_user_settings({"safe": True}, merge=False)
    assert victim.read_text(encoding="utf-8") == "do not overwrite"
    assert '"safe": true' in target.read_text(encoding="utf-8")


def test_fetch_rejects_oversized_response(monkeypatch):
    import sys
    import types
    from unittest.mock import MagicMock

    import peke.fetch as fetch_module

    monkeypatch.setattr(fetch_module, "MAX_RESPONSE_BYTES", 4)
    response = MagicMock(status=200, headers={"content-type": "text/plain"}, body=b"12345")

    class FakeFetcher:
        def get(self, *args, **kwargs):
            return response

    fake = types.ModuleType("scrapling.fetchers")
    fake.Fetcher = FakeFetcher
    fake.StealthyFetcher = MagicMock()
    monkeypatch.setitem(sys.modules, "scrapling.fetchers", fake)
    from peke.fetch import FetchError, fetch
    from peke.profile import load_profile
    with pytest.raises(FetchError, match="safety limit"):
        fetch(load_profile({"url": "https://example.com?token=private"}), Settings(None))
