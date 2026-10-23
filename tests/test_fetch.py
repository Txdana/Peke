"""Tests for Scrapling fetching wrapper."""

from unittest.mock import MagicMock, patch

import pytest

from peke.fetch import FetchError, fetch_target


@patch("peke.fetch.Fetcher.get")
def test_fetch_target_success_json(mock_get):
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.headers = {"content-type": "application/json"}
    mock_response.body = b'{"status": "ok", "count": 5}'
    mock_response.json.return_value = {"status": "ok", "count": 5}
    mock_get.return_value = mock_response

    result = fetch_target("https://api.example.com/data")
    assert result.status_code == 200
    assert result.is_json is True
    assert result.json_data == {"status": "ok", "count": 5}
    assert result.fetcher_used == "Fetcher"


@patch("peke.fetch.StealthyFetcher")
def test_fetch_target_stealthy_fetcher(mock_stealthy_cls):
    mock_stealthy = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.headers = {"content-type": "text/html"}
    mock_response.body = b"<html><body>Protected content</body></html>"
    mock_stealthy.fetch.return_value = mock_response
    mock_stealthy_cls.return_value = mock_stealthy

    result = fetch_target("https://example.com/protected", fetcher_type="StealthyFetcher")
    assert result.status_code == 200
    assert result.fetcher_used == "StealthyFetcher"
    assert result.cloudflare_bypassed is True
    assert "Protected content" in result.text


@patch("peke.fetch.Fetcher.get")
def test_fetch_target_failure_raises_fetch_error(mock_get):
    mock_get.side_effect = Exception("Connection timed out")
    with pytest.raises(FetchError) as exc_info:
        fetch_target("https://failing.example.com")
    assert "Fetch failed" in str(exc_info.value)
