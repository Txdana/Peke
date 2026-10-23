"""Main extraction workspace page for Peke GUI."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from peke.gui.widgets.console import ConsoleWidget
from peke.gui.widgets.endpoint_tree import EndpointTreeWidget
from peke.gui.widgets.json_view import JsonViewWidget
from peke.gui.widgets.metrics_tab import MetricsTabWidget
from peke.gui.widgets.vram_card import VramCardWidget
from peke.gui.worker import PipelineWorker
from peke.pipeline import PipelineEvent, PipelineResult
from peke.schemas import SCHEMA_REGISTRY


class WorkspacePage(QWidget):
    """Main extraction workspace panel combining controls, endpoint tree, output tabs, and VRAM monitor."""

    sig_status_updated = Signal(str, float, float)  # model_name, temp, tok_sec

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.worker: PipelineWorker | None = None
        self.init_ui()

    def init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Control Bar
        control_card = QWidget()
        control_card.setStyleSheet("background-color: #252526; border-radius: 6px;")
        control_layout = QHBoxLayout(control_card)

        control_layout.addWidget(QLabel("Target URL:"))
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://example.com/api/products or profile path...")
        control_layout.addWidget(self.url_input)

        control_layout.addWidget(QLabel("Fetcher:"))
        self.fetcher_combo = QComboBox()
        self.fetcher_combo.addItems(["Fetcher", "StealthyFetcher"])
        control_layout.addWidget(self.fetcher_combo)

        control_layout.addWidget(QLabel("Schema:"))
        self.schema_combo = QComboBox()
        self.schema_combo.addItems(list(SCHEMA_REGISTRY.keys()))
        control_layout.addWidget(self.schema_combo)

        self.run_btn = QPushButton("▶ Run Pipeline")
        self.run_btn.setStyleSheet("background-color: #2D5A4C; color: white; font-weight: bold;")
        self.run_btn.clicked.connect(self._on_run_clicked)
        control_layout.addWidget(self.run_btn)

        self.cancel_btn = QPushButton("⏹ Cancel")
        self.cancel_btn.setStyleSheet("background-color: #B04A24; color: white; font-weight: bold;")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._on_cancel_clicked)
        control_layout.addWidget(self.cancel_btn)

        layout.addWidget(control_card)

        # Main Splitter (Left: Endpoint Tree + VRAM Card | Right: Console + Output Tabs)
        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left Container
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        left_layout.addWidget(QLabel("Discovered Endpoints:"))
        self.endpoint_tree = EndpointTreeWidget(on_use_endpoint=self.on_use_endpoint_selected)
        left_layout.addWidget(self.endpoint_tree)

        self.vram_card = VramCardWidget()
        left_layout.addWidget(self.vram_card)

        main_splitter.addWidget(left_widget)

        # Right Container
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # Vertical Splitter between Console Log and Output Tabs
        right_splitter = QSplitter(Qt.Orientation.Vertical)

        self.console_widget = ConsoleWidget()
        right_splitter.addWidget(self.console_widget)

        self.output_tabs = QTabWidget()

        # Output Tab 1: Highlighted JSON View
        self.json_view = JsonViewWidget()
        self.output_tabs.addTab(self.json_view, "Clean JSON Data")

        # Output Tab 2: Markdown & Metrics Tab
        self.metrics_tab = MetricsTabWidget()
        self.output_tabs.addTab(self.metrics_tab, "Markdown & Metrics")

        right_splitter.addWidget(self.output_tabs)
        right_splitter.setSizes([200, 400])

        right_layout.addWidget(right_splitter)
        main_splitter.addWidget(right_widget)

        main_splitter.setSizes([350, 650])
        layout.addWidget(main_splitter)

    def on_use_endpoint_selected(
        self, path: str, method: str, headers: dict, params: dict
    ) -> None:
        self.url_input.setText(path)

    def _on_run_clicked(self) -> None:
        url = self.url_input.text().strip()
        if not url:
            return

        self.run_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.console_widget.clear_log()

        fetcher = self.fetcher_combo.currentText()
        schema = self.schema_combo.currentText()

        self.worker = PipelineWorker(
            target_input=url,
            fetcher_type=fetcher,
            schema_name=schema,
        )
        self.worker.sig_event_emitted.connect(self._on_event_received)
        self.worker.sig_finished.connect(self._on_pipeline_finished)
        self.worker.sig_cancelled.connect(self._on_pipeline_cancelled)
        self.worker.start()

    def _on_cancel_clicked(self) -> None:
        if self.worker:
            self.worker.cancel()

    def _on_event_received(self, event: PipelineEvent) -> None:
        self.console_widget.add_event(event)

        if event.stage == "DISCOVER" and event.details and "endpoints" in event.details:
            self.endpoint_tree.populate_endpoints(event.details["endpoints"])

    def _on_pipeline_finished(self, result: PipelineResult | None) -> None:
        self.run_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)

        if result and result.profile and result.profile.endpoint_hints:
            self.endpoint_tree.populate_endpoints(result.profile.endpoint_hints)

        if result and result.extraction_result:
            ext = result.extraction_result
            if ext.json_output:
                self.json_view.set_json(ext.json_output)

            self.metrics_tab.set_extraction_result(ext)
            self.sig_status_updated.emit(ext.model_name, ext.temperature, ext.tokens_per_second)

    def _on_pipeline_cancelled(self) -> None:
        self.run_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        cancel_event = PipelineEvent(
            timestamp="",
            stage="PIPELINE",
            level="WARNING",
            message="Pipeline run cancelled by user.",
        )
        self.console_widget.add_event(cancel_event)
