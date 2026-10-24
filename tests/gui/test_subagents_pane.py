"""Offscreen pytest-qt tests for Sub-agents UI pane."""
import json

from peke.gui.panes.subagents_pane import SubagentsPane


def test_subagents_pane_instantiation(qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    runs_dir = tmp_path / ".peke" / "runs" / "run_test123"
    runs_dir.mkdir(parents=True, exist_ok=True)

    run_file = runs_dir / "subagents.json"
    run_file.write_text(json.dumps({
        "run_id": "run_test123",
        "target_url": "http://example.com",
        "ok": True,
        "provider": "local_builtin",
        "duration_seconds": 1.5,
        "bundle": {"endpoints": []},
        "network": {"routes": []},
        "auth": {"tokens": [{"name": "Authorization", "value": "secret_value", "redacted": False}]},
        "synthesis": {},
    }))

    pane = SubagentsPane()
    qtbot.addWidget(pane)

    assert pane.table.rowCount() == 1
    item = pane.table.item(0, 0)
    assert item.text() == "run_test123"


def test_subagents_pane_secret_redaction(qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    runs_dir = tmp_path / ".peke" / "runs" / "run_secret"
    runs_dir.mkdir(parents=True, exist_ok=True)

    run_file = runs_dir / "subagents.json"
    run_file.write_text(json.dumps({
        "run_id": "run_secret",
        "target_url": "http://example.com",
        "ok": True,
        "provider": "local_builtin",
        "duration_seconds": 1.0,
        "auth": {"tokens": [{"name": "Authorization", "value": "my_secret_token", "redacted": False}]},
    }))

    pane = SubagentsPane()
    qtbot.addWidget(pane)
    pane.table.selectRow(0)

    # By default, reveal_secrets is False -> secret token value should be masked
    json_text = pane.json_view.editor.toPlainText()
    assert "REDACTED" in json_text
