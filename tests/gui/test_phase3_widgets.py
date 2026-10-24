import pytest

pytest.importorskip("PySide6")
from peke.gui.widgets.endpoint_tree import EndpointTree  # noqa: E402
from peke.gui.widgets.json_view import JsonView  # noqa: E402
from peke.gui.widgets.vram_card import VramCard  # noqa: E402


def test_endpoint_tree_groups_and_marks_hidden(qtbot):
    tree = EndpointTree(); qtbot.addWidget(tree)
    tree.set_endpoints([
        {"method": "GET", "path": "/api/v1/items", "discovered_by": "rea", "hidden": True},
        {"method": "POST", "path": "/api/v1/search", "discovered_by": "profile"},
    ])
    assert tree.topLevelItemCount() == 1
    host = tree.topLevelItem(0)
    assert host.childCount() == 1
    group = host.child(0).child(0)
    assert group.childCount() == 2
    assert "Hidden" in group.child(0).text(2)


def test_json_view_pretty_prints(qtbot):
    view = JsonView(); qtbot.addWidget(view)
    view.set_json('{"title":"hello","count":2}')
    assert '"title": "hello"' in view.editor.toPlainText()
    assert view.editor.blockCount() >= 3


def test_vram_card_fallback_does_not_raise(qtbot, monkeypatch):
    card = VramCard(); qtbot.addWidget(card)
    monkeypatch.setattr("importlib.util.find_spec", lambda name: None)
    card.refresh()
    assert "GPU: not detected" in card.label.text()
