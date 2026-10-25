"""Regression test: startup results must be handled on the GUI thread, not the worker thread."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import threading  # noqa: E402

import pytest  # noqa: E402

pytest.importorskip("PySide6")
pytest.importorskip("pytestqt")

from PySide6.QtCore import QThread  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from peke.gui.app import StartupBridge, StartupWorker  # noqa: E402
from peke.gui.main_window import MainWindow  # noqa: E402


def test_startup_ready_runs_on_gui_thread(qtbot, monkeypatch):
    seen: list[int] = []
    window = MainWindow()
    qtbot.addWidget(window)
    thread = QThread()
    worker = StartupWorker()
    worker.moveToThread(thread)
    bridge = StartupBridge(window, None, thread)
    monkeypatch.setattr(bridge, "_maybe_show_welcome", lambda: None)
    original = StartupBridge.on_ready

    def spy(self, extractor):
        seen.append(threading.get_ident())
        original(self, extractor)

    monkeypatch.setattr(StartupBridge, "on_ready", spy)
    # Reconnect after patching so the spy is the slot that runs.
    thread.started.connect(worker.run)
    worker.finished.connect(bridge.on_ready)
    thread.start()
    qtbot.waitUntil(lambda: bool(seen), timeout=10000)
    assert seen[0] == threading.main_thread().ident
    assert window.isVisible()
    thread.quit()
    thread.wait(5000)
    assert QApplication.instance() is not None
