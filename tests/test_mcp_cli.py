"""Tests for Peke MCP CLI subcommands and agent registrars."""

import json

from typer.testing import CliRunner

from peke.cli import app
from peke.mcp.clients.registrars import CodexRegistrar, JsonMcpRegistrar

runner = CliRunner()


def test_mcp_cli_tools_command():
    res = runner.invoke(app, ["mcp", "tools"])
    assert res.exit_code == 0
    assert "peke_doctor" in res.stdout
    assert "peke_fetch" in res.stdout


def test_mcp_cli_token_command(tmp_path, monkeypatch):
    monkeypatch.setenv("PEKE_HOME", str(tmp_path))

    res = runner.invoke(app, ["mcp", "token"])
    assert res.exit_code == 0
    token1 = res.stdout.strip().split()[-1]
    assert len(token1) >= 32

    res_rot = runner.invoke(app, ["mcp", "token", "--rotate"])
    assert res_rot.exit_code == 0
    token2 = res_rot.stdout.strip().split()[-1]
    assert token1 != token2


def test_mcp_cli_print_config_command():
    res = runner.invoke(app, ["mcp", "print-config", "--client", "cursor"])
    assert res.exit_code == 0
    assert "mcpServers" in res.stdout
    assert "peke" in res.stdout


def test_mcp_cli_install_and_uninstall_json_client(tmp_path, monkeypatch):
    monkeypatch.setenv("PEKE_HOME", str(tmp_path))
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

    # Dry run install
    res_dry = runner.invoke(app, ["mcp", "install", "--client", "cursor", "--dry-run"])
    assert res_dry.exit_code == 0
    assert "Cursor" in res_dry.stdout

    # Real install with --yes
    res_inst = runner.invoke(app, ["mcp", "install", "--client", "cursor", "--yes"])
    assert res_inst.exit_code == 0

    reg = JsonMcpRegistrar("cursor", "Cursor", ".cursor/mcp.json")
    assert reg.is_registered() is True

    cfg_file = tmp_path / ".cursor" / "mcp.json"
    assert cfg_file.is_file()
    cfg_data = json.loads(cfg_file.read_text(encoding="utf-8"))
    assert "peke" in cfg_data["mcpServers"]

    # Uninstall
    res_uninst = runner.invoke(app, ["mcp", "uninstall", "--client", "cursor", "--yes"])
    assert res_uninst.exit_code == 0
    assert reg.is_registered() is False


def test_mcp_cli_codex_registrar(tmp_path, monkeypatch):
    monkeypatch.setenv("PEKE_HOME", str(tmp_path))
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

    reg = CodexRegistrar()
    assert reg.is_registered() is False

    ok = reg.install()
    assert ok is True
    assert reg.is_registered() is True

    ok_un = reg.uninstall()
    assert ok_un is True
    assert reg.is_registered() is False


def test_mcp_cli_doctor_command(tmp_path, monkeypatch):
    monkeypatch.setenv("PEKE_HOME", str(tmp_path))

    res = runner.invoke(app, ["mcp", "doctor", "--json"])
    assert res.exit_code == 0
    payload = json.loads(res.stdout)
    assert payload["stdio_handshake"] is True
    assert payload["tools_count"] == 11
