"""Small, keyboard-dismissable startup splash screen."""
from __future__ import annotations

from PySide6.QtCore import QSettings, Qt, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from peke.banner import rea_available
from peke.config import load_settings
from peke.gui import theme


class SplashScreen(QWidget):
    """Frameless splash with a short line-by-line reveal."""
    dismissed = Signal()
    LINES = (
        "┌──────────────────────────────────────────────────────┐",
        "│  PEKE  [REA CLI Off]                 local: llama.cpp     │",
        "└──────────────────────────────────────────────────────┘",
        "  │",
        "  ├── [01] REA Analysis  ──▶  Discovered Endpoint",
        "  ├── [02] Scrapling     ──▶  Page Retrieved",
        "  └── [03] Local SLM     ──▶  Clean JSON Formatted",
    )

    def __init__(self, parent=None, reduced_motion: bool = False) -> None:
        super().__init__(
            parent,
            Qt.WindowType.SplashScreen | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint,
        )
        self.setObjectName("pekeSplash")
        self.setFixedSize(640, 300)
        self.setStyleSheet(f"#pekeSplash {{ background: {theme.CONSOLE_BG}; border-radius: 12px; }}")
        self.setAccessibleName("Peke startup splash")
        self.label = QLabel("", self)
        self.label.setTextFormat(Qt.TextFormat.PlainText)
        self.label.setStyleSheet(f"color: {theme.CONSOLE_TIMESTAMP}; background: transparent;")
        self.label.setFont(QFont("IBM Plex Mono", 10))
        self.label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.addWidget(self.label)
        settings = load_settings()
        status = "[REA CLI Found]" if rea_available(settings.rea_command) else "[REA CLI Missing]"
        self.lines = tuple(line.replace("[REA CLI Off]", status) for line in self.LINES)
        self._index = 0
        self._timer = QTimer(self)
        self._timer.setInterval(170)
        self._timer.timeout.connect(self._reveal_next)
        if reduced_motion:
            self.label.setText("\n".join(self.lines))
        else:
            self._timer.start()

    def _reveal_next(self) -> None:
        self._index += 1
        self.label.setText("\n".join(self.lines[:self._index]))
        if self._index >= len(self.LINES):
            self._timer.stop()

    def keyPressEvent(self, event) -> None:
        self._timer.stop()
        self.dismissed.emit()
        self.close()
        event.accept()

    def mousePressEvent(self, event) -> None:
        self.keyPressEvent(event)

    @staticmethod
    def enabled_by_setting() -> bool:
        settings = QSettings("Peke", "PekeWorkbench")
        return settings.value("show_splash", True, type=bool)
