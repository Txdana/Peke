"""Unit tests for Peke MCP resources and prompts."""

import json

import pytest

from peke.mcp.runs import RunStore
from peke.mcp.server import build_server


@pytest.mark.anyio
async def test_resources_list_and_read(tmp_path, monkeypatch):
    monkeypatch.setenv("PEKE_HOME", str(tmp_path))
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

    # Create a test run
    store = RunStore(tool_name="peke_fetch")
    store.save_content("Sample Page Text", content_type="text/plain")
    store.finish()

    server = build_server()

    # Read peke://runs
    runs_res = await server.read_resource("peke://runs")
    assert len(runs_res) > 0
    runs_json = json.loads(runs_res[0].content if hasattr(runs_res[0], "content") else runs_res[0].text)
    assert len(runs_json) == 1
    assert runs_json[0]["run_id"] == store.run_id

    # Read peke://runs/{run_id}/content
    part_res = await server.read_resource(f"peke://runs/{store.run_id}/content")
    part_json = json.loads(part_res[0].content if hasattr(part_res[0], "content") else part_res[0].text)
    assert part_json["data"] == "Sample Page Text"

    # Read peke://schemas/Article
    schema_res = await server.read_resource("peke://schemas/Article")
    schema_json = json.loads(schema_res[0].content if hasattr(schema_res[0], "content") else schema_res[0].text)
    assert "properties" in schema_json


@pytest.mark.anyio
async def test_prompts_templates():
    server = build_server()

    # List prompts
    prompts = await server.list_prompts()
    pnames = [p.name for p in prompts]
    assert "peke_reverse_engineer" in pnames
    assert "peke_extract_page" in pnames

    # Get prompt peke_reverse_engineer
    p1 = await server.get_prompt("peke_reverse_engineer", {"url": "https://example.com/shop"})
    p1_str = str(p1)
    assert "https://example.com/shop" in p1_str
    assert len(p1_str.split()) < 200

    # Get prompt peke_extract_page
    p2 = await server.get_prompt("peke_extract_page", {"url": "https://example.com/item", "schema": "Product"})
    p2_str = str(p2)
    assert "https://example.com/item" in p2_str
    assert "Product" in p2_str
    assert len(p2_str.split()) < 200
