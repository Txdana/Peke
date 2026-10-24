"""JSON editor with lightweight syntax highlighting, line numbers and search."""
import json
import re

from PySide6.QtCore import Qt
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
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from peke.gui import theme


class JsonHighlighter(QSyntaxHighlighter):
    def __init__(self, document) -> None:
        super().__init__(document)
        self.rules: list[tuple[re.Pattern[str], QTextCharFormat]] = []
        for pattern, color, bold in [
            (r'"(?:\\.|[^"\\])*"(?=\\s*:)', theme.SAGE, True),
            (r'"(?:\\.|[^"\\])*"', theme.TEXT, False),
            (r'\b(?:true|false|null)\b|-?\b\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\b', theme.JSON_NUMBER, False),
            (r'[{}\[\],:]', theme.MUTED_TEXT, False),
        ]:
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color))
            fmt.setFontWeight(QFont.Weight.Bold if bold else QFont.Weight.Normal)
            self.rules.append((re.compile(pattern), fmt))

    def highlightBlock(self, text: str) -> None:
        for pattern, fmt in self.rules:
            for match in pattern.finditer(text):
                self.setFormat(match.start(), match.end() - match.start(), fmt)


class LineNumberArea(QWidget):
    def __init__(self, editor: "JsonTextEdit") -> None:
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        return self.editor.line_number_area_width(), 0

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(event.rect(), QColor(theme.SURFACE))
        block = self.editor.firstVisibleBlock()
        number = block.blockNumber()
        top = int(self.editor.blockBoundingGeometry(block).translated(self.editor.contentOffset()).top())
        bottom = top + int(self.editor.blockBoundingRect(block).height())
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.setPen(QColor(theme.MUTED_TEXT))
                painter.drawText(0, top, self.width() - 5, self.editor.fontMetrics().height(), Qt.AlignmentFlag.AlignRight, str(number + 1))
            block = block.next()
            top = bottom
            bottom = top + int(self.editor.blockBoundingRect(block).height())
            number += 1


class JsonTextEdit(QPlainTextEdit):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.line_number_area = LineNumberArea(self)
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.update_line_number_area_width()
        self.highlighter = JsonHighlighter(self.document())
        self._all_text = ""
        self._show_all = False
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setStyleSheet("font-family:'IBM Plex Mono',monospace;font-size:12px;padding-left:5px")

    def line_number_area_width(self) -> int:
        return 10 + self.fontMetrics().horizontalAdvance("9") * len(str(max(1, self.blockCount())))

    def update_line_number_area_width(self, *_args) -> None:
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def update_line_number_area(self, rect, dy) -> None:
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(cr.left(), cr.top(), self.line_number_area_width(), cr.height())

    def set_json(self, text: str) -> None:
        self._all_text = text
        if len(text) > 1_000_000 and not self._show_all:
            self.setPlainText(text[:1_000_000] + "\n\n/* Preview limited to 1 MB. Use Show all to display the full output. */")
        else:
            self.setPlainText(text)

    def show_all(self) -> None:
        self._show_all = True
        self.setPlainText(self._all_text)


class JsonView(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        search_row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Find in JSON… (Ctrl+F)")
        self.search.setAccessibleName("Search JSON output")
        self.find_next = QPushButton("Find next")
        self.show_all_button = QPushButton("Show all")
        self.show_all_button.hide()
        self.show_all_button.clicked.connect(self.show_all)
        self.find_next.clicked.connect(self.find_text)
        search_row.addWidget(self.search, 1)
        search_row.addWidget(self.find_next)
        search_row.addWidget(self.show_all_button)
        layout.addLayout(search_row)
        self.editor = JsonTextEdit()
        self.editor.setReadOnly(True)
        layout.addWidget(self.editor, 1)
        self.search.returnPressed.connect(self.find_text)
        self.find_shortcut = QShortcut(QKeySequence.StandardKey.Find, self)
        self.find_shortcut.activated.connect(self._focus_search)

    def set_json(self, text: str) -> None:
        try:
            parsed = json.loads(text)
            text = json.dumps(parsed, indent=2, ensure_ascii=False)
        except (json.JSONDecodeError, TypeError):
            pass
        self.editor.set_json(text)
        self.show_all_button.setVisible(len(text) > 1_000_000)

    def show_all(self) -> None:
        self.editor.show_all()
        self.show_all_button.hide()

    def _focus_search(self) -> None:
        self.search.setFocus()
        self.search.selectAll()

    def find_text(self) -> None:
        needle = self.search.text()
        if not needle:
            return
        if not self.editor.find(needle):
            cursor = self.editor.textCursor()
            cursor.movePosition(cursor.MoveOperation.Start)
            self.editor.setTextCursor(cursor)
            self.editor.find(needle)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_F and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.search.setFocus()
            self.search.selectAll()
            return
        super().keyPressEvent(event)
