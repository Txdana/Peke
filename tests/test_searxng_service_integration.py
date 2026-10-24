"""Lifecycle regression tests for the bundled SearXNG controller.

Tests marked ``real_service`` launch the actual bundled ``searx.webapp`` process (no mocks) with an
isolated config directory. They need the pinned SearXNG dependencies and a free 127.0.0.1:8888.
They do NOT need internet: they verify the local service, not upstream search engines.
"""
import os
import socket
import subprocess
import sys
import threading
import time

import pytest

import peke.searxng_runtime as runtime
from peke.search import SearxngClient


def _port_free() -> bool:
    return not runtime._port_in_use()


def _have_searx_deps() -> bool:
    import importlib.util

    return all(importlib.util.find_spec(n) for n in ("flask", "flask_babel", "msgspec", "valkey", "typer"))


real_service = pytest.mark.skipif(
    not (_have_searx_deps() and _port_free()),
    reason="needs bundled SearXNG dependencies and a free 127.0.0.1:8888",
)


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime, "_config_dir", lambda: tmp_path / "searxng")
    monkeypatch.setattr(runtime, "_SERVER_PROCESS", None)
    monkeypatch.setattr(runtime, "_SERVER_LOG", None)
    yield tmp_path
    try:
        runtime.stop_local_server()
    except Exception:
        pass
    # last-resort cleanup so a failing test never leaks a listener
    state = runtime._read_state()
    if state:
        try:
            os.kill(state["pid"], 9)
        except OSError:
            pass


def test_foreign_listener_on_port_gets_clear_error_and_is_left_alone(isolated):
    if not _port_free():
        pytest.skip("127.0.0.1:8888 already in use")
    srv = socket.socket()
    srv.bind(("127.0.0.1", 8888))
    srv.listen(5)
    try:
        with pytest.raises(runtime.SearXNGServiceError, match="already in use"):
            runtime.start_local_server(startup_timeout=5)
        assert runtime._SERVER_PROCESS is None          # nothing spawned
        assert srv.fileno() != -1                        # unrelated listener untouched
        result = runtime.stop_local_server()
        assert result["stopped"] is False
    finally:
        srv.close()


def test_stop_never_signals_a_process_whose_token_does_not_match(isolated, monkeypatch):
    runtime._config_dir().mkdir(parents=True)
    runtime._write_state(os.getpid(), "deadbeefdeadbeef")   # pid of the test runner itself
    monkeypatch.setattr(runtime, "_answering_token", lambda: "someoneelse")
    monkeypatch.setattr(runtime, "_is_ready", lambda timeout=1.5: {"available": False})
    monkeypatch.setattr(runtime.os, "kill", lambda *a: pytest.fail("must not signal an unverified pid"))
    result = runtime.stop_local_server()
    assert result["stopped"] is False
    assert runtime._read_state() is None                     # stale record discarded


def test_log_tail_only_shows_the_current_launch(isolated, monkeypatch):
    cfg = runtime._config_dir()
    cfg.mkdir(parents=True)
    log = cfg / "searxng.log"
    log.write_bytes(b"OLD RUN: boom\n")
    monkeypatch.setattr(runtime, "_LOG_START_OFFSET", log.stat().st_size)
    with log.open("ab") as fh:
        fh.write(b"NEW RUN: real cause\n")
    tail = runtime._tail_log()
    assert "real cause" in tail and "OLD RUN" not in tail


def test_address_in_use_in_log_becomes_a_plain_message(isolated, monkeypatch):
    cfg = runtime._config_dir()
    cfg.mkdir(parents=True)
    (cfg / "searxng.log").write_bytes(b"Traceback...\nAddress already in use\n")
    monkeypatch.setattr(runtime, "_LOG_START_OFFSET", 0)
    assert "already in use" in runtime._tail_log() and "Traceback" not in runtime._tail_log()


def test_client_records_unresponsive_engines_separately_from_empty_results(monkeypatch):
    client = SearxngClient("http://127.0.0.1:8888")
    payload = {"results": [], "unresponsive_engines": [["brave", "Suspended: HTTP connection error"], "junk"]}
    monkeypatch.setattr(client, "_get", lambda params: payload)
    assert client.search("anything") == []
    assert client.last_unresponsive == [("brave", "Suspended: HTTP connection error")]
    status = client.status()
    assert status["available"] is True and status["engines_unresponsive"] == 1


@real_service
def test_real_service_binds_loopback_only_and_serves_json_api(isolated):
    result = runtime.start_local_server(startup_timeout=90)
    assert result["managed_by_peke"] is True
    hits = []
    for _fam, f in (("v4", "/proc/net/tcp"), ("v6", "/proc/net/tcp6")):
        if os.path.exists(f):
            for line in open(f).read().splitlines()[1:]:
                cols = line.split()
                if cols[3] == "0A" and int(cols[1].split(":")[1], 16) == 8888:
                    hits.append(cols[1].split(":")[0])
    if hits:  # /proc only exists on Linux; Windows is covered by the settings test
        assert hits == ["0100007F"]
    data = SearxngClient(runtime.BASE_URL, timeout=60)._get({"q": "peke", "format": "json"})
    assert isinstance(data["results"], list)
    settings_text = runtime._settings_file().read_text(encoding="utf-8")
    secret = settings_text.split('secret_key: "')[1].split('"')[0]
    assert len(secret) == 64
    log_text = (runtime._config_dir() / "searxng.log").read_text(encoding="utf-8", errors="replace")
    assert secret not in log_text                          # the generated secret must never be logged


@real_service
def test_real_concurrent_starts_leave_exactly_one_owned_process(isolated):
    outcomes = []

    def go():
        try:
            outcomes.append(runtime.start_local_server(startup_timeout=90)["already_running"])
        except Exception as exc:  # pragma: no cover - reported by assertion below
            outcomes.append(repr(exc))

    threads = [threading.Thread(target=go) for _ in range(4)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert outcomes.count(False) == 1, outcomes          # exactly one real launch
    assert all(o in (True, False) for o in outcomes)
    stopped = runtime.stop_local_server()
    assert stopped["stopped"] is True
    time.sleep(1)
    assert runtime._port_in_use() is False


@real_service
def test_real_orphan_after_force_kill_is_adopted_and_stopped_by_next_session(isolated, tmp_path):
    cfg = runtime._config_dir()
    code = (
        "import sys, time\n"
        "import peke.searxng_runtime as r\n"
        f"from pathlib import Path\nr._config_dir = lambda: Path({str(cfg)!r})\n"
        "r.start_local_server(startup_timeout=90)\nprint('up', flush=True)\ntime.sleep(300)\n"
    )
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(sys.path))
    first = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True, env=env)
    assert first.stdout.readline().strip() == "up"
    first.kill()
    first.wait()
    time.sleep(1)
    assert runtime._port_in_use() is True                      # orphan survived the kill (known limitation)
    status = runtime.local_server_status()
    assert status["running"] is True and status["managed_by_peke"] is True   # adopted via token
    result = runtime.stop_local_server()
    assert result["stopped"] is True
    time.sleep(1)
    assert runtime._port_in_use() is False
    assert runtime._read_state() is None


def test_child_environment_is_utf8_and_uses_private_temp(isolated, monkeypatch):
    """Windows hardening: legacy console code page and shared temp dir must not leak to the child."""
    captured = {}

    class FakePopen:
        pid = 4242

        def __init__(self, args, **kwargs):
            captured["env"] = kwargs["env"]
            captured["args"] = args

        def poll(self):
            return None

        def terminate(self):
            pass

        def wait(self, timeout=None):
            return 0

    monkeypatch.setattr(runtime.subprocess, "Popen", FakePopen)
    monkeypatch.setattr(runtime, "_port_in_use", lambda *a, **k: False)
    ready = iter([{"available": False, "reason": "x"}, {"available": True, "url": runtime.BASE_URL}])
    monkeypatch.setattr(runtime, "_is_ready", lambda timeout=1.5: next(ready))
    monkeypatch.setattr(runtime.atexit, "register", lambda *a, **k: None)
    runtime.start_local_server(startup_timeout=5)
    env = captured["env"]
    private = str(runtime._config_dir() / "tmp")
    assert env["PYTHONUTF8"] == "1" and env["PYTHONIOENCODING"] == "utf-8"
    assert env["TEMP"] == env["TMP"] == env["TMPDIR"] == private
    assert os.path.isdir(private)
    assert captured["args"][1:] == ["-m", "searx.webapp"]          # argument list, never a shell string


def test_stop_adopted_handles_windows_style_oserror_for_missing_pid(isolated, monkeypatch):
    """Windows raises a plain OSError (not ProcessLookupError) when the pid no longer exists."""
    runtime._config_dir().mkdir(parents=True)
    runtime._write_state(999999, "tok")
    answers = iter(["tok", None])      # verified once, then gone
    monkeypatch.setattr(runtime, "_answering_token", lambda: next(answers, None))

    def fake_kill(pid, sig):
        raise OSError(22, "The parameter is incorrect")

    monkeypatch.setattr(runtime.os, "kill", fake_kill)
    result = runtime.stop_local_server()
    assert result["already_stopped"] is True and result["stopped"] is False
    assert runtime._read_state() is None


def test_log_rotation_failure_does_not_block_startup(isolated, monkeypatch):
    """Windows refuses to rename a file held open by another process; truncate instead."""
    cfg = runtime._config_dir()
    cfg.mkdir(parents=True)
    log = cfg / "searxng.log"
    log.write_bytes(b"x" * (5 * 1024 * 1024 + 10))
    monkeypatch.setattr(runtime.os, "replace", lambda *a: (_ for _ in ()).throw(PermissionError("in use"))
                        if str(a[0]).endswith("searxng.log") else __import__("os").rename(*a))

    class FakePopen:
        pid = 1
        def __init__(self, *a, **k): pass
        def poll(self): return None
        def terminate(self): pass
        def wait(self, timeout=None): return 0

    monkeypatch.setattr(runtime.subprocess, "Popen", FakePopen)
    monkeypatch.setattr(runtime, "_port_in_use", lambda *a, **k: False)
    ready = iter([{"available": False, "reason": "x"}, {"available": True, "url": runtime.BASE_URL}])
    monkeypatch.setattr(runtime, "_is_ready", lambda timeout=1.5: next(ready))
    monkeypatch.setattr(runtime.atexit, "register", lambda *a, **k: None)
    runtime.start_local_server(startup_timeout=5)
    assert log.stat().st_size < 1024 * 1024
