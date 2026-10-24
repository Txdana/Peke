"""Target inspection workspace and phase-two placeholder pages."""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from peke.gui import theme
from peke.gui.panes.mcp_page import McpSettingsPage
from peke.gui.panes.settings_pages import ModelSettingsPage, SchemaSettingsPage, ScraperSettingsPage
from peke.gui.widgets.console import ExecutionConsole
from peke.gui.widgets.endpoint_tree import EndpointTree


class TargetInspectionPage(QWidget):
    run_requested = Signal(str, str)
    cancel_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(14)
        top = QHBoxLayout()
        self.url_input = QLineEdit("https://example.com")
        self.url_input.setPlaceholderText("Enter target URL or load a profile")
        self.url_input.setAccessibleName("Target URL")
        self.url_input.setStyleSheet("font-family:'IBM Plex Mono',monospace;border-radius:18px")
        self.fetcher = QComboBox()
        self.fetcher.addItems(["StealthyFetcher", "Fetcher"])
        self.fetcher.setAccessibleName("Fetcher type")
        self.run_button = QPushButton("▶  Run Pipeline")
        self.run_button.setObjectName("primaryButton")
        self.run_button.setMinimumHeight(42)
        self.run_button.clicked.connect(lambda: self.run_requested.emit(self.url_input.text().strip(), "stealthy" if self.fetcher.currentIndex() == 0 else "basic"))
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setAccessibleName("Cancel pipeline")
        self.cancel_button.hide()
        self.cancel_button.clicked.connect(self.cancel_requested.emit)
        top.addWidget(self.url_input, 1)
        top.addWidget(self.fetcher)
        top.addWidget(self.run_button)
        top.addWidget(self.cancel_button)
        root.addLayout(top)
        network = QFrame()
        network.setObjectName("card")
        net_layout = QVBoxLayout(network)
        net_layout.setContentsMargins(14, 12, 14, 14)
        heading = QHBoxLayout()
        title = QLabel("Network Endpoint Inspector")
        title.setStyleSheet("font-size:15px;font-weight:700")
        badge = QLabel("●  Endpoint Hints")
        badge.setStyleSheet(f"background:{theme.SAGE};color:white;border-radius:10px;padding:5px 9px;font-size:11px")
        heading.addWidget(title)
        heading.addStretch(1)
        heading.addWidget(badge)
        net_layout.addLayout(heading)
        self.endpoint_tree = EndpointTree()
        net_layout.addWidget(self.endpoint_tree, 1)
        root.addWidget(network, 3)
        self.console = ExecutionConsole()
        root.addWidget(self.console, 2)
        reminder = QLabel("Respect robots.txt and site terms.")
        reminder.setStyleSheet(f"color:{theme.MUTED_TEXT};font-size:11px")
        root.addWidget(reminder)


class Workspace(QStackedWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.target_page = TargetInspectionPage()
        self.scraper_page = ScraperSettingsPage()
        self.model_page = ModelSettingsPage()
        self.schema_page = SchemaSettingsPage()
        self.mcp_page = McpSettingsPage()
        self.addWidget(self.target_page)
        self.addWidget(self.scraper_page)
        self.addWidget(self.model_page)
        self.addWidget(self.schema_page)
        self.addWidget(self.mcp_page)
