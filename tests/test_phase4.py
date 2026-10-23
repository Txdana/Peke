"""Tests for Phase 4 additions: banner, doctor command, splash widget, wheel checks, and version."""

import io
import zipfile
from unittest.mock import patch

import pytest
from rich.console import Console
from typer.testing import CliRunner

from peke.banner import get_banner_string, print_banner
from peke.cli import app
from peke.fetch import sanitize_headers

runner = CliRunner()


def test_banner_string_formatting() -> None:
    banner_active = get_banner_string(mcp_active=True)
    assert "[MCP Active]" in banner_active
    assert "PEKE" in banner_active

    banner_off = get_banner_string(mcp_active=False)
    assert "[MCP Off]" in banner_off


def test_print_banner_no_color(monkeypatch) -> None:
    monkeypatch.setenv("NO_COLOR", "1")
    banner_str = get_banner_string(mcp_active=False)
    assert "[MCP Off]" in banner_str


def test_print_banner_non_tty() -> None:
    buf = io.StringIO()
    c = Console(file=buf, force_terminal=False)
    print_banner(console=c, mcp_active=True)
    output = buf.getvalue()
    assert "[MCP Active]" in output


def test_cli_version_command() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "Peke version" in result.stdout
    assert "PEKE" in result.stdout


def test_cli_doctor_command() -> None:
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "Diagnostic" in result.stdout
    assert "Python Environment" in result.stdout
    assert "Scrapling Fetcher" in result.stdout


def test_cli_no_banner_flag() -> None:
    result = runner.invoke(app, ["--no-banner", "doctor"])
    assert result.exit_code == 0
    assert "Diagnostic" in result.stdout


def test_header_sanitization() -> None:
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Authorization": "Bearer secret_token_123",
        "Cookie": "session=xyz",
        "X-API-Key": "key_456",
    }
    sanitized = sanitize_headers(headers)
    assert sanitized["User-Agent"] == "Mozilla/5.0"
    assert sanitized["Authorization"] == "[REDACTED]"
    assert sanitized["Cookie"] == "[REDACTED]"
    assert sanitized["X-API-Key"] == "[REDACTED]"


def test_wheel_contents_include_assets() -> None:
    # Check that built wheel file in dist contains assets
    import glob
    wheels = glob.glob("dist/*.whl")
    if wheels:
        with zipfile.ZipFile(wheels[0], "r") as zf:
            file_names = zf.namelist()
            assert any("theme.qss" in name for name in file_names)
            assert any("icon.svg" in name for name in file_names)


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def test_splash_widget_headless(qapp) -> None:
    from peke.gui.splash import SplashWidget

    with patch("peke.gui.splash.ResourceDataLoaderThread.start"):
        splash = SplashWidget(mcp_active=False, no_splash=True)
        assert not splash.should_show

        splash_active = SplashWidget(mcp_active=True, no_splash=False)
        assert splash_active.should_show
        assert splash_active.full_banner_text is not None
        assert "[MCP Active]" in splash_active.full_banner_text
