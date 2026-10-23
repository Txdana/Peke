"""Bounded event console with stage/level filtering and log export."""
from datetime import datetime
from pathlib import Path
from typing import Any
from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QComboBox, QFileDialog, QFrame, QHBoxLayout, QPlainTextEdit, QPushButton, QVBoxLayout
from peke.gui import theme


class ExecutionConsole(QFrame):
    MAX_LINES = 5000

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("consoleCard")
        self._events: list[tuple[Any, str]] = []
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 10, 12, 12)
        top = QHBoxLayout()
        title = QPushButton("Execution Console")
        title.setEnabled(False)
        title.setStyleSheet("text-align:left; border:0; background:transparent; font-weight:700; padding:2px")
        self.filter = QComboBox()
        self.filter.addItems(["All", "Info", "Warn", "Error"])
        self.filter.setAccessibleName("Filter console events")
        self.filter.currentTextChanged.connect(self._render)
        self.copy_button = QPushButton("Copy log")
        self.copy_button.clicked.connect(self.copy_log)
        self.save_button = QPushButton("Save log")
        self.save_button.clicked.connect(self.save_log)
        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self.clear)
        top.addWidget(title)
        top.addStretch(1)
        top.addWidget(self.filter)
        top.addWidget(self.copy_button)
        top.addWidget(self.save_button)
        top.addWidget(self.clear_button)
        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setMaximumBlockCount(self.MAX_LINES)
        self.text.setObjectName("executionConsole")
        self.text.setStyleSheet(f"background:{theme.CONSOLE_BG}; color:{theme.WHITE}; border:0; border-radius:8px; font-family:'IBM Plex Mono',monospace; font-size:12.5px")
        outer.addLayout(top)
        outer.addWidget(self.text, 1)

    def clear(self) -> None:
        self._events.clear()
        self.text.clear()

    def append_event(self, event: Any) -> None:
        self._events.append((event, self._line(event)))
        self._events = self._events[-self.MAX_LINES:]
        self._render()

    def _line(self, event: Any) -> str:
        timestamp = getattr(event, "ts", None) or datetime.now().isoformat()
        try:
            stamp = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00")).strftime("%H:%M:%S")
        except ValueError:
            stamp = datetime.now().strftime("%H:%M:%S")
        tag = getattr(event, "tag", None)
        return f"[{stamp}] {f'[{tag}] ' if tag else ''}{getattr(event, 'message', event)}"

    def _render(self, *_args) -> None:
        scrollbar = self.text.verticalScrollBar()
        follow = scrollbar.value() >= scrollbar.maximum() - 2
        selected = self.filter.currentText().lower()
        self.text.clear()
        cursor = self.text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        for event, line in self._events:
            level = str(getattr(event, "level", "info")).lower()
            if selected != "all" and level != selected:
                continue
            timestamp_end = line.find("]") + 1
            stamp_fmt = QTextCharFormat(); stamp_fmt.setForeground(QColor(theme.CONSOLE_TIMESTAMP))
            cursor.insertText(line[:timestamp_end], stamp_fmt)
            rest = line[timestamp_end:]
            tag_fmt = QTextCharFormat(); tag_fmt.setForeground(QColor(theme.CONSOLE_HIGHLIGHT))
            if rest.startswith(" [") and "]" in rest:
                end = rest.find("]") + 1
                cursor.insertText(rest[:end], tag_fmt)
                rest = rest[end:]
            msg_fmt = QTextCharFormat()
            msg_fmt.setForeground(QColor(theme.CONSOLE_HIGHLIGHT if level == "error" else theme.CONSOLE_MUTED_TEXT if level == "warn" else theme.WHITE))
            cursor.insertText(rest + "\n", msg_fmt)
        self.text.setTextCursor(cursor)
        if follow:
            scrollbar.setValue(scrollbar.maximum())

    def copy_log(self) -> None:
        from PySide6.QtGui import QGuiApplication
        QGuiApplication.clipboard().setText("\n".join(line for _event, line in self._events))

    def save_log(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save execution log", "peke.log", "Log files (*.log *.txt)")
        if path:
            try:
                Path(path).write_text("\n".join(line for _event, line in self._events) + "\n", encoding="utf-8")
            except OSError as exc:
                self.append_event(type("LogEvent", (), {"level": "error", "message": f"Could not save log: {exc}", "tag": "SAVE"})())
