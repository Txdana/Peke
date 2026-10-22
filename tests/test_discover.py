"""Tests for REA findings discovery integration."""

from unittest.mock import MagicMock, patch

from peke.discover import discover_target_profile, is_rea_available, read_rea_findings


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
    # When REA is not active or available, should return default TargetProfile
    profile = discover_target_profile("https://example.com/target", rea_url=None)
    assert profile.url == "https://example.com/target"
    assert profile.fetcher == "Fetcher"
    assert profile.name == "Hand-written Target Profile"
