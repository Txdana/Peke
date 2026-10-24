"""Live, host/path-grouped endpoint hint tree."""
from urllib.parse import urlparse

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)


class EndpointTree(QTreeWidget):
    endpoint_selected = Signal(dict)
    use_endpoint = Signal(dict)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setColumnCount(3)
        self.setHeaderLabels(["Method / Path", "Size", "Source"])
        self.setAlternatingRowColors(False)
        self.setUniformRowHeights(True)
        self.header().setStretchLastSection(True)
        self.itemSelectionChanged.connect(self._selection_changed)
        self.itemDoubleClicked.connect(self._show_details)
        self._hints: list[dict] = []

    def set_endpoints(self, endpoints: list[dict]) -> None:
        self.clear()
        self._hints = endpoints
        hosts: dict[str, QTreeWidgetItem] = {}
        groups: dict[tuple[str, str], QTreeWidgetItem] = {}
        for hint in endpoints:
            path = str(hint.get("path", "/"))
            parsed = urlparse(path)
            host = parsed.netloc or "Target host"
            path = parsed.path or path or "/"
            if host not in hosts:
                root = QTreeWidgetItem([host, "", "Host"])
                root.setFlags(root.flags() & ~Qt.ItemFlag.ItemIsSelectable)
                self.addTopLevelItem(root)
                hosts[host] = root
            parts = [part for part in path.split("/") if part]
            parent = hosts[host]
            accumulated = ""
            for segment in parts[:-1]:
                accumulated += "/" + segment
                key = (host, accumulated)
                if key not in groups:
                    node = QTreeWidgetItem([segment + "/", "", "Path"])
                    node.setFlags(node.flags() & ~Qt.ItemFlag.ItemIsSelectable)
                    parent.addChild(node)
                    groups[key] = node
                parent = groups[key]
            leaf = QTreeWidgetItem([f"{hint.get('method', 'GET')}  {path}", str(hint.get("size") or "—"),
                                    "REA Discovered" if hint.get("discovered_by") == "rea" else "Profile"])
            leaf.setData(0, Qt.ItemDataRole.UserRole, hint)
            if hint.get("discovered_by") == "rea":
                leaf.setForeground(2, Qt.GlobalColor.darkGreen)
            if hint.get("hidden"):
                leaf.setText(2, leaf.text(2) + " · Hidden")
            parent.addChild(leaf)
        self.expandToDepth(0)
        for col in range(3):
            self.resizeColumnToContents(col)

    def _selection_changed(self) -> None:
        item = self.currentItem()
        hint = item.data(0, Qt.ItemDataRole.UserRole) if item else None
        if isinstance(hint, dict):
            self.endpoint_selected.emit(hint)

    def _show_details(self, item: QTreeWidgetItem, column: int) -> None:
        hint = item.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(hint, dict):
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Endpoint details")
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(f"{hint.get('method', 'GET')} {hint.get('path', '')}"))
        details = QLabel(f"Headers: {hint.get('headers', {})}\nParameters: {hint.get('params', {})}\nNote: {hint.get('note') or '—'}")
        details.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(details)
        actions = QHBoxLayout()
        use = QPushButton("Use this endpoint")
        use.clicked.connect(lambda: (self.use_endpoint.emit(hint), dialog.accept()))
        close = QPushButton("Close")
        close.clicked.connect(dialog.accept)
        actions.addWidget(use)
        actions.addWidget(close)
        layout.addLayout(actions)
        dialog.exec()
