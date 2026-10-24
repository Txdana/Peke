"""Tests for the probe + schema subagents (network and AI mocked)."""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from peke.agents.probe_agent import ProbeAgent
from peke.agents.schema_agent import (
    SchemaAgent,
    field_types,
    find_items,
    infer_shape,
    pagination_hints,
)
from peke.config import Settings

DATA = {"meta": {"total": 2, "page": 1}, "data": {"results": [{"id": 1, "title": "a", "price": 1.5}, {"id": 2, "title": "b", "price": 2.0}]}}


def _res(payload):
    return SimpleNamespace(status=200, content_type="application/json", text="", json=payload)


def test_find_items_and_fields():
    path, items = find_items(DATA)
    assert path == "data.results" and len(items) == 2
    assert field_types(items) == {"id": "int", "title": "str", "price": "float"}
    assert pagination_hints(DATA) == ["page", "total"]
    assert infer_shape(DATA)["data"]["results"][1] == "len=2"


def test_schema_agent_uses_ai_but_survives_failure():
    ok = MagicMock()
    ok.complete_json.return_value = SimpleNamespace(parsed={"schema_name": "Product", "description": "x"}, raw_text="")
    assert SchemaAgent().analyze({"u": DATA}, ok).findings[0]["schema_name"] == "Product"
    bad = MagicMock()
    bad.complete_json.side_effect = RuntimeError("no model")
    assert SchemaAgent().analyze({"u": DATA}, bad).findings[0]["schema_name"] == "Listing"


def test_probe_agent_get_only_same_origin(monkeypatch):
    hints = [
        {"method": "GET", "path": "/api/items", "params": {"limit": "5"}},
        {"method": "POST", "path": "/api/delete"},
        {"method": "GET", "path": "/api/users/{id}"},
    ]
    s = Settings(model_path=None, request_delay_seconds=0.0)
    with patch("peke.agents.probe_agent.validate_url_security", side_effect=lambda u, _s: u), \
         patch("peke.agents.probe_agent.fetch", return_value=_res(DATA)) as fetched:
        out = ProbeAgent().analyze("https://example.test/", hints, s)
    assert fetched.call_count == 1
    assert out.probes[0]["path"] == "/api/items" and out.probes[0]["is_json"]
    assert "payloads" not in out.probes[0] and len(out.payloads) == 1


# ---- pipeline: lists, pagination, limits ----
from peke.fetch import FetchResult  # noqa: E402
from peke.pipeline import Pipeline, next_profile, select_path  # noqa: E402
from peke.profile import load_profile  # noqa: E402


def _fr(payload):
    return FetchResult("https://example.test/api", 200, "application/json", "", payload, 1.0)


def test_select_path_supports_list_indexes():
    assert select_path({"a": [{"b": 1}]}, "a.0.b") == 1
    assert select_path({"a": 1}, "a.b") is None


def test_pipeline_validates_every_item_and_paginates():
    pages = [_fr({"results": [{"title": "a"}, {"title": "b"}]}), _fr({"results": [{"title": "c"}]}), _fr({"results": []})]
    profile = load_profile({"url": "https://example.test/api", "params": {"page": 1}, "mode": "api",
                            "schema_name": "Article", "item_path": "results", "max_pages": 10})
    with patch("peke.pipeline.fetch", side_effect=pages) as fetched:
        result = Pipeline(settings=Settings(None, request_delay_seconds=0.0)).run(profile)
    assert [r.title for r in result.records] == ["a", "b", "c"]
    assert fetched.call_count == 3


def test_next_link_must_stay_same_origin():
    profile = load_profile({"url": "https://example.test/api"})
    assert next_profile(profile, {"next": "https://evil.test/x"}, set()) is None
    assert next_profile(profile, {"next": "/api?page=2"}, set()).url == "https://example.test/api?page=2"


def test_unlimited_settings_accepted():
    s = Settings(None, max_response_bytes=0, subagents_max_probes=0, subagents_max_scripts=0, request_delay_seconds=0.0)
    assert s.max_response_bytes == 0
