"""Tests for Peke MCP server core (runs, activity, model lock, settings)."""

import json

import pytest
from filelock import Timeout

from peke.config import ConfigError, Settings
from peke.mcp.activity import log_activity, read_activity_log, sanitize_value
from peke.mcp.runs import RunStore, get_run_part, list_runs, prune_runs
from peke.mcp.server import build_server, get_model_lock


def test_mcp_config_settings_validation(tmp_path, monkeypatch):
    monkeypatch.setenv("PEKE_HOME", str(tmp_path))
    s = Settings(
        model_path=None,
        mcp_read_only=True,
        mcp_robots_policy="respect",
        mcp_max_inline_chars=5000,
        mcp_max_fetch_bytes=1_000_000,
        mcp_http_port=9000,
    )
    assert s.mcp_read_only is True
    assert s.mcp_robots_policy == "respect"
    assert s.mcp_max_inline_chars == 5000
    assert s.mcp_http_port == 9000

    with pytest.raises(ConfigError):
        Settings(model_path=None, mcp_robots_policy="invalid")

    with pytest.raises(ConfigError):
        Settings(model_path=None, mcp_http_port=80)


def test_run_store_lifecycle_and_parts(tmp_path, monkeypatch):
    monkeypatch.setenv("PEKE_HOME", str(tmp_path))

    store = RunStore(tool_name="peke_fetch")
    run_id = store.run_id

    content_filename = store.save_content("Hello World Page Content", content_type="text/plain")
    assert content_filename == "content.txt"

    records = [{"title": "Item 1"}]
    store.save_records(records)

    endpoints = [{"method": "GET", "path": "/api/items"}]
    store.save_endpoints(endpoints)

    store.add_event({"tag": "TEST", "message": "Event recorded"})
    store.finish(status="ok")

    # Read back parts
    meta, truncated, next_off = get_run_part(run_id, part="meta")
    assert meta["status"] == "ok"
    assert meta["tool"] == "peke_fetch"
    assert truncated is False

    text, truncated, next_off = get_run_part(run_id, part="content", limit=10)
    assert text == "Hello Worl"
    assert truncated is True
    assert next_off == 10

    recs, _, _ = get_run_part(run_id, part="records")
    assert recs == records

    eps, _, _ = get_run_part(run_id, part="endpoints")
    assert eps == endpoints

    evs, _, _ = get_run_part(run_id, part="events")
    assert len(evs) == 1
    assert evs[0]["tag"] == "TEST"

    runs = list_runs()
    assert len(runs) == 1
    assert runs[0]["run_id"] == run_id


def test_run_store_pruning(tmp_path, monkeypatch):
    monkeypatch.setenv("PEKE_HOME", str(tmp_path))

    for i in range(10):
        store = RunStore(run_id=f"run_20260101_00000{i}_abcd", tool_name="test")
        store.save_content("x" * 1000)
        store.finish()

    assert len(list_runs()) == 10
    pruned = prune_runs(max_runs=5)
    assert pruned == 5
    assert len(list_runs()) == 5


def test_activity_log_redaction_and_reading(tmp_path, monkeypatch):
    monkeypatch.setenv("PEKE_HOME", str(tmp_path))

    log_activity(
        client_info="Claude Code/1.0",
        tool="peke_fetch",
        target="https://user:password@secret.example.com/api?token=123",
        duration_ms=150,
        status="ok",
        run_id="run_123",
    )

    entries = read_activity_log()
    assert len(entries) == 1
    entry = entries[0]
    assert entry["client"] == "Claude Code/1.0"
    assert entry["target_host"] == "secret.example.com"
    assert "password" not in json.dumps(entry)
    assert "token" not in json.dumps(entry)

    # Test sanitize_value
    assert sanitize_value("authorization", "Bearer xyz") == "***"
    assert sanitize_value("Cookie", "session=abc") == "***"


def test_model_lock_contention(tmp_path, monkeypatch):
    monkeypatch.setenv("PEKE_HOME", str(tmp_path))

    lock1 = get_model_lock()
    lock2 = get_model_lock()

    with lock1:
        with pytest.raises(Timeout):
            lock2.acquire(timeout=0.05)


def test_build_server_returns_configured_instance():
    server = build_server()
    assert server.name == "peke"
    assert server.version == "0.2.0"
    assert "SAFETY NOTICE" in server.instructions
