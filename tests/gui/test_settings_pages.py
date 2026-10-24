"""GUI settings persistence tests; executed by the offscreen Qt CI job."""
import json

import pytest

pytest.importorskip("PySide6")

from peke import config  # noqa: E402
from peke.gui.panes.settings_pages import ModelSettingsPage  # noqa: E402


def test_model_settings_page_persists_local_model_and_rea_command(qtbot, tmp_path, monkeypatch):
    config_file = tmp_path / "settings.json"
    monkeypatch.setattr(config, "user_settings_path", lambda: config_file)
    model_file = tmp_path / "local.gguf"
    model_file.write_bytes(b"not a real model; settings-only fixture")
    config_file.write_text(json.dumps({"REQUEST_DELAY_SECONDS": 2.0}), encoding="utf-8")

    page = ModelSettingsPage()
    qtbot.addWidget(page)
    page.model_path.setText(str(model_file))
    page.rea_command.setText('"/opt/rea tool" --json {url}')
    page.n_ctx.setValue(2048)
    page.save_settings()

    saved = json.loads(config_file.read_text(encoding="utf-8"))
    assert saved["MODEL_PATH"] == str(model_file)
    assert saved["REA_COMMAND"] == '"/opt/rea tool" --json {url}'
    assert saved["N_CTX"] == 2048
    assert saved["REQUEST_DELAY_SECONDS"] == 2.0
    assert "Could not save" not in page.status.text()


def test_model_settings_page_rejects_missing_model(qtbot, tmp_path, monkeypatch):
    config_file = tmp_path / "settings.json"
    monkeypatch.setattr(config, "user_settings_path", lambda: config_file)
    page = ModelSettingsPage()
    qtbot.addWidget(page)
    page.model_path.setText(str(tmp_path / "missing.gguf"))
    page.save_settings()
    assert not config_file.exists()
    assert "does not exist" in page.status.text()
