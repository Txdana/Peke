"""Endpoint tree widget for Peke GUI."""

from collections.abc import Callable
from urllib.parse import urlparse

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHeaderView,
    QLabel,
    QPushButton,
    QSplitter,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)


class EndpointTreeWidget(QWidget):
    """Collapsible tree grouping discovered endpoints by host and path segments."""

    def __init__(
        self,
        on_use_endpoint: Callable[[str, str, dict, dict], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.on_use_endpoint = on_use_endpoint
        self.init_ui()

    def init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)

        # Tree Widget
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Method / Path", "Size", "Source"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        splitter.addWidget(self.tree)

        # Popover / Detail Panel
        self.detail_panel = QWidget()
        detail_layout = QVBoxLayout(self.detail_panel)
        detail_layout.setContentsMargins(10, 10, 10, 10)

        self.detail_title = QLabel("Select an endpoint to inspect details")
        self.detail_title.setStyleSheet("font-weight: bold; color: #2D5A4C;")
        detail_layout.addWidget(self.detail_title)

        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        detail_layout.addWidget(self.detail_text)

        self.use_btn = QPushButton("Use this endpoint")
        self.use_btn.setEnabled(False)
        self.use_btn.clicked.connect(self._on_use_clicked)
        detail_layout.addWidget(self.use_btn)

        splitter.addWidget(self.detail_panel)
        splitter.setSizes([350, 250])

        self.tree.itemSelectionChanged.connect(self._on_selection_changed)
        self._current_selected_hint: dict | None = None

    def populate_endpoints(self, endpoints: list[dict]) -> None:
        """Populate tree grouped by host and path segments.

        :param endpoints: List of endpoint dicts or EndpointHint models.
        """
        self.tree.clear()
        hosts_map: dict[str, QTreeWidgetItem] = {}

        for ep in endpoints:
            if hasattr(ep, "model_dump"):
                ep_data = ep.model_dump()
            elif isinstance(ep, dict):
                ep_data = ep
            else:
                continue

            path = ep_data.get("path") or ep_data.get("url") or "/"
            parsed = urlparse(path)
            host = parsed.netloc or "Discovered Host"
            path_str = parsed.path or path

            if host not in hosts_map:
                host_item = QTreeWidgetItem(self.tree, [host, "", ""])
                host_item.setExpanded(True)
                hosts_map[host] = host_item

            host_item = hosts_map[host]

            method = ep_data.get("method", "GET").upper()
            size = str(ep_data.get("size") or "-")
            disc_by = str(ep_data.get("discovered_by") or ep_data.get("source") or "profile").lower()
            hidden = bool(ep_data.get("hidden", False))

            if disc_by == "rea":
                source_tag = "[REA Discovered]"
            else:
                source_tag = "[Profile]"

            if hidden:
                source_tag += " (Hidden)"

            item_text = f"{method}  {path_str}"
            item = QTreeWidgetItem(host_item, [item_text, size, source_tag])
            item.setData(0, Qt.UserRole, ep_data)

    def _on_selection_changed(self) -> None:
        selected = self.tree.selectedItems()
        if not selected:
            self.detail_title.setText("Select an endpoint to inspect details")
            self.detail_text.clear()
            self.use_btn.setEnabled(False)
            self._current_selected_hint = None
            return

        item = selected[0]
        data = item.data(0, Qt.UserRole)
        if not data or not isinstance(data, dict):
            self.detail_title.setText("Group Folder")
            self.detail_text.clear()
            self.use_btn.setEnabled(False)
            self._current_selected_hint = None
            return

        self._current_selected_hint = data
        method = data.get("method", "GET")
        path = data.get("path") or data.get("url") or "/"
        headers = data.get("headers") or {}
        params = data.get("parameters") or data.get("params") or {}
        note = data.get("note") or ""

        self.detail_title.setText(f"{method} {path}")

        details_md = f"**Headers:**\n{headers}\n\n**Parameters:**\n{params}\n"
        if note:
            details_md += f"\n**Note:** {note}"

        self.detail_text.setPlainText(details_md)
        self.use_btn.setEnabled(True)

    def _on_use_clicked(self) -> None:
        if self._current_selected_hint and self.on_use_endpoint:
            data = self._current_selected_hint
            method = data.get("method", "GET")
            path = data.get("path") or data.get("url") or "/"
            headers = data.get("headers") or {}
            params = data.get("parameters") or data.get("params") or {}
            self.on_use_endpoint(path, method, headers, params)
