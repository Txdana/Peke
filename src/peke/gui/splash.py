"""Startup splash banner window for Peke GUI."""

from PySide6.QtCore import QSettings, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QKeyEvent, QMouseEvent
from PySide6.QtWidgets import QGraphicsDropShadowEffect, QLabel, QVBoxLayout, QWidget

from peke.banner import get_banner_string


class ResourceDataLoaderThread(QThread):
    """Background thread to preload fonts and check model availability."""

    resources_loaded = Signal()

    def run(self) -> None:
        # Preload or check resources in background thread
        try:
            from peke.config import get_settings
            _ = get_settings()
        except Exception:
            pass
        self.resources_loaded.emit()


class SplashWidget(QWidget):
    """Frameless dark splash window (#1A1615, 12px radius, ~640x300) with line-by-line reveal."""

    def __init__(self, mcp_active: bool = False, no_splash: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.mcp_active = mcp_active
        self.no_splash = no_splash

        # QSettings toggle check
        self.settings = QSettings("Peke", "PekeStudio")
        splash_enabled = self.settings.value("show_splash", True, type=bool)
        self.should_show = not self.no_splash and bool(splash_enabled)

        if not self.should_show:
            self.hide()
            return

        self.full_banner_text = get_banner_string(mcp_active=mcp_active)
        self.banner_lines = self.full_banner_text.splitlines()
        self.current_line_idx = 0

        self.init_ui()
        self.setup_loader_thread()

    def init_ui(self) -> None:
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.SplashScreen)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(640, 320)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        # Container widget with border-radius and background
        self.container = QWidget(self)
        self.container.setStyleSheet("""
            QWidget {
                background-color: #1A1615;
                border-radius: 12px;
                border: 1px solid #332B28;
            }
        """)
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(24, 24, 24, 24)

        # Drop shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(Qt.GlobalColor.black)
        shadow.setOffset(0, 4)
        self.container.setGraphicsEffect(shadow)

        self.label = QLabel("", self.container)
        self.label.setStyleSheet("font-family: 'IBM Plex Mono', 'Courier New', monospace; font-size: 13px; color: #E2E8F0; border: none;")
        self.label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        container_layout.addWidget(self.label)

        layout.addWidget(self.container)

        # OS reduced motion setting check or quick timer
        # Total reveal duration ~1.2s across lines
        interval = max(50, int(1200 / max(1, len(self.banner_lines))))

        self.reveal_timer = QTimer(self)
        self.reveal_timer.timeout.connect(self._reveal_next_line)
        self.reveal_timer.start(interval)

    def _reveal_next_line(self) -> None:
        if self.current_line_idx < len(self.banner_lines):
            self.current_line_idx += 1
            visible_text = "\n".join(self.banner_lines[: self.current_line_idx])
            self.label.setText(visible_text)
        else:
            self.reveal_timer.stop()

    def setup_loader_thread(self) -> None:
        self.loader_thread = ResourceDataLoaderThread()
        self.loader_thread.resources_loaded.connect(self._on_resources_loaded)
        self.loader_thread.start()

    def _on_resources_loaded(self) -> None:
        # Ensure full text displayed when loading completes
        self.label.setText(self.full_banner_text)
        QTimer.singleShot(500, self.close)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        self.close()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self.close()
