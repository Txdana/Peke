"""Offscreen tests for the Agent Access (MCP) GUI pane."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pytestqt")

from peke.gui.main_window import MainWindow  # noqa: E402
from peke.gui.panes.mcp_page import McpSettingsPage  # noqa: E402


def test_mcp_settings_page_constructs(qtbot, tmp_path, monkeypatch):
    monkeypatch.setenv("PEKE_HOME", str(tmp_path))

    page = McpSettingsPage()
    qtbot.addWidget(page)

    assert "Launcher path:" in page.launcher_label.text()
    assert page.agents_table.rowCount() >= 1
    assert page.activity_table.columnCount() == 6


def test_mcp_settings_page_selftest_button(qtbot, tmp_path, monkeypatch):
    monkeypatch.setenv("PEKE_HOME", str(tmp_path))

    page = McpSettingsPage()
    qtbot.addWidget(page)

    # Click self-test button
    monkeypatch.setattr("PySide6.QtWidgets.QMessageBox.information", lambda parent, title, text: None)
    page.selftest_btn.click()
    assert "PASS" in page.status_chip.text()


def test_main_window_navigates_to_mcp_page(qtbot, tmp_path, monkeypatch):
    monkeypatch.setenv("PEKE_HOME", str(tmp_path))

    window = MainWindow()
    qtbot.addWidget(window)

    assert window.workspace.count() == 6
    window.sidebar.buttons[5].click()
    assert window.workspace.currentIndex() == 5
    assert isinstance(window.workspace.currentWidget(), McpSettingsPage)
