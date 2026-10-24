"""Unit tests for OS desktop integration and safe uninstall."""
from unittest.mock import MagicMock

from typer.testing import CliRunner

from peke.cli import app
from peke.desktop import (
    install_desktop_integration,
    is_desktop_installed,
    uninstall_desktop_integration,
)

runner = CliRunner()


def test_desktop_integration_install_and_uninstall(tmp_path, monkeypatch):
    monkeypatch.setattr("peke.desktop.paths.get_desktop_entry_path", lambda: tmp_path / "peke.desktop")
    monkeypatch.setattr("peke.desktop.paths.get_icon_dir", lambda: tmp_path / "icons")

    install_desktop_integration()
    assert (tmp_path / "peke.desktop").is_file()
    assert is_desktop_installed() is True

    uninstall_desktop_integration()
    assert (tmp_path / "peke.desktop").exists() is False


def test_cli_uninstall_purge_dry_run(tmp_path, monkeypatch):
    monkeypatch.setattr("peke.desktop.integration.uninstall_desktop_integration", MagicMock())

    result = runner.invoke(app, ["uninstall", "--purge", "--yes"])
    assert result.exit_code == 0
    assert "Peke Removal Plan" in result.output
