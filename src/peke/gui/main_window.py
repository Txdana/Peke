"""Main three-pane Peke workbench window."""
import time
from importlib.resources import files
from urllib.parse import urljoin, urlparse

from PySide6.QtCore import QSettings, Qt, QThread
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QSplitter,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from peke.config import load_settings
from peke.extract import Extractor
from peke.gui import theme
from peke.gui.events import ui_event
from peke.gui.panes.output_panel import OutputPanel
from peke.gui.panes.sidebar import NAV_ITEMS, Sidebar
from peke.gui.panes.workspace import Workspace
from peke.gui.widgets.icons import svg_icon
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
        self.output_toggle.setToolTip("Toggle output panel")
        self.output_toggle.toggled.connect(self._toggle_output_panel)
        self.splash_toggle = toolbar.addAction("Startup splash")
        self.splash_toggle.setCheckable(True)
        self.splash_toggle.setChecked(self.settings_value("show_splash", True))
        self.splash_toggle.setToolTip("Enable startup splash")
        self.splash_toggle.toggled.connect(lambda enabled: self._save_setting("show_splash", enabled))
        about_action = toolbar.addAction("About Peke")
        about_action.triggered.connect(self._show_about)
        self.resize(1440, 900)
        self.setMinimumSize(1100, 720)
        self.settings = QSettings("Peke", "PekeWorkbench")
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
            self._ensure_on_screen()
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

    def _ensure_on_screen(self) -> None:
        """A saved position from a monitor that is gone would open the window off-screen."""
        screens = QGuiApplication.screens()
        if not screens:
            return
        if any(screen.availableGeometry().intersects(self.geometry()) for screen in screens):
            return
        available = (QGuiApplication.primaryScreen() or screens[0]).availableGeometry()
        self.resize(min(1440, available.width()), min(900, available.height()))
        self.move(available.center() - self.rect().center())

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
            "<p>License: <a href='https://www.apache.org/licenses/LICENSE-2.0'>Apache-2.0</a>. "
            "See <a href='https://github.com/Scrapling/Scrapling'>Scrapling</a>, "
            "<a href='https://github.com/ggml-org/llama.cpp'>llama.cpp</a>, "
            "<a href='https://doc.qt.io/qtforpython-6/'>PySide6</a>, and "
            "<a href='https://docs.pydantic.dev/'>Pydantic</a> for upstream documentation. "
            "Use the Third-party notices button for the licenses bundled with this installation.</p>"
        )
        dialog.setStandardButtons(QMessageBox.StandardButton.Ok)
        notices_button = dialog.addButton("Third-party notices", QMessageBox.ButtonRole.ActionRole)
        dialog.exec()
        if dialog.clickedButton() == notices_button:
            self._show_third_party_notices()

    def _show_third_party_notices(self) -> None:
        """Display packaged attribution and licensing information even when offline."""
        try:
            notices = files("peke").joinpath("THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
        except (OSError, ModuleNotFoundError) as exc:
            QMessageBox.warning(self, "Third-party notices", f"Could not load bundled notices: {exc}")
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Peke · Third-party notices")
        dialog.resize(760, 620)
        layout = QVBoxLayout(dialog)
        content = QPlainTextEdit(dialog)
        content.setReadOnly(True)
        content.setPlainText(notices)
        layout.addWidget(content)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=dialog)
        buttons.rejected.connect(dialog.reject)
        buttons.accepted.connect(dialog.accept)
        layout.addWidget(buttons)
        dialog.exec()

    def _select_page(self, index: int) -> None:
        if not 0 <= index < self.workspace.count():
            return
        self.workspace.setCurrentIndex(index)
        for idx, button in enumerate(self.sidebar.buttons):
            button.setChecked(idx == index)
            icon_name = NAV_ITEMS[idx][1] if idx < len(NAV_ITEMS) else "target"
            button.setIcon(svg_icon(icon_name, theme.TERRACOTTA if idx == index else theme.MUTED_TEXT))

    def start_pipeline(self, url: str, fetcher: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            self.workspace.target_page.console.append_event(
                ui_event("INVALID URL", "error", "Enter a valid http:// or https:// URL.")
            )
            return
        if self._thread is not None:
            return
        now = time.monotonic()
        delay = load_settings().request_delay_seconds
        if self._last_run_at and now - self._last_run_at < delay:
            page = self.workspace.target_page
            page.console.append_event(
                ui_event("RATE LIMIT", "warn", f"Please wait {delay - (now - self._last_run_at):.1f}s before starting another run.")
            )
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
                self.workspace.setCurrentWidget(self.workspace.providers_page)
                self.workspace.providers_page.choose_model()
                return
        page = self.workspace.target_page
        page.run_button.setEnabled(False)
        page.run_button.setText("Running…")
        page.cancel_button.show()
        page.console.append_event(ui_event("START", "info", f"Starting pipeline for {url}"))
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
            self.workspace.target_page.console.append_event(
                ui_event("CANCEL", "warn", "Cancellation requested.")
            )

    def _on_pipeline_event(self, event) -> None:
        page = self.workspace.target_page
        page.console.append_event(event)
        data = getattr(event, "data", None)
        if isinstance(data, dict) and isinstance(data.get("endpoints"), list):
            page.endpoint_tree.set_endpoints(data["endpoints"])

    def _use_endpoint(self, hint: dict) -> None:
        page = self.workspace.target_page
        current = page.url_input.text().strip()
        path = str(hint.get("path", "/"))
        page.url_input.setText(urljoin(current, path))
        QSettings("Peke", "PekeWorkbench").setValue("selected_endpoint", hint)
        page.fetcher.setCurrentIndex(1)
        page.console.append_event(
            ui_event("ENDPOINT", "info", "Endpoint selected; next run will use API mode.")
        )

    def _pipeline_finished(self, result) -> None:
        if self._worker is not None:
            self._extractor = self._worker.extractor
        self.output_panel.set_result(result)
        if getattr(result, "endpoints", None):
            self.workspace.target_page.endpoint_tree.set_endpoints([hint.model_dump(mode="json") for hint in result.endpoints])
        self.workspace.target_page.console.append_event(
            ui_event("DONE", "ok", f"Pipeline finished with {len(result.records)} record(s).")
        )
        self._reset_run_button()

    def _pipeline_failed(self, message: str) -> None:
        if self._worker is not None:
            self._extractor = self._worker.extractor
        self.workspace.target_page.console.append_event(ui_event("ERROR", "error", message))
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
        # A QThread must not outlive the QObject tree that owns it. The network
        # and Docker workers are synchronous operations, so keep the window alive
        # until they return instead of destroying a running QThread.
        search_thread = getattr(self.workspace.search_page, "_thread", None)
        if search_thread is not None and search_thread.isRunning():
            QMessageBox.information(
                self,
                "Search operation in progress",
                "A search, research, or local SearXNG operation is still running. "
                "Wait for it to finish before closing Peke.",
            )
            event.ignore()
            return
        if self._worker is not None:
            self._worker.cancel()
        if self._thread is not None and self._thread.isRunning():
            self._thread.quit()
            if not self._thread.wait(5000):
                QMessageBox.warning(
                    self,
                    "Extraction still running",
                    "The extraction worker has not exited yet. Peke remains open to avoid "
                    "destroying an active worker; wait for cancellation to finish and close again.",
                )
                event.ignore()
                return
        self.settings.setValue("geometry", self.saveGeometry())
        if self._extractor is not None:
            try:
                model = getattr(self._extractor, "_llm", None)
                if model is not None and hasattr(model, "close"):
                    model.close()
            except (RuntimeError, AttributeError):
                pass
        super().closeEvent(event)
