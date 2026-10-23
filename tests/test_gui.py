"""GUI integration and unit tests for Peke desktop workbench."""

import os
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

# Ensure offscreen Qt platform plugin for headless test environments
os.environ["QT_QPA_PLATFORM"] = "offscreen"


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def test_endpoint_tree_grouping(qapp):
    from peke.gui.widgets.endpoint_tree import EndpointTreeWidget

    tree_widget = EndpointTreeWidget()
    endpoints = [
        {
            "method": "GET",
            "path": "https://api.example.com/v1/products",
            "size": "10KB",
            "discovered_by": "rea",
            "hidden": False,
        },
        {
            "method": "POST",
            "path": "https://api.example.com/v1/cart",
            "size": "2KB",
            "discovered_by": "profile",
            "hidden": True,
        },
    ]

    tree_widget.populate_endpoints(endpoints)
    assert tree_widget.tree.topLevelItemCount() == 1
    host_item = tree_widget.tree.topLevelItem(0)
    assert host_item.text(0) == "api.example.com"
    assert host_item.childCount() == 2


def test_json_highlighter_token_rules(qapp):
    from peke.gui.widgets.json_view import JsonViewWidget

    widget = JsonViewWidget()
    sample_json = {"title": "Test Product", "price": 99.99, "in_stock": True}
    widget.set_json(sample_json)

    assert "Test Product" in widget.editor.toPlainText()
    assert widget.highlighter is not None
    assert len(widget.highlighter.rules) == 4


def test_vram_card_fallback_no_gpu(qapp):
    from peke.gui.widgets.vram_card import VramCardWidget

    card = VramCardWidget()
    card.pynvml_available = False
    card.psutil_available = False
    card.update_metrics()

    assert "not detected" in card.title_label.text().lower() or "cpu" in card.title_label.text().lower()


def test_vram_card_with_mocked_pynvml(qapp):
    from peke.gui.widgets.vram_card import VramCardWidget

    card = VramCardWidget()
    card.pynvml_available = True

    mock_info = MagicMock()
    mock_info.used = 4 * (1024**3)
    mock_info.total = 8 * (1024**3)

    with patch("pynvml.nvmlDeviceGetHandleByIndex"), patch(
        "pynvml.nvmlDeviceGetMemoryInfo", return_value=mock_info
    ):
        card.update_metrics()
        assert "4.0 GB / 8.0 GB" in card.value_label.text()
        assert card.progress_bar.value() == 50


def test_schemas_page_invalid_file_handling(qapp, tmp_path):
    from peke.gui.panes.schemas_page import SchemasPage

    page = SchemasPage()
    bad_py = tmp_path / "invalid_schema.py"
    bad_py.write_text("def invalid_code(: print('syntax error')")

    with patch("PySide6.QtWidgets.QFileDialog.getOpenFileName", return_value=(str(bad_py), "")):
        with patch("PySide6.QtWidgets.QMessageBox.critical") as mock_crit:
            page.load_schema_from_file()
            assert mock_crit.called


def test_worker_cancellation(qapp):
    from peke.gui.worker import PipelineWorker

    worker = PipelineWorker(target_input="https://example.com")
    cancelled_emitted = False

    def on_cancelled():
        nonlocal cancelled_emitted
        cancelled_emitted = True

    worker.sig_cancelled.connect(on_cancelled)
    worker.cancel()
    worker.run()

    assert cancelled_emitted is True


def test_full_mocked_pipeline_in_gui(qapp):
    from peke.extract import ExtractionResult
    from peke.fetch import FetchResult
    from peke.gui.panes.workspace import WorkspacePage
    from peke.schemas import Article

    workspace = WorkspacePage()
    workspace.url_input.setText("https://example.com/api/article")

    mock_fetch = FetchResult(
        url="https://example.com/api/article",
        text='{"title": "GUI Test Article", "content": "Sample content"}',
        status_code=200,
        is_json=True,
        json_data={"title": "GUI Test Article", "content": "Sample content"},
    )

    art_instance = Article(title="GUI Test Article", content="Sample content")
    mock_extract = ExtractionResult(
        data=art_instance,
        json_output=art_instance.model_dump(),
        markdown_output="# Article\n**Title**: GUI Test Article",
        used_llm=False,
    )

    with patch("peke.pipeline.fetch_target", return_value=mock_fetch), patch(
        "peke.pipeline.extract_data", return_value=mock_extract
    ):
        workspace._on_run_clicked()
        workspace.worker.wait(2000)
        QCoreApplication.processEvents()

        assert "GUI Test Article" in workspace.json_view.editor.toPlainText()
        assert "GUI Test Article" in workspace.metrics_tab.md_view.toPlainText()
