"""Tests for REA findings discovery integration."""

from unittest.mock import MagicMock, patch

from peke.discover import (
    discover_target_profile,
    is_rea_available,
    parse_rea_json_output,
    read_rea_findings,
    run_rea,
)


def test_read_rea_findings():
    findings = {
        "url": "https://example.com/api/items",
        "fetcher": "StealthyFetcher",
        "headers": {"Authorization": "Bearer token123"},
        "endpoints": ["/api/v1/items", "/api/v1/details"],
        "schema_name": "Listing",
    }
    profile = read_rea_findings(findings)
    assert profile.url == "https://example.com/api/items"
    assert profile.fetcher == "StealthyFetcher"
    assert profile.headers["Authorization"] == "Bearer token123"
    assert len(profile.endpoint_hints) == 2
    assert profile.schema_name == "Listing"


def test_parse_rea_json_output_fixture():
    fixture_json = """{
        "target_url": "https://example.com/shop",
        "endpoints": [
            {"method": "GET", "path": "/api/v1/products/list", "size": "12.4KB", "hidden": false},
            {"method": "POST", "path": "/api/v1/cart/checkout", "size": "2.1KB", "hidden": true}
        ]
    }"""
    hints = parse_rea_json_output(fixture_json)
    assert len(hints) == 2
    assert hints[0].path == "/api/v1/products/list"
    assert hints[0].hidden is False
    assert hints[1].method == "POST"
    assert hints[1].hidden is True


@patch("peke.discover.subprocess.run")
def test_run_rea_subprocess_success(mock_run):
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stdout = '{"endpoints": [{"method": "GET", "path": "/api/items"}]}'
    mock_run.return_value = mock_proc

    hints = run_rea("https://example.com")
    assert len(hints) == 1
    assert hints[0].path == "/api/items"


@patch("peke.discover.subprocess.run")
def test_run_rea_subprocess_missing_executable_graceful_fallback(mock_run):
    mock_run.side_effect = FileNotFoundError("Executable not found")
    events = []
    def on_event(level, msg):
        events.append((level, msg))

    hints = run_rea("https://example.com", on_event=on_event)
    assert hints == []
    assert len(events) == 1
    assert events[0][0] == "WARNING"


@patch("peke.discover.httpx.get")
def test_is_rea_available_true(mock_get):
    mock_res = MagicMock()
    mock_res.status_code = 200
    mock_get.return_value = mock_res
    assert is_rea_available("http://localhost:8000") is True


@patch("peke.discover.httpx.get")
def test_is_rea_available_false_on_connection_error(mock_get):
    mock_get.side_effect = Exception("Connection refused")
    assert is_rea_available("http://localhost:8000") is False


def test_discover_target_profile_fallback():
    profile = discover_target_profile("https://example.com/target", rea_url=None)
    assert profile.url == "https://example.com/target"
    assert profile.fetcher == "Fetcher"
    assert profile.name == "Hand-written Target Profile"
