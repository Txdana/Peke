"""Unit tests for the 11 Peke MCP tools (peke_*)."""

import json

import pytest

from peke.mcp.server import build_server


@pytest.mark.anyio
async def test_tools_registered_and_metadata_valid():
    server = build_server()
    # Fetch registered tools
    tools = await server.list_tools()
    assert len(tools) == 11

    tool_names = [t.name for t in tools]
    assert "peke_doctor" in tool_names
    assert "peke_fetch" in tool_names
    assert "peke_discover_endpoints" in tool_names
    assert "peke_probe_endpoint" in tool_names
    assert "peke_extract" in tool_names
    assert "peke_run_profile" in tool_names
    assert "peke_list_profiles" in tool_names
    assert "peke_get_profile" in tool_names
    assert "peke_save_profile" in tool_names
    assert "peke_schemas" in tool_names
    assert "peke_get_run" in tool_names

    for t in tools:
        assert len(t.description) <= 280, f"Description for {t.name} exceeds 280 chars: {len(t.description)}"


@pytest.mark.anyio
async def test_peke_doctor_tool_call(tmp_path, monkeypatch):
    monkeypatch.setenv("PEKE_HOME", str(tmp_path))
    server = build_server()

    res = await server.call_tool("peke_doctor", {})
    assert res.is_error is False
    content_text = res.content[0].text
    payload = json.loads(content_text)
    assert payload["ok"] is True
    assert payload["data"]["version"] == "0.2.0"
    assert "tools_count" in payload["data"]


@pytest.mark.anyio
async def test_peke_schemas_tool_call(tmp_path, monkeypatch):
    monkeypatch.setenv("PEKE_HOME", str(tmp_path))
    server = build_server()

    # List schemas
    res = await server.call_tool("peke_schemas", {})
    payload = json.loads(res.content[0].text)
    assert payload["ok"] is True
    assert "Article" in payload["data"]["schemas"]

    # Get Article schema
    res_art = await server.call_tool("peke_schemas", {"name": "Article"})
    payload_art = json.loads(res_art.content[0].text)
    assert payload_art["ok"] is True
    assert payload_art["data"]["name"] == "Article"
    assert "properties" in payload_art["data"]["schema"]


@pytest.mark.anyio
async def test_peke_probe_endpoint_rejects_non_get(tmp_path, monkeypatch):
    monkeypatch.setenv("PEKE_HOME", str(tmp_path))
    server = build_server()

    res = await server.call_tool("peke_probe_endpoint", {"url": "https://example.com", "method": "POST"})
    payload = json.loads(res.content[0].text)
    assert payload["ok"] is False
    assert "rejected" in payload["error"].lower() or "only get" in payload["error"].lower()


@pytest.mark.anyio
async def test_peke_save_profile_validation_and_overwrite_refusal(tmp_path, monkeypatch):
    monkeypatch.setenv("PEKE_HOME", str(tmp_path))
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    server = build_server()

    profile_data = {
        "name": "test_profile",
        "url": "https://example.com/items",
        "schema_name": "Article",
    }

    # Save initial profile
    res = await server.call_tool("peke_save_profile", {"name": "test_profile", "profile": profile_data})
    payload = json.loads(res.content[0].text)
    assert payload["ok"] is True

    # Attempt overwrite
    res2 = await server.call_tool("peke_save_profile", {"name": "test_profile", "profile": profile_data})
    payload2 = json.loads(res2.content[0].text)
    assert payload2["ok"] is False
    assert "already exists" in payload2["error"] or "refused" in payload2["error"]

    # Invalid name regex
    res3 = await server.call_tool("peke_save_profile", {"name": "Invalid Name!", "profile": profile_data})
    payload3 = json.loads(res3.content[0].text)
    assert payload3["ok"] is False


@pytest.mark.anyio
async def test_read_only_mode_filtering(tmp_path, monkeypatch):
    monkeypatch.setenv("PEKE_HOME", str(tmp_path))
    monkeypatch.setenv("MCP_READ_ONLY", "true")

    server = build_server()

    # Read-only tool works
    res_doc = await server.call_tool("peke_doctor", {})
    assert json.loads(res_doc.content[0].text)["ok"] is True

    # Non-read-only tool is blocked
    res_save = await server.call_tool(
        "peke_save_profile",
        {"name": "test_prof", "profile": {"name": "test_prof", "url": "https://example.com", "schema_name": "Article"}},
    )
    payload_save = json.loads(res_save.content[0].text)
    assert payload_save["ok"] is False
    assert "disabled in read-only mode" in payload_save["error"]
