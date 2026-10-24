"""Tests for installer, launcher path, setup, and doctor MCP integration."""

from pathlib import Path

from typer.testing import CliRunner

from peke.cli import app
from peke.mcp.clients.base import get_peke_launcher
from peke.mcp.clients.registrars import get_mcp_entry

runner = CliRunner()


def test_launcher_path_resolves():
    launcher = get_peke_launcher()
    assert launcher is not None
    assert len(launcher) > 0
    p = Path(launcher)
    assert p.exists() or p.parent.exists()


def test_mcp_entry_windows_wrapper():
    entry = get_mcp_entry(transport="stdio", is_win=True)
    assert entry["command"] == "cmd.exe"
    assert entry["args"][:3] == ["/d", "/c", get_peke_launcher()]


def test_mcp_entry_posix():
    entry = get_mcp_entry(transport="stdio", is_win=False)
    assert entry["command"] == get_peke_launcher()
    assert entry["args"] == ["mcp", "serve"]


def test_doctor_includes_mcp_registrations():
    res = runner.invoke(app, ["doctor"])
    assert res.exit_code == 0
    assert "MCP Registrations" in res.stdout
