"""Main window layout and controls for Peke GUI."""

import importlib.metadata
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from peke.config import get_settings
from peke.discover import is_rea_available
from peke.gui.panes.model_page import ModelPage
from peke.gui.panes.schemas_page import SchemasPage
from peke.gui.panes.scraper_page import ScraperPage
from peke.gui.panes.sidebar import SidebarNav
from peke.gui.splash import SplashWidget


class AboutDialog(QDialog):
    """About dialog displaying application identity, version, licenses, and links."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("About Peke")
        self.setFixedSize(500, 380)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        try:
            version = importlib.metadata.version("peke")
        except Exception:
            version = "0.1.0"

        title = QLabel(f"<h2>Peke v{version}</h2>")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("<b>Open-Source Data-Extraction Workbench</b>")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        description = QLabel(
            "Peke orchestrates REA, Scrapling, and local llama.cpp into a deterministic "
            "and LLM-assisted web extraction pipeline."
        )
        description.setWordWrap(True)
        description.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(description)

        tabs = QTabWidget(self)

        # Tab 1: License
        license_text = QLabel(
            "<b>License: MIT License</b><br><br>"
            "Permission is hereby granted, free of charge, to any person obtaining a copy "
            "of this software and associated documentation files..."
        )
        license_text.setWordWrap(True)
        tabs.addTab(license_text, "License")

        # Tab 2: Third-party notices
        notices_text = QLabel(
            "<b>Third-Party Components:</b><br>"
            "• <b>Scrapling:</b> Stealth fetching & parsing (BSD/MIT)<br>"
            "• <b>llama-cpp-python:</b> In-process GGUF LLM inference (MIT)<br>"
            "• <b>REA:</b> Reverse-engineering assistant MCP server (Optional integration)<br>"
            "• <b>PySide6:</b> Qt for Python GUI bindings (LGPLv3)"
        )
        notices_text.setWordWrap(True)
        tabs.addTab(notices_text, "Third-Party Notices")

        layout.addWidget(tabs)

        bbox = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        bbox.accepted.connect(self.accept)
        layout.addWidget(bbox)


class MainWindow(QMainWindow):
    """Primary application window for Peke workbench."""

    def __init__(self, no_splash: bool = False) -> None:
        super().__init__()
        self.setWindowTitle("Peke")
        self.resize(1100, 750)

        # Set window icon
        icon_path = Path(__file__).parent / "assets" / "icon.svg"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        settings = get_settings()
        mcp_status = is_rea_available(settings.rea_server_url)

        # Show splash if enabled
        if not no_splash:
            self.splash = SplashWidget(mcp_active=mcp_status)
            if self.splash.should_show:
                self.splash.show()

        self.init_ui()

    def init_ui(self) -> None:
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Sidebar navigation
        self.sidebar = SidebarNav()
        main_layout.addWidget(self.sidebar)

        # Right pane container
        right_container = QWidget(self)
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # Stacked pages
        self.pages_stack = QStackedWidget(right_container)
        self.scraper_page = ScraperPage()
        self.schemas_page = SchemasPage()
        self.model_page = ModelPage()

        self.pages_stack.addWidget(self.scraper_page)
        self.pages_stack.addWidget(self.schemas_page)
        self.pages_stack.addWidget(self.model_page)

        right_layout.addWidget(self.pages_stack)

        # Bottom toolbar for About and options
        bottom_bar = QWidget(right_container)
        bottom_layout = QHBoxLayout(bottom_bar)
        bottom_layout.setContentsMargins(8, 4, 8, 4)

        about_btn = QPushButton("About Peke")
        about_btn.clicked.connect(self.show_about_dialog)
        bottom_layout.addWidget(about_btn)
        bottom_layout.addStretch()

        right_layout.addWidget(bottom_bar)

        main_layout.addWidget(right_container)

        # Connect sidebar nav buttons
        self.sidebar.nav_changed.connect(self.pages_stack.setCurrentIndex)

    def show_about_dialog(self) -> None:
        dialog = AboutDialog(self)
        dialog.exec()
