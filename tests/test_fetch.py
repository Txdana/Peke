from unittest.mock import MagicMock
import sys
import types
import pytest
from peke.config import Settings
from peke.fetch import FetchError, fetch
from peke.profile import load_profile


def test_basic_fetch_json(monkeypatch):
    response = MagicMock(status=200, headers={"content-type": "application/json"}, body=b'{"title":"x"}')
    class FakeFetcher:
        def get(self, *args, **kwargs):
            return response
    fake = types.ModuleType("scrapling.fetchers")
    fake.Fetcher = FakeFetcher
    fake.StealthyFetcher = MagicMock()
    monkeypatch.setitem(sys.modules, "scrapling.fetchers", fake)
    result = fetch(load_profile({"url": "https://example.com", "mode": "api"}), Settings(None))
    assert result.json == {"title": "x"} and result.status == 200


def test_empty_body_fails(monkeypatch):
    response = MagicMock(status=200, headers={}, body=b'')
    class FakeFetcher:
        def get(self, *args, **kwargs):
            return response
    fake = types.ModuleType("scrapling.fetchers")
    fake.Fetcher = FakeFetcher
    fake.StealthyFetcher = MagicMock()
    monkeypatch.setitem(sys.modules, "scrapling.fetchers", fake)
    with pytest.raises(FetchError, match="Empty"):
        fetch(load_profile({"url": "https://example.com"}), Settings(None))
