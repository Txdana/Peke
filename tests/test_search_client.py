"""Regression tests for the SearXNG API client and local configuration."""
import json
import math

import pytest

from peke.search import SearchError, SearxngClient
from peke.searxng_runtime import _write_settings


class FakeResponse:
    def __init__(self, payload: object):
        self.body = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, _limit: int = -1) -> bytes:
        return self.body


def test_status_requires_a_results_list(monkeypatch):
    client = SearxngClient("http://127.0.0.1:8888")
    monkeypatch.setattr("urllib.request.urlopen", lambda *_args, **_kwargs: FakeResponse({"ok": True}))

    status = client.status()

    assert status["available"] is False
    assert "results" in status["reason"]


def test_status_accepts_valid_empty_results(monkeypatch):
    client = SearxngClient("http://127.0.0.1:8888")
    monkeypatch.setattr("urllib.request.urlopen", lambda *_args, **_kwargs: FakeResponse({"results": []}))

    status = client.status()

    assert status["available"] is True


@pytest.mark.parametrize(
    "url",
    [
        "ftp://search.example",
        "https://user:password@search.example",
        "https://search.example:99999",
        "https://search.example?format=json",
        "https://search.example/#result",
        "https://search example",
    ],
)
def test_rejects_invalid_base_urls(url):
    with pytest.raises(SearchError):
        SearxngClient(url)


@pytest.mark.parametrize("timeout", [0, -1, math.inf, math.nan, "not-a-number", True])
def test_rejects_invalid_timeouts(timeout):
    with pytest.raises(SearchError, match="timeout"):
        SearxngClient("http://127.0.0.1:8888", timeout=timeout)


def test_search_validates_query_filter_and_pagination():
    client = SearxngClient("http://127.0.0.1:8888")
    with pytest.raises(SearchError, match="cannot be empty"):
        client.search("   ")
    with pytest.raises(SearchError, match="500 characters"):
        client.search("x" * 501)
    with pytest.raises(SearchError, match="time_range"):
        client.search("query", time_range="week")
    with pytest.raises(SearchError, match="positive integer"):
        client.search("query", pages=1.5)
    with pytest.raises(SearchError, match="non-negative integer"):
        client.search("query", max_results=-1)


def test_search_uses_moderate_safe_search_by_default(monkeypatch):
    client = SearxngClient("http://127.0.0.1:8888")
    calls: list[dict[str, str]] = []

    def fake_get(params):
        calls.append(params)
        return {"results": []}

    monkeypatch.setattr(client, "_get", fake_get)
    assert client.search("a safe query") == []
    assert calls[0]["safesearch"] == "1"


def test_extreme_but_finite_timeout_is_bounded():
    client = SearxngClient("http://127.0.0.1:8888", timeout=1e100)
    assert client.timeout == 120.0


def test_start_timeout_must_be_finite(monkeypatch):
    import peke.searxng_runtime as runtime

    with pytest.raises(runtime.SearXNGServiceError, match="positive finite"):
        runtime.start_local_server(startup_timeout=float("inf"))


def test_pagination_is_capped_and_malformed_result_urls_are_skipped(monkeypatch):
    client = SearxngClient("http://127.0.0.1:8888")
    calls: list[dict[str, str]] = []

    def fake_get(params):
        calls.append(params)
        return {
            "results": [
                {"url": "https://example.com/good?utm_source=unit-test#section", "title": "good", "content": "ok"},
                {"url": "https://[broken", "title": "malformed", "content": "discard"},
                {"url": "javascript:alert(1)", "title": "unsafe", "content": "discard"},
                {"url": "https://example.com/?" + "x=1&" * 1100, "title": "too many query fields"},
                {"url": "https://example.com/" + "x" * 9000, "title": "oversized url"},
            ]
        }

    monkeypatch.setattr(client, "_get", fake_get)
    results = client.search("query", pages=200)

    assert len(calls) == 10
    assert [call["pageno"] for call in calls] == [str(i) for i in range(1, 11)]
    assert len(results) == 1
    assert results[0].url == "https://example.com/good"


def test_local_settings_enable_json_and_keep_a_unique_secret(tmp_path, monkeypatch):
    monkeypatch.setattr("peke.searxng_runtime._config_dir", lambda: tmp_path / "config")

    first = _write_settings()
    text_one = first.read_text(encoding="utf-8")
    second = _write_settings()
    text_two = second.read_text(encoding="utf-8")

    assert first == second
    assert "    - json" in text_one
    assert "safe_search: 1" in text_one
    assert "use_default_settings: true" in text_one
    assert "secret_key:" in text_one
    assert text_one != text_two
    if __import__("os").name != "nt":
        assert first.stat().st_mode & 0o777 == 0o600
        assert first.parent.stat().st_mode & 0o777 == 0o700


def test_local_service_settings_bind_loopback_and_enable_json(tmp_path, monkeypatch):
    import os

    import peke.searxng_runtime as runtime

    monkeypatch.setattr(runtime, "_config_dir", lambda: tmp_path / "config")
    path = runtime._write_settings()
    text = path.read_text(encoding="utf-8")
    assert 'bind_address: "127.0.0.1"' in text
    assert "port: 8888" in text
    assert "    - json" in text
    assert "safe_search: 1" in text
    assert "secret_key:" in text
    if os.name != "nt":
        assert path.stat().st_mode & 0o777 == 0o600
        assert path.parent.stat().st_mode & 0o777 == 0o700


def test_start_local_launches_bundled_module_without_docker(tmp_path, monkeypatch):
    import peke.searxng_runtime as runtime

    class FakeProcess:
        def __init__(self, args, **kwargs):
            self.args = args
            self.kwargs = kwargs
            self.returncode = None
        def poll(self):
            return self.returncode
        def terminate(self):
            self.returncode = 0
        def wait(self, timeout=None):
            return self.returncode
        def kill(self):
            self.returncode = -9

    monkeypatch.setattr(runtime, "_config_dir", lambda: tmp_path / "config")
    monkeypatch.setenv("SEARXNG_BIND_ADDRESS", "0.0.0.0")
    monkeypatch.setenv("SEARXNG_PORT", "80")
    monkeypatch.setenv("SEARXNG_PUBLIC_INSTANCE", "true")
    monkeypatch.setenv("SEARXNG_SECRET", "external-secret-must-not-win")
    ready_calls = iter([
        {"available": False, "reason": "not started"},
        {"available": True, "url": runtime.BASE_URL, "reason": "ok"},
    ])
    monkeypatch.setattr(runtime, "_is_ready", lambda timeout=1.5: next(ready_calls))
    monkeypatch.setattr(runtime, "_SERVER_PROCESS", None)
    monkeypatch.setattr(runtime, "_SERVER_LOG", None)
    monkeypatch.setattr(runtime, "_port_in_use", lambda *a, **k: False)
    monkeypatch.setattr(runtime.subprocess, "Popen", FakeProcess)
    result = runtime.start_local_server(startup_timeout=5)
    assert result["status"]["available"] is True
    assert result["managed_by_peke"] is True
    process = runtime._SERVER_PROCESS
    assert process.args[-2:] == ["-m", "searx.webapp"]
    env = process.kwargs["env"]
    assert env["SEARXNG_SETTINGS_PATH"] == str(tmp_path / "config")
    assert env["SEARXNG_BIND_ADDRESS"] == "127.0.0.1"
    assert env["SEARXNG_PORT"] == "8888"
    assert env["SEARXNG_PUBLIC_INSTANCE"] == "false"
    assert "SEARXNG_SECRET" not in env
    assert "docker" not in " ".join(process.args).lower()
    stopped = runtime.stop_local_server()
    assert stopped["stopped"] is True


def test_stop_does_not_kill_a_service_not_started_by_this_session(monkeypatch):
    import peke.searxng_runtime as runtime
    monkeypatch.setattr(runtime, "_SERVER_PROCESS", None)
    monkeypatch.setattr(runtime, "_is_ready", lambda timeout=1.5: {"available": True})
    result = runtime.stop_local_server()
    assert result["stopped"] is False
    assert "did not launch it" in result["message"]


def test_local_status_reports_bundled_service_without_docker(monkeypatch):
    import peke.searxng_runtime as runtime
    monkeypatch.setattr(runtime, "_SERVER_PROCESS", None)
    monkeypatch.setattr(runtime, "_is_ready", lambda timeout=1.5: {"available": True, "url": runtime.BASE_URL})
    status = runtime.local_server_status()
    assert status["bundled"] is True
    assert status["installed"] is True
    assert status["running"] is True
    assert status["managed_by_peke"] is False


def test_search_rejects_non_object_payload(monkeypatch):
    client = SearxngClient("http://127.0.0.1:8888")
    monkeypatch.setattr("urllib.request.urlopen", lambda *_args, **_kwargs: FakeResponse([{"results": []}]))

    with pytest.raises(SearchError, match="JSON object"):
        client._get({"q": "query", "format": "json"})


def test_local_settings_do_not_follow_a_predictable_temp_symlink(tmp_path, monkeypatch):
    import os

    import peke.searxng_runtime as runtime

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    victim = tmp_path / "victim.txt"
    victim.write_text("do not overwrite", encoding="utf-8")
    legacy_temp = config_dir / "settings.yml.tmp"
    try:
        legacy_temp.symlink_to(victim)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is unavailable on this platform")

    monkeypatch.setattr(runtime, "_config_dir", lambda: config_dir)
    settings_path = runtime._write_settings()

    assert victim.read_text(encoding="utf-8") == "do not overwrite"
    assert settings_path.is_file()
    assert os.path.islink(legacy_temp)


