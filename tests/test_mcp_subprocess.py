"""Subprocess stdio test asserting stdout contains ONLY valid JSON-RPC protocol messages."""

import json
import shutil
import subprocess
import sys


def test_stdio_mode_stdout_is_clean_jsonrpc():
    launcher = shutil.which("peke") or sys.executable
    args = ["mcp", "serve"] if shutil.which("peke") else ["-m", "peke.cli", "mcp", "serve"]

    proc = subprocess.Popen(
        [launcher] + args,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    # Send MCP initialize request
    init_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0"},
        },
    }

    assert proc.stdin is not None
    assert proc.stdout is not None

    proc.stdin.write(json.dumps(init_request) + "\n")
    proc.stdin.flush()

    line = proc.stdout.readline()

    # Terminate process
    proc.terminate()
    proc.wait(timeout=2)

    assert line and line.strip(), "Expected response from peke mcp serve"
    # Verify line parses cleanly as JSON-RPC
    data = json.loads(line)
    assert data.get("jsonrpc") == "2.0"
    assert data.get("id") == 1
    assert "result" in data
    assert data["result"]["serverInfo"]["name"] == "peke"
