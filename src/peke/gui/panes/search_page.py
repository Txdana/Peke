"""Integrated SearXNG search and evidence-research workspace."""
from __future__ import annotations

import logging
from urllib.parse import urlsplit

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QPlainTextEdit,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from peke.config import load_settings, save_user_settings
from peke.search import MAX_URL_LENGTH, SearchError, SearxngClient, detect
from peke.searxng_runtime import BASE_URL, SearXNGServiceError
from peke.gui import theme

logger = logging.getLogger(__name__)


class SearchWorker(QObject):
    """Run search and local SearXNG operations away from the GUI thread."""
    finished = Signal(object)
    progress = Signal(str, str, str)

    def __init__(self, operation: str, base_url: str, query: str = "", time_range: str | None = None) -> None:
        super().__init__()
        self.operation = operation
        self.base_url = base_url.strip()
        self.query = query.strip()
        self.time_range = time_range

    @Slot()
    def run(self) -> None:
        try:
            if self.operation == "check":
                client, status = detect(self.base_url or None, timeout=3.0)
                self.finished.emit({"operation": "check", "status": status, "connected": client is not None})
                return
            if self.operation == "search":
                client, status = detect(self.base_url or None, timeout=3.0)
                if client is None:
                    self.finished.emit({"operation": "search", "status": status, "hits": []})
                    return
                hits = client.search(self.query, time_range=self.time_range, pages=2, max_results=25)
                self.finished.emit({"operation": "search", "status": status, "hits": [hit.to_dict() for hit in hits]})
                return
            if self.operation == "research":
                from peke.research import research

                settings = load_settings()
                self.progress.emit("info", "Planning sources and checking available capabilities…", "RESEARCH")
                result = research(
                    self.query,
                    settings,
                    searxng_url=self.base_url or None,
                    deep=False,
                    depth=0,
                    max_sources=8,
                    workers=3,
                    stealth=False,
                    on_event=lambda event: self.progress.emit(event.level, event.message, event.tag or "RESEARCH"),
                )
                self.finished.emit({"operation": "research", "result": result.to_dict()})
                return
            if self.operation == "start_local":
                from peke.searxng_runtime import start_local_server

                self.progress.emit("info", "Starting the bundled local SearXNG service…", "SEARXNG")
                self.finished.emit({"operation": "start_local", "service": start_local_server()})
                return
            if self.operation == "stop_local":
                from peke.searxng_runtime import stop_local_server

                self.finished.emit({"operation": "stop_local", "service": stop_local_server()})
                return
            raise ValueError(f"Unsupported operation: {self.operation}")
        except (SearchError, SearXNGServiceError, OSError, ValueError) as exc:
            self.finished.emit({"operation": self.operation, "error": str(exc)})
        except Exception as exc:  # surfaced to the UI, with details logged for debugging
            logger.exception("SearXNG operation failed")
            self.finished.emit({"operation": self.operation, "error": f"Unexpected error ({type(exc).__name__}): {exc}"})


class SearchPage(QWidget):
    """A first-class search UI with instance testing and optional local service controls."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._thread: QThread | None = None
        self._worker: SearchWorker | None = None
        self._active_url: str | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea(self)
        scroll.setObjectName("searchPageScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        root = QVBoxLayout(content)
        root.setContentsMargins(22, 20, 22, 18)
        root.setSpacing(14)
        scroll.setWidget(content)
        outer.addWidget(scroll)

        intro = QVBoxLayout()
        title = QLabel("Search & Research")
        title.setObjectName("pageTitle")
        subtitle = QLabel("Search the web through SearXNG, then turn source pages into a cited evidence summary.")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(f"color:{theme.MUTED_TEXT};font-size:12px")
        intro.addWidget(title)
        intro.addWidget(subtitle)
        root.addLayout(intro)

        connection_card = QFrame()
        connection_card.setObjectName("card")
        connection_layout = QVBoxLayout(connection_card)
        connection_layout.setContentsMargins(16, 14, 16, 16)
        connection_layout.setSpacing(10)
        heading = QHBoxLayout()
        instance_title = QLabel("SearXNG instance")
        instance_title.setStyleSheet("font-size:15px;font-weight:700")
        self.connection_status = QLabel("Not checked")
        self.connection_status.setObjectName("connectionStatus")
        self.connection_status.setStyleSheet(f"background:{theme.SURFACE};color:{theme.MUTED_TEXT};border-radius:9px;padding:5px 8px;font-size:11px")
        heading.addWidget(instance_title)
        heading.addStretch(1)
        heading.addWidget(self.connection_status)
        connection_layout.addLayout(heading)

        self.url_input = QLineEdit(load_settings().searxng_url or "")
        self.url_input.setPlaceholderText("Leave blank to use the bundled local service or detect localhost:8080")
        self.url_input.setAccessibleName("SearXNG base URL")
        self.url_input.setClearButtonEnabled(True)
        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.addRow("Base URL", self.url_input)
        connection_layout.addLayout(form)
        self.connection_detail = QLabel("Peke bundles SearXNG and runs it as a private local service. No Docker installation is required.")
        self.connection_detail.setWordWrap(True)
        self.connection_detail.setStyleSheet(f"color:{theme.MUTED_TEXT};font-size:11px")
        connection_layout.addWidget(self.connection_detail)

        connection_buttons = QHBoxLayout()
        self.save_button = QPushButton("Save URL")
        self.check_button = QPushButton("Test connection")
        self.start_local_button = QPushButton("Start bundled SearXNG")
        self.stop_local_button = QPushButton("Stop local")
        self.open_instance_button = QPushButton("Open instance")
        for button in (self.save_button, self.check_button, self.start_local_button, self.stop_local_button, self.open_instance_button):
            button.setMinimumHeight(34)
        self.save_button.clicked.connect(self.save_url)
        self.check_button.clicked.connect(lambda: self._start_operation("check"))
        self.start_local_button.clicked.connect(lambda: self._start_operation("start_local"))
        self.stop_local_button.clicked.connect(lambda: self._start_operation("stop_local"))
        self.open_instance_button.clicked.connect(self.open_instance)
        connection_buttons.addWidget(self.save_button)
        connection_buttons.addWidget(self.check_button)
        connection_buttons.addStretch(1)
        connection_buttons.addWidget(self.start_local_button)
        connection_buttons.addWidget(self.stop_local_button)
        connection_buttons.addWidget(self.open_instance_button)
        connection_layout.addLayout(connection_buttons)
        root.addWidget(connection_card)

        search_card = QFrame()
        search_card.setObjectName("card")
        search_layout = QVBoxLayout(search_card)
        search_layout.setContentsMargins(16, 14, 16, 16)
        search_layout.setSpacing(10)
        search_title = QLabel("Search the web")
        search_title.setStyleSheet("font-size:15px;font-weight:700")
        search_layout.addWidget(search_title)
        search_row = QHBoxLayout()
        self.query_input = QLineEdit()
        self.query_input.setPlaceholderText("Search across SearXNG engines…")
        self.query_input.setAccessibleName("Search query")
        self.query_input.setClearButtonEnabled(True)
        self.time_range = QComboBox()
        self.time_range.addItem("Any time", None)
        self.time_range.addItem("Past day", "day")
        self.time_range.addItem("Past month", "month")
        self.time_range.addItem("Past year", "year")
        self.search_button = QPushButton("Search")
        self.search_button.setObjectName("primaryButton")
        self.research_button = QPushButton("Research with Peke")
        self.search_button.setMinimumHeight(40)
        self.research_button.setMinimumHeight(40)
        self.search_button.clicked.connect(self.search)
        self.research_button.clicked.connect(self.research_query)
        self.query_input.returnPressed.connect(self.search)
        search_row.addWidget(self.query_input, 1)
        search_row.addWidget(self.time_range)
        search_row.addWidget(self.search_button)
        search_row.addWidget(self.research_button)
        search_layout.addLayout(search_row)
        root.addWidget(search_card)

        results_card = QFrame()
        results_card.setObjectName("card")
        results_layout = QVBoxLayout(results_card)
        results_layout.setContentsMargins(14, 12, 14, 14)
        results_layout.setSpacing(8)
        result_heading = QHBoxLayout()
        result_title = QLabel("Results")
        result_title.setStyleSheet("font-size:15px;font-weight:700")
        self.result_count = QLabel("No search performed")
        self.result_count.setStyleSheet(f"color:{theme.MUTED_TEXT};font-size:11px")
        result_heading.addWidget(result_title)
        result_heading.addStretch(1)
        result_heading.addWidget(self.result_count)
        results_layout.addLayout(result_heading)
        self.results_table = QTableWidget(0, 3)
        self.results_table.setHorizontalHeaderLabels(["Title", "Engine / host", "Preview"])
        self.results_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.results_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.results_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.results_table.setAlternatingRowColors(True)
        self.results_table.verticalHeader().setVisible(False)
        self.results_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.results_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.results_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.results_table.setMinimumHeight(210)
        self.results_table.cellDoubleClicked.connect(self._open_row)
        results_layout.addWidget(self.results_table, 2)
        action_row = QHBoxLayout()
        self.open_result_button = QPushButton("Open selected result")
        self.copy_link_button = QPushButton("Copy selected link")
        self.open_result_button.setAccessibleName("Open selected search result")
        self.copy_link_button.setAccessibleName("Copy selected search result URL")
        self.open_result_button.clicked.connect(self.open_selected_result)
        self.copy_link_button.clicked.connect(self.copy_selected_link)
        action_row.addWidget(self.open_result_button)
        action_row.addWidget(self.copy_link_button)
        action_row.addStretch(1)
        results_layout.addLayout(action_row)
        answer_label = QLabel("Research summary")
        answer_label.setStyleSheet("font-size:13px;font-weight:700")
        results_layout.addWidget(answer_label)
        self.answer_view = QPlainTextEdit()
        self.answer_view.setReadOnly(True)
        self.answer_view.setPlaceholderText("Choose ‘Research with Peke’ to fetch relevant pages and build an evidence-based summary. A local model is optional; without one, ranked source excerpts are shown.")
        self.answer_view.setMaximumBlockCount(250)
        self.answer_view.setMinimumHeight(92)
        results_layout.addWidget(self.answer_view)
        self.activity_log = QPlainTextEdit()
        self.activity_log.setReadOnly(True)
        self.activity_log.setMaximumHeight(74)
        self.activity_log.setPlaceholderText("Search and research activity will appear here.")
        results_layout.addWidget(self.activity_log)
        root.addWidget(results_card, 1)

    def save_url(self) -> None:
        url = self.url_input.text().strip().rstrip("/")
        if url:
            try:
                SearxngClient(url)
            except SearchError as exc:
                self._set_status(False, str(exc))
                return
        try:
            path = save_user_settings({"SEARXNG_URL": url})
        except OSError as exc:
            self._set_status(False, f"Could not save SearXNG URL: {exc}")
            return
        self.url_input.setText(url)
        shown = url or "automatic local detection"
        self._set_status(None, f"Saved to {path}. Active environment variables still take precedence for CLI commands.")
        self.connection_detail.setText(f"Saved instance: {shown}. Use Test connection to verify the JSON API is reachable.")

    def search(self) -> None:
        query = self.query_input.text().strip()
        if not query:
            self._set_status(False, "Enter a search query first.")
            self.query_input.setFocus()
            return
        if len(query) > 500:
            self._set_status(False, "Search queries are limited to 500 characters.")
            return
        self._start_operation("search", query=query, time_range=self.time_range.currentData())

    def research_query(self) -> None:
        query = self.query_input.text().strip()
        if not query:
            self._set_status(False, "Enter a research question first.")
            self.query_input.setFocus()
            return
        if len(query) > 500:
            self._set_status(False, "Research questions are limited to 500 characters.")
            return
        self._start_operation("research", query=query, time_range=self.time_range.currentData())

    def _start_operation(self, operation: str, *, query: str = "", time_range: str | None = None) -> None:
        if self._thread is not None:
            self._append_activity("An operation is already running; wait for it to finish.")
            return
        self._set_busy(True, operation)
        worker_thread = QThread(self)
        worker = SearchWorker(operation, self.url_input.text().strip(), query, time_range)
        worker.moveToThread(worker_thread)
        worker_thread.started.connect(worker.run)
        worker.progress.connect(self._on_progress)
        worker.finished.connect(self._on_operation_finished)
        worker.finished.connect(worker_thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker_thread.finished.connect(self._on_thread_finished)
        worker_thread.finished.connect(worker_thread.deleteLater)
        self._thread, self._worker = worker_thread, worker
        worker_thread.start()

    @Slot(str, str, str)
    def _on_progress(self, level: str, message: str, tag: str) -> None:
        self._append_activity(f"[{tag or 'SEARCH'}] {message}")

    @Slot(object)
    def _on_operation_finished(self, payload: dict) -> None:
        operation = payload.get("operation", "")
        if payload.get("error"):
            self._set_status(False, payload["error"])
            self._append_activity(f"[ERROR] {payload['error']}")
            # Keep controls disabled until the worker thread has actually exited.
            return
        if operation == "check":
            status = payload.get("status", {})
            connected = bool(payload.get("connected"))
            self._set_status(connected, self._status_text(status))
            if connected:
                self._active_url = str(status.get("url") or "") or None
                self.connection_detail.setText(f"Connected to {status.get('url')}. SearXNG returned a valid results list.")
            return
        if operation == "search":
            search_status = payload.get("status", {})
            if not isinstance(search_status, dict):
                search_status = {"available": False, "reason": "Malformed connection status."}
            connected = bool(search_status.get("available"))
            self._set_status(connected, self._status_text(search_status))
            if connected:
                self._active_url = str(search_status.get("url") or "") or None
            hits = payload.get("hits", [])
            if not isinstance(hits, list):
                hits = []
            self._populate_results(hits)
            visible_count = self.results_table.rowCount()
            self.result_count.setText(f"{visible_count} result(s)")
            if not visible_count:
                if not connected:
                    self.answer_view.setPlainText("Search is unavailable. Check the SearXNG URL, enable its JSON search format, or start bundled SearXNG.")
                else:
                    self.answer_view.setPlainText("No results were returned. The instance may be reachable but configured search engines did not return matches.")
            else:
                self.answer_view.clear()
            self._append_activity(f"[SEARCH] Received {len(hits)} result(s).")
            return
        if operation == "research":
            result = payload.get("result", {})
            if not isinstance(result, dict):
                result = {}
            sources = result.get("sources", [])
            if not isinstance(sources, list):
                sources = []
            self._populate_results(sources)
            situation = result.get("situation")
            search_info = situation.get("search") if isinstance(situation, dict) else None
            source_url = search_info.get("url") if isinstance(search_info, dict) else None
            self._active_url = str(source_url or self.url_input.text().strip() or self._active_url or "") or None
            answer = result.get("answer")
            answer = answer if isinstance(answer, dict) else {}
            lines = []
            answer_text = answer.get("answer")
            if isinstance(answer_text, str) and answer_text.strip():
                lines.extend([answer_text.strip(), "", f"Confidence: {answer.get('confidence', 'not assessed')}"])
                gaps = answer.get("gaps")
                if gaps:
                    lines.extend(["", f"Evidence gaps: {gaps}"])
            else:
                lines.append("Peke could not produce a generated answer. Review the ranked source excerpts below; no unsupported answer was invented.")
            notes = result.get("notes", [])
            if isinstance(notes, list) and notes:
                lines.extend(["", "Notes:", *[f"• {str(note)[:1000]}" for note in notes[:30]]])
            self.answer_view.setPlainText("\n".join(lines))
            try:
                elapsed = max(0.0, float(result.get("elapsed_seconds", 0) or 0))
            except (TypeError, ValueError):
                elapsed = 0.0
            self.result_count.setText(f"{len(sources)} source(s) · {elapsed:g}s")
            self._set_status(None, "Research finished. Review the linked sources and the evidence gaps before relying on the answer.")
            self._append_activity("[RESEARCH] Research run finished.")
            return
        if operation == "start_local":
            service = payload.get("service", {})
            service = service if isinstance(service, dict) else {}
            already_running = bool(service.get("already_running"))
            prefix = "Local SearXNG was already running" if already_running else "Local SearXNG started"
            self.url_input.setText(BASE_URL)
            self._active_url = BASE_URL
            try:
                save_user_settings({"SEARXNG_URL": BASE_URL})
            except OSError as exc:
                self._set_status(True, f"{prefix} at {BASE_URL}, but the URL could not be saved: {exc}")
                self._append_activity(f"[WARN] SearXNG is available, but settings could not be saved: {exc}")
            else:
                self._set_status(True, f"{prefix} at {BASE_URL}.")
            self.connection_detail.setText(f"Bundled SearXNG is running privately at {BASE_URL}; it is bound to loopback only. No Docker daemon is used.")
            self._append_activity(f"[SEARXNG] {prefix}.")
            return
        if operation == "stop_local":
            service = payload.get("service", {})
            self._set_status(None, str(service.get("message", "Local service stop completed.")))
            self._append_activity(f"[SEARXNG] {service.get('message', 'Local service stop completed.')}")
            return

    def _on_thread_finished(self) -> None:
        thread = self.sender()
        if thread is self._thread:
            self._thread = None
            self._worker = None
        self._set_busy(False, "")

    def _set_busy(self, busy: bool, operation: str) -> None:
        for button in (self.save_button, self.check_button, self.start_local_button, self.stop_local_button,
                       self.search_button, self.research_button):
            button.setEnabled(not busy)
        if busy:
            self.connection_status.setText({"check": "Checking…", "search": "Searching…", "research": "Researching…",
                                            "start_local": "Starting…", "stop_local": "Stopping…"}.get(operation, "Working…"))

    def _set_status(self, connected: bool | None, detail: str) -> None:
        if connected is True:
            background, foreground, label = theme.SAGE, "white", "Connected"
        elif connected is False:
            background, foreground, label = theme.TERRACOTTA, "white", "Unavailable"
        else:
            background, foreground, label = theme.SURFACE, theme.MUTED_TEXT, "Status"
        self.connection_status.setText(label)
        self.connection_status.setStyleSheet(f"background:{background};color:{foreground};border-radius:9px;padding:5px 8px;font-size:11px")
        self.connection_detail.setText(detail)

    @staticmethod
    def _status_text(status: dict) -> str:
        url = status.get("url") or "local SearXNG"
        reason = status.get("reason", "unknown status")
        return f"{url} · {reason}"

    def _populate_results(self, hits: list[dict]) -> None:
        self.results_table.setRowCount(0)
        if not isinstance(hits, list):
            return
        for hit in hits:
            if not isinstance(hit, dict):
                continue
            url = str(hit.get("url", ""))
            try:
                parts = urlsplit(url)
                _ = parts.port
            except ValueError:
                continue
            if (
                len(url) > MAX_URL_LENGTH
                or parts.scheme.lower() not in {"http", "https"}
                or not parts.hostname
                or not parts.netloc
                or parts.username is not None
                or parts.password is not None
                or any(char.isspace() or ord(char) < 32 for char in url)
            ):
                continue
            row = self.results_table.rowCount()
            self.results_table.insertRow(row)
            title_item = QTableWidgetItem(str(hit.get("title") or url)[:200])
            title_item.setData(Qt.ItemDataRole.UserRole, url)
            title_item.setToolTip(url)
            engine = str(hit.get("engine") or hit.get("via") or "").strip()
            source = f"{engine} · {parts.netloc}" if engine else parts.netloc
            source_item = QTableWidgetItem(source)
            source_item.setToolTip(url)
            snippet = str(hit.get("snippet") or hit.get("excerpt") or hit.get("content") or "").replace("\x00", "")[:700]
            preview_item = QTableWidgetItem(snippet)
            preview_item.setToolTip(snippet)
            self.results_table.setItem(row, 0, title_item)
            self.results_table.setItem(row, 1, source_item)
            self.results_table.setItem(row, 2, preview_item)
            self.results_table.setRowHeight(row, 54)
        if self.results_table.rowCount():
            self.results_table.selectRow(0)

    def _selected_result_url(self) -> str | None:
        row = self.results_table.currentRow()
        if row < 0:
            return None
        item = self.results_table.item(row, 0)
        url = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        return str(url) if url else None

    def open_selected_result(self) -> None:
        url = self._selected_result_url()
        if url:
            QDesktopServices.openUrl(QUrl(url))

    def _open_row(self, row: int, _column: int) -> None:
        self.results_table.selectRow(row)
        self.open_selected_result()

    def copy_selected_link(self) -> None:
        url = self._selected_result_url()
        if url:
            from PySide6.QtGui import QGuiApplication

            QGuiApplication.clipboard().setText(url)
            self._append_activity("[COPY] Selected source URL copied to the clipboard.")

    def open_instance(self) -> None:
        url = self.url_input.text().strip().rstrip("/") or self._active_url or BASE_URL
        try:
            client = SearxngClient(url)
        except SearchError as exc:
            self._set_status(False, str(exc))
            return
        QDesktopServices.openUrl(QUrl(client.base_url))

    def _append_activity(self, message: str) -> None:
        self.activity_log.appendPlainText(message[:1000])
        document = self.activity_log.document()
        while document.blockCount() > 100:
            cursor = self.activity_log.textCursor()
            cursor.movePosition(cursor.MoveOperation.Start)
            cursor.select(cursor.SelectionType.BlockUnderCursor)
            cursor.removeSelectedText()
            cursor.deleteChar()
