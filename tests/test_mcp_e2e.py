"""End-to-end integration test running discover -> probe -> fetch -> extract via MCP Client."""

import json
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler

import pytest

from peke.mcp.server import build_server


class DemoAppHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/items":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"title": "Demo Product", "price": "$19.99"}')
        else:
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<html><body><h1>Shop Demo</h1><script src='/api/items'></script></body></html>")

    def log_message(self, format, *args):
        pass


@pytest.fixture
def demo_server():
    server = HTTPServer(("127.0.0.1", 0), DemoAppHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


@pytest.mark.anyio
async def test_mcp_end_to_end_pipeline(demo_server, tmp_path, monkeypatch):
    monkeypatch.setenv("PEKE_HOME", str(tmp_path))
    monkeypatch.setenv("MCP_ALLOW_PRIVATE_HOSTS", "true")

    server = build_server()

    # 1. Doctor check
    doc_res = await server.call_tool("peke_doctor", {})
    doc_payload = json.loads(doc_res.content[0].text)
    assert doc_payload["ok"] is True

    # 2. Discover endpoints
    disc_res = await server.call_tool("peke_discover_endpoints", {"url": f"{demo_server}/"})
    disc_payload = json.loads(disc_res.content[0].text)
    assert disc_payload["ok"] is True

    # 3. Probe endpoint
    api_url = f"{demo_server}/api/items"
    probe_res = await server.call_tool("peke_probe_endpoint", {"url": api_url, "method": "GET"})
    probe_payload = json.loads(probe_res.content[0].text)
    assert probe_payload["ok"] is True
    assert probe_payload["data"]["status"] == 200
    assert probe_payload["data"]["json_shape"]["type"] == "object"

    # 4. Fetch page
    fetch_res = await server.call_tool("peke_fetch", {"url": api_url, "fetcher": "basic"})
    fetch_payload = json.loads(fetch_res.content[0].text)
    assert fetch_payload["ok"] is True
    run_id = fetch_payload["run_id"]

    # 5. Extract schema-constrained JSON
    ext_res = await server.call_tool("peke_extract", {"schema": "Product", "run_id": run_id})
    ext_payload = json.loads(ext_res.content[0].text)
    assert ext_payload["ok"] is True
    assert ext_payload["data"]["records"][0]["title"] == "Demo Product"

    # 6. Retrieve stored run artifact
    run_res = await server.call_tool("peke_get_run", {"run_id": run_id, "part": "content"})
    run_payload = json.loads(run_res.content[0].text)
    assert run_payload["ok"] is True
    assert "Demo Product" in run_payload["data"]["content"]
