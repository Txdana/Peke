"""Main three-pane Peke workbench window."""
import time

from PySide6.QtCore import QSettings, QThread, Qt
from PySide6.QtWidgets import QHBoxLayout, QMainWindow, QMessageBox, QSplitter, QToolBar, QWidget
from peke.config import load_settings
from peke.extract import Extractor
from peke.gui.panes.output_panel import OutputPanel
from peke.gui.panes.sidebar import Sidebar
from peke.gui.panes.workspace import Workspace
from peke.gui.worker import PipelineWorker


class MainWindow(QMainWindow):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Peke")
        toolbar = QToolBar("Workbench controls", self)
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        self.output_toggle = toolbar.addAction("Show / hide output panel")
        self.output_toggle.setCheckable(True)
        self.output_toggle.setChecked(True)
        self.output_toggle.setAccessibleName("Toggle output panel")
        self.output_toggle.toggled.connect(self._toggle_output_panel)
        self.splash_toggle = toolbar.addAction("Startup splash")
        self.splash_toggle.setCheckable(True)
        self.splash_toggle.setChecked(self.settings_value("show_splash", True))
        self.splash_toggle.setAccessibleName("Enable startup splash")
        self.splash_toggle.toggled.connect(lambda enabled: self._save_setting("show_splash", enabled))
        about_action = toolbar.addAction("About Peke")
        about_action.triggered.connect(self._show_about)
        self.resize(1440, 900)
        self.setMinimumSize(1100, 720)
        self.settings = QSettings("Peke", "PekeWorkbench")
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        self._thread: QThread | None = None
        self._worker: PipelineWorker | None = None
        self._output_visible = True
        self._extractor: Extractor | None = None
        self._last_run_at = 0.0
        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.sidebar = Sidebar()
        self.workspace = Workspace()
        self.output_panel = OutputPanel()
        self.splitter.addWidget(self.sidebar)
        self.splitter.addWidget(self.workspace)
        self.splitter.addWidget(self.output_panel)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setStretchFactor(2, 0)
        self.splitter.setSizes([240, 760, 420])
        layout.addWidget(self.splitter)
        self.setCentralWidget(central)
        for index, button in enumerate(self.sidebar.buttons):
            button.clicked.connect(lambda checked=False, i=index: self._select_page(i))
        target = self.workspace.target_page
        target.run_requested.connect(self.start_pipeline)
        target.endpoint_tree.use_endpoint.connect(self._use_endpoint)
        target.cancel_requested.connect(self.cancel_pipeline)

    def settings_value(self, key: str, default):
        return QSettings("Peke", "PekeWorkbench").value(key, default, type=bool)

    def _save_setting(self, key: str, value) -> None:
        QSettings("Peke", "PekeWorkbench").setValue(key, value)

    def _show_about(self) -> None:
        from peke import __version__
        dialog = QMessageBox(self)
        dialog.setWindowTitle("About Peke")
        dialog.setTextFormat(Qt.TextFormat.RichText)
        dialog.setText(
            f"<h2>Peke {__version__}</h2>"
            "<p>Open-source local-first data extraction workbench.</p>"
            "<p>License: <a href='https://opensource.org/license/mit'>MIT</a>. "
            "See <a href='https://github.com/Scrapling/Scrapling'>Scrapling</a>, "
            "<a href='https://github.com/ggml-org/llama.cpp'>llama.cpp</a>, "
            "<a href='https://doc.qt.io/qtforpython-6/'>PySide6</a>, and "
            "<a href='https://docs.pydantic.dev/'>Pydantic</a> for upstream documentation. "
            "Third-party license details are listed in docs/third-party-notices.md.</p>"
        )
        dialog.setStandardButtons(QMessageBox.StandardButton.Ok)
        dialog.exec()

    def _select_page(self, index: int) -> None:
        self.workspace.setCurrentIndex(index)
        for idx, button in enumerate(self.sidebar.buttons):
            button.setChecked(idx == index)
            if self.sidebar.collapsed:
                from peke.gui.widgets.icons import svg_icon
                from peke.gui import theme
                button.setIcon(svg_icon(["target", "scraper", "model", "schema"][idx], theme.TERRACOTTA if idx == index else theme.MUTED_TEXT))

    def start_pipeline(self, url: str, fetcher: str) -> None:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            self.workspace.target_page.console.append_event(type("UiEvent", (), {"ts":"", "tag":"INVALID URL", "level":"error", "message":"Enter a valid http:// or https:// URL."})())
            return
        if self._thread is not None:
            return
        now = time.monotonic()
        delay = load_settings().request_delay_seconds
        if self._last_run_at and now - self._last_run_at < delay:
            page = self.workspace.target_page
            page.console.append_event(type("UiEvent", (), {"ts":"", "tag":"RATE LIMIT", "level":"warn", "message":f"Please wait {delay - (now - self._last_run_at):.1f}s before starting another run."})())
            return
        self._last_run_at = now
        if load_settings().model_path is None:
            choice = QMessageBox(self)
            choice.setWindowTitle("No local model configured")
            choice.setText("Peke can validate clean JSON without a model. HTML extraction needs a local GGUF model. Nothing will be downloaded automatically.")
            choose_button = choice.addButton("Choose model…", QMessageBox.ButtonRole.AcceptRole)
            choice.addButton("Continue without model", QMessageBox.ButtonRole.RejectRole)
            choice.exec()
            if choice.clickedButton() == choose_button:
                self.workspace.setCurrentIndex(2)
                self.workspace.model_page.choose_model()
                return
        page = self.workspace.target_page
        page.run_button.setEnabled(False)
        page.run_button.setText("Running…")
        page.cancel_button.show()
        page.console.append_event(type("UiEvent", (), {"ts":"", "tag":"START", "level":"info", "message":f"Starting pipeline for {url}"})())
        self._thread = QThread(self)
        self._worker = PipelineWorker(url, fetcher, extractor=self._extractor)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.event.connect(self._on_pipeline_event)
        self._worker.finished.connect(self._pipeline_finished)
        self._worker.failed.connect(self._pipeline_failed)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._cleanup_worker)
        self._thread.start()

    def cancel_pipeline(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            self.workspace.target_page.console.append_event(type("UiEvent", (), {"ts":"", "tag":"CANCEL", "level":"warn", "message":"Cancellation requested."})())

    def _on_pipeline_event(self, event) -> None:
        page = self.workspace.target_page
        page.console.append_event(event)
        data = getattr(event, "data", None)
        if isinstance(data, dict) and isinstance(data.get("endpoints"), list):
            page.endpoint_tree.set_endpoints(data["endpoints"])

    def _use_endpoint(self, hint: dict) -> None:
        from urllib.parse import urljoin
        page = self.workspace.target_page
        current = page.url_input.text().strip()
        path = str(hint.get("path", "/"))
        page.url_input.setText(urljoin(current, path))
        from PySide6.QtCore import QSettings
        QSettings("Peke", "PekeWorkbench").setValue("selected_endpoint", hint)
        page.fetcher.setCurrentIndex(1)
        page.console.append_event(type("UiEvent", (), {"ts":"", "tag":"ENDPOINT", "level":"info", "message":"Endpoint selected; next run will use API mode."})())

    def _pipeline_finished(self, result) -> None:
        if self._worker is not None:
            self._extractor = self._worker.extractor
        self.output_panel.set_result(result)
        if getattr(result, "endpoints", None):
            self.workspace.target_page.endpoint_tree.set_endpoints([hint.model_dump(mode="json") for hint in result.endpoints])
        self.workspace.target_page.console.append_event(type("UiEvent", (), {"ts":"", "tag":"DONE", "level":"ok", "message":f"Pipeline finished with {len(result.records)} record(s)."})())
        self._reset_run_button()

    def _pipeline_failed(self, message: str) -> None:
        if self._worker is not None:
            self._extractor = self._worker.extractor
        self.workspace.target_page.console.append_event(type("UiEvent", (), {"ts":"", "tag":"ERROR", "level":"error", "message":message})())
        self._reset_run_button()

    def _reset_run_button(self) -> None:
        page = self.workspace.target_page
        page.run_button.setEnabled(True)
        page.run_button.setText("▶  Run Pipeline")
        page.cancel_button.hide()

    def _cleanup_worker(self) -> None:
        if self._worker is not None:
            self._worker.deleteLater()
        if self._thread is not None:
            self._thread.deleteLater()
        self._worker = None
        self._thread = None

    def _toggle_output_panel(self, visible: bool) -> None:
        self._output_visible = visible
        self.output_panel.setVisible(visible and self.width() >= 1250)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        should_show = self.width() >= 1250
        requested = self.output_toggle.isChecked()
        self.output_panel.setVisible(should_show and requested)

    def closeEvent(self, event) -> None:
        self.settings.setValue("geometry", self.saveGeometry())
        if self._worker is not None:
            self._worker.cancel()
        if self._thread is not None and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(5000)
        if self._extractor is not None:
            try:
                model = getattr(self._extractor, "_llm", None)
                if model is not None and hasattr(model, "close"):
                    model.close()
            except (RuntimeError, AttributeError):
                pass
        super().closeEvent(event)
