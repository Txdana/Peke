"""Syntax-highlighted JSON viewer with search and line numbers for Peke GUI."""

import json
import re

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QKeySequence,
    QPainter,
    QShortcut,
    QSyntaxHighlighter,
    QTextCharFormat,
)
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class JsonHighlighter(QSyntaxHighlighter):
    """QSyntaxHighlighter for JSON formatting with specified palette colors:

    Keys: #2D5A4C
    Numbers / Booleans / Null: #B04A24
    Strings: #2C2523
    Punctuation: muted (#808080)
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.rules = []

        # Key format (#2D5A4C)
        key_fmt = QTextCharFormat()
        key_fmt.setForeground(QColor("#2D5A4C"))
        key_fmt.setFontWeight(QFont.Weight.Bold)
        self.rules.append((re.compile(r'"[^"\\]*"\s*(?=\:)'), key_fmt))

        # String value format (#2C2523)
        str_fmt = QTextCharFormat()
        str_fmt.setForeground(QColor("#2C2523"))
        self.rules.append((re.compile(r':\s*("[^"\\]*")'), str_fmt))

        # Number / Boolean / Null format (#B04A24)
        num_fmt = QTextCharFormat()
        num_fmt.setForeground(QColor("#B04A24"))
        num_fmt.setFontWeight(QFont.Weight.Bold)
        self.rules.append((re.compile(r'\b(-?\d+(\.\d+)?([eE][+-]?\d+)?|true|false|null)\b'), num_fmt))

        # Punctuation format (#808080)
        punc_fmt = QTextCharFormat()
        punc_fmt.setForeground(QColor("#808080"))
        self.rules.append((re.compile(r'[\{\}\[\]\:\,]'), punc_fmt))

    def highlightBlock(self, text: str) -> None:
        for pattern, fmt in self.rules:
            for match in pattern.finditer(text):
                start, end = match.span()
                self.setFormat(start, end - start, fmt)


class LineNumberGutter(QWidget):
    """Line numbers gutter sidebar for JSON editor."""

    def __init__(self, editor: "CodeEditor") -> None:
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self) -> QSize:
        return QSize(self.editor.line_number_area_width(), 0)

    def paintEvent(self, event) -> None:
        self.editor.line_number_area_paint_event(event)


class CodeEditor(QPlainTextEdit):
    """QPlainTextEdit with custom line number gutter sidebar."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.line_number_area = LineNumberGutter(self)

        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)

        self.update_line_number_area_width(0)

    def line_number_area_width(self) -> int:
        digits = max(1, len(str(self.blockCount())))
        space = 10 + self.fontMetrics().horizontalAdvance("9") * digits
        return space

    def update_line_number_area_width(self, new_block_count: int) -> None:
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def update_line_number_area(self, rect: QRect, dy: int) -> None:
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())

        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width(0)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height()))

    def line_number_area_paint_event(self, event) -> None:
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), QColor("#181818"))

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())

        painter.setPen(QColor("#666666"))
        painter.setFont(self.font())

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.drawText(
                    0,
                    top,
                    self.line_number_area.width() - 5,
                    self.fontMetrics().height(),
                    Qt.AlignmentFlag.AlignRight,
                    number,
                )

            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            block_number += 1


class JsonViewWidget(QWidget):
    """Pretty-printed JSON view widget with line numbers gutter and 1MB+ output safety."""

    LARGE_PAYLOAD_LIMIT = 500000  # 500 KB limit for initial highlight

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._raw_json_str = ""
        self.init_ui()

    def init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Search Bar Toolbar
        self.search_bar = QWidget()
        search_layout = QHBoxLayout(self.search_bar)
        search_layout.setContentsMargins(5, 5, 5, 5)

        search_layout.addWidget(QLabel("Find:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search JSON (Ctrl+F)...")
        self.search_input.returnPressed.connect(self.search_next)
        search_layout.addWidget(self.search_input)

        self.find_next_btn = QPushButton("Next")
        self.find_next_btn.clicked.connect(self.search_next)
        search_layout.addWidget(self.find_next_btn)

        self.show_all_btn = QPushButton("Show All Payload")
        self.show_all_btn.setVisible(False)
        self.show_all_btn.clicked.connect(self._show_full_payload)
        search_layout.addWidget(self.show_all_btn)

        self.search_bar.setVisible(False)
        layout.addWidget(self.search_bar)

        # Editor with Line Numbers Gutter
        self.editor = CodeEditor()
        self.editor.setReadOnly(True)
        self.editor.setFont(QFont("Monospace", 10))
        self.editor.setStyleSheet("background-color: #1E1E1E; color: #D4D4D4;")

        self.highlighter = JsonHighlighter(self.editor.document())

        layout.addWidget(self.editor)

        # Shortcut for Ctrl+F
        shortcut = QShortcut(QKeySequence("Ctrl+F"), self)
        shortcut.activated.connect(self.toggle_search_bar)

    def set_json(self, data: dict | list | str) -> None:
        """Pretty-print and display JSON data smoothly.

        :param data: JSON payload dictionary, list, or string.
        """
        if isinstance(data, str):
            try:
                data = json.loads(data)
                self._raw_json_str = json.dumps(data, indent=2)
            except Exception:
                self._raw_json_str = data
        else:
            self._raw_json_str = json.dumps(data, indent=2)

        if len(self._raw_json_str) > self.LARGE_PAYLOAD_LIMIT:
            truncated = self._raw_json_str[: self.LARGE_PAYLOAD_LIMIT] + "\n\n... [Large JSON payload truncated for performance]"
            self.editor.setPlainText(truncated)
            self.show_all_btn.setVisible(True)
        else:
            self.editor.setPlainText(self._raw_json_str)
            self.show_all_btn.setVisible(False)

    def _show_full_payload(self) -> None:
        self.editor.setPlainText(self._raw_json_str)
        self.show_all_btn.setVisible(False)

    def toggle_search_bar(self) -> None:
        self.search_bar.setVisible(not self.search_bar.isVisible())
        if self.search_bar.isVisible():
            self.search_input.setFocus()

    def search_next(self) -> None:
        query = self.search_input.text()
        if query:
            self.editor.find(query)
