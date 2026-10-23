"""Offscreen tests for the optional desktop shell."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pytestqt")

from peke.gui.main_window import MainWindow  # noqa: E402
from peke.gui.panes.sidebar import Sidebar  # noqa: E402
from peke.gui.widgets.console import ExecutionConsole  # noqa: E402


class DummyEvent:
    ts = "2026-01-02T03:04:05+00:00"
    tag = "VALID"
    level = "ok"
    message = "Payload validated"


def test_window_constructs(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    assert window.minimumWidth() == 1100
    assert window.workspace.count() == 4


def test_sidebar_collapse_toggles(qtbot):
    sidebar = Sidebar()
    qtbot.addWidget(sidebar)
    sidebar.toggle_collapsed()
    assert sidebar.collapsed is True
    assert sidebar.collapse_button.accessibleName() == "Expand sidebar"
    sidebar.toggle_collapsed()
    assert sidebar.collapsed is False


def test_navigation_switches_pages(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.sidebar.buttons[2].click()
    assert window.workspace.currentIndex() == 2


def test_console_renders_tagged_event(qtbot):
    console = ExecutionConsole()
    qtbot.addWidget(console)
    console.append_event(DummyEvent())
    assert "[VALID] Payload validated" in console.text.toPlainText()
    assert "03:04:05" in console.text.toPlainText()


def test_copy_json_to_clipboard(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.output_panel.last_json = '{"ok": true}'
    window.output_panel.copy_json()
    from PySide6.QtGui import QGuiApplication
    assert QGuiApplication.clipboard().text() == '{"ok": true}'


def test_run_button_disables_and_reenables(qtbot, monkeypatch):
    from peke.gui import worker as worker_module

    class FakeResult:
        records = []
        markdown_summary = "# Done"
        metrics = {"model_name": "test-model", "temperature": 0.1}

    class FakePipeline:
        def __init__(self, settings=None, on_event=None):
            self.on_event = on_event

        def run(self, profile):
            import time
            time.sleep(0.1)
            return FakeResult()

    monkeypatch.setattr(worker_module, "Pipeline", FakePipeline)
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    window.start_pipeline("https://example.com", "basic")
    assert not window.workspace.target_page.run_button.isEnabled()
    qtbot.waitUntil(lambda: window.workspace.target_page.run_button.isEnabled(), timeout=3000)
    qtbot.waitUntil(lambda: window._thread is None, timeout=3000)
