"""Offscreen pytest-qt tests for the providers and local model settings pane."""
from unittest.mock import patch

from peke.gui.panes.providers_pane import ProvidersPane


def test_providers_pane_instantiation(qtbot):
    pane = ProvidersPane()
    qtbot.addWidget(pane)
    assert pane.provider_combo.count() == 4
    assert pane.model_path_input is not None


def test_choose_model_uses_file_dialog(qtbot, monkeypatch, tmp_path):
    pane = ProvidersPane()
    qtbot.addWidget(pane)
    model = tmp_path / "local.gguf"
    model.write_bytes(b"test model placeholder")
    monkeypatch.setattr(
        "peke.gui.panes.providers_pane.QFileDialog.getOpenFileName",
        lambda *args, **kwargs: (str(model), "GGUF models (*.gguf)"),
    )
    pane.choose_model()
    assert pane.model_path_input.text() == str(model)


def test_save_local_model_persists_existing_gguf(qtbot, monkeypatch, tmp_path):
    pane = ProvidersPane()
    qtbot.addWidget(pane)
    model = tmp_path / "local.gguf"
    model.write_bytes(b"test model placeholder")
    pane.model_path_input.setText(str(model))
    with patch("peke.gui.panes.providers_pane.save_user_settings") as save:
        pane.save_local_model()
    save.assert_called_once_with({"MODEL_PATH": str(model.resolve())})
    assert "saved" in pane.model_status.text().lower()
