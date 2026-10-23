"""Console logging widget with filtering and line capping for Peke GUI."""

from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from peke.pipeline import PipelineEvent


class ConsoleWidget(QWidget):
    """Stage-aware console display with filtering, copy/save, and 5000-line cap."""

    MAX_LINES = 5000

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.all_events: list[PipelineEvent] = []
        self.init_ui()

    def init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("Console Log:"))

        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["All", "Info", "Warning", "Error", "Success"])
        self.filter_combo.currentTextChanged.connect(self.refresh_display)
        toolbar.addWidget(self.filter_combo)

        toolbar.addStretch()

        self.copy_btn = QPushButton("Copy log")
        self.copy_btn.clicked.connect(self.copy_log)
        toolbar.addWidget(self.copy_btn)

        self.save_btn = QPushButton("Save log")
        self.save_btn.clicked.connect(self.save_log)
        toolbar.addWidget(self.save_btn)

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.clicked.connect(self.clear_log)
        toolbar.addWidget(self.clear_btn)

        layout.addLayout(toolbar)

        # Log Display Area
        self.text_edit = QPlainTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setMaximumBlockCount(self.MAX_LINES)
        self.text_edit.setStyleSheet("font-family: monospace; background-color: #181818; color: #D4D4D4;")
        layout.addWidget(self.text_edit)

    def add_event(self, event: PipelineEvent) -> None:
        """Append a pipeline log event to the console widget."""
        self.all_events.append(event)
        filter_text = self.filter_combo.currentText().upper()

        if filter_text != "ALL" and event.level.upper() != filter_text:
            return

        self._append_formatted(event)

    def _append_formatted(self, event: PipelineEvent) -> None:
        level_icons = {
            "INFO": "ℹ️",
            "WARNING": "⚠️",
            "ERROR": "❌",
            "SUCCESS": "✅",
        }
        level_colors = {
            "INFO": "#569CD6",
            "WARNING": "#D7BA7D",
            "ERROR": "#F44747",
            "SUCCESS": "#4EC9B0",
        }

        icon = level_icons.get(event.level.upper(), "🔹")
        color = level_colors.get(event.level.upper(), "#D4D4D4")

        html_msg = (
            f"<span style='color: #808080;'>[{event.timestamp}]</span> "
            f"<span style='color: #C586C0;'>[{event.stage}]</span> "
            f"{icon} <span style='color: {color}; font-weight: bold;'>{event.message}</span>"
        )
        self.text_edit.appendHtml(html_msg)

    def refresh_display(self) -> None:
        """Re-render log display based on selected filter."""
        self.text_edit.clear()
        filter_text = self.filter_combo.currentText().upper()

        for ev in self.all_events:
            if filter_text == "ALL" or ev.level.upper() == filter_text:
                self._append_formatted(ev)

    def clear_log(self) -> None:
        self.all_events.clear()
        self.text_edit.clear()

    def copy_log(self) -> None:
        self.text_edit.selectAll()
        self.text_edit.copy()

    def save_log(self) -> None:
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Console Log", "peke_log.txt", "Text Files (*.txt);;All Files (*)"
        )
        if file_path:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(self.text_edit.toPlainText())
