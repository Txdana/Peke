"""Sub-agents activity, run history, and JSON output UI pane."""
import json
import logging
from pathlib import Path

from PySide6.QtCore import QFileSystemWatcher, Qt, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from peke.gui import theme
from peke.gui.widgets.json_view import JsonView

logger = logging.getLogger(__name__)


class SubagentsPane(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.runs_dir = Path.home() / ".peke" / "runs"
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self.reveal_secrets = False

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # Header bar
        header = QHBoxLayout()
        title = QLabel("Sub-Agent Reconnaissance Activity")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch(1)

        self.reveal_checkbox = QCheckBox("Reveal secret token values (session)")
        self.reveal_checkbox.stateChanged.connect(self._on_reveal_toggled)
        header.addWidget(self.reveal_checkbox)
        root.addLayout(header)

        # Splitter: Left runs table, Right JSON details
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left table card
        table_card = QFrame()
        table_card.setStyleSheet(f"QFrame {{ background: {theme.SURFACE}; border-radius: 12px; }}")
        tc_layout = QVBoxLayout(table_card)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Run ID", "Target URL", "Provider", "Status", "Duration"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.itemSelectionChanged.connect(self._on_run_selected)
        tc_layout.addWidget(self.table)

        # Right JSON details card
        details_card = QFrame()
        details_card.setStyleSheet(f"QFrame {{ background: {theme.SURFACE}; border-radius: 12px; }}")
        dc_layout = QVBoxLayout(details_card)

        dc_title = QLabel("Structured Output & Synthesis")
        dc_title.setStyleSheet("font-size: 14px; font-weight: bold;")
        dc_layout.addWidget(dc_title)

        self.json_view = JsonView()
        dc_layout.addWidget(self.json_view)

        splitter.addWidget(table_card)
        splitter.addWidget(details_card)
        splitter.setSizes([500, 500])

        root.addWidget(splitter)

        # File watcher for ~/.peke/runs/
        self.watcher = QFileSystemWatcher(self)
        self.watcher.addPath(str(self.runs_dir))
        self.watcher.directoryChanged.connect(self.refresh_runs)

        self.refresh_runs()

    def _on_reveal_toggled(self, state: int) -> None:
        if state == Qt.CheckState.Checked.value:
            confirm = QMessageBox.question(
                self,
                "Reveal Secret Values",
                "Displaying secret token values in the GUI may expose sensitive credentials. Enable secret display for this session?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if confirm == QMessageBox.StandardButton.Yes:
                self.reveal_secrets = True
            else:
                self.reveal_checkbox.setChecked(False)
                self.reveal_secrets = False
        else:
            self.reveal_secrets = False
        self._on_run_selected()

    @Slot()
    def refresh_runs(self) -> None:
        self.table.setRowCount(0)
        if not self.runs_dir.exists():
            return

        run_files = sorted(self.runs_dir.glob("*/subagents.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        for p in run_files:
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                row = self.table.rowCount()
                self.table.insertRow(row)

                run_id = data.get("run_id", p.parent.name)
                target = data.get("target_url", "unknown")
                provider = data.get("provider", "unknown")
                status = "OK" if data.get("ok") else "FAILED"
                dur = f"{data.get('duration_seconds', 0.0):.2f}s"

                item_id = QTableWidgetItem(run_id)
                item_id.setData(Qt.ItemDataRole.UserRole, str(p))

                self.table.setItem(row, 0, item_id)
                self.table.setItem(row, 1, QTableWidgetItem(target))
                self.table.setItem(row, 2, QTableWidgetItem(provider))
                self.table.setItem(row, 3, QTableWidgetItem(status))
                self.table.setItem(row, 4, QTableWidgetItem(dur))
            except Exception as exc:
                logger.debug("Could not parse subagent run file %s: %s", p, exc)

    def _on_run_selected(self) -> None:
        selected = self.table.selectedItems()
        if not selected:
            self.json_view.set_json("{}")
            return

        first_item = self.table.item(selected[0].row(), 0)
        filepath = first_item.data(Qt.ItemDataRole.UserRole)
        if not filepath or not Path(filepath).is_file():
            return

        try:
            data = json.loads(Path(filepath).read_text(encoding="utf-8"))
            if not self.reveal_secrets and "auth" in data and "tokens" in data["auth"]:
                # Mask token values
                tokens = data["auth"]["tokens"]
                for t in tokens:
                    if "value" in t and not t.get("redacted"):
                        t["value"] = f"[REDACTED len={len(t['value'])}]"
            self.json_view.set_json(json.dumps(data, indent=2))
        except Exception as exc:
            self.json_view.set_json(f'{{"error": "Could not read run file: {exc}"}}')
