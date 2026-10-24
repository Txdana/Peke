"""Offscreen pytest-qt tests for Providers and Model Manager UI pane."""
from unittest.mock import MagicMock

from peke.gui.panes.providers_pane import ProvidersPane


def test_providers_pane_instantiation(qtbot):
    pane = ProvidersPane()
    qtbot.addWidget(pane)
    assert pane.provider_combo.count() == 4


def test_providers_pane_download_trigger(qtbot, monkeypatch):
    pane = ProvidersPane()
    qtbot.addWidget(pane)

    mock_worker = MagicMock()
    monkeypatch.setattr("peke.gui.panes.providers_pane.ModelDownloadWorker", MagicMock(return_value=mock_worker))

    pane.show()
    pane._start_download()
    assert not pane.progress_bar.isHidden()
    mock_worker.start.assert_called_once()
