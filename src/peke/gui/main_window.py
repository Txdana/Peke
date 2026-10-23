"""Main application window for Peke GUI."""

import logging
from pathlib import Path

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from peke.config import get_settings
from peke.gui.panes.model_page import ModelPage
from peke.gui.panes.schemas_page import SchemasPage
from peke.gui.panes.scraper_page import ScraperPage
from peke.gui.panes.workspace import WorkspacePage
from peke.gui.splash import SplashWidget

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Main Application Window with sidebar navigation and stacked pages."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Peke - Stealth Data Extraction Workbench")
        self.resize(1200, 800)

        self.settings_manager = QSettings("Peke", "Workbench")

        self.init_ui()
        self.check_first_run_model()

    def init_ui(self) -> None:
        main_widget = QWidget()
        self.setCentralWidget(main_widget)

        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Sidebar Navigation
        self.sidebar = QListWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(220)

        nav_items = [
            ("⚡ Workspace", 0),
            ("📜 JSON Schemas", 1),
            ("🧠 Model Pipeline", 2),
            ("🥷 Stealth Scraper", 3),
        ]

        for text, index in nav_items:
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, index)
            self.sidebar.addItem(item)

        main_layout.addWidget(self.sidebar)

        # 2. Main Stacked Pages
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        self.splash = SplashWidget(mcp_active=False)
        right_layout.addWidget(self.splash)

        self.stacked_widget = QStackedWidget()

        # Page 0: Workspace
        self.workspace_page = WorkspacePage()
        self.workspace_page.sig_status_updated.connect(self.update_status_chip)
        self.stacked_widget.addWidget(self.workspace_page)

        # Page 1: JSON Schemas
        self.schemas_page = SchemasPage()
        self.stacked_widget.addWidget(self.schemas_page)

        # Page 2: Model Pipeline
        self.model_page = ModelPage()
        self.stacked_widget.addWidget(self.model_page)

        # Page 3: Stealth Scraper
        self.scraper_page = ScraperPage()
        self.stacked_widget.addWidget(self.scraper_page)

        right_layout.addWidget(self.stacked_widget)

        main_layout.addWidget(right_container)

        self.sidebar.currentRowChanged.connect(self.on_nav_changed)
        self.sidebar.setCurrentRow(0)

        # 3. Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self.status_chip = QLabel("llama.cpp: Not Loaded | Temp: 0.1 | 0.0 tok/s")
        self.status_chip.setStyleSheet(
            "background-color: #252526; color: #2D5A4C; font-weight: bold; padding: 2px 8px; border-radius: 4px;"
        )
        self.status_bar.addPermanentWidget(self.status_chip)

        self.footer_reminder = QLabel("Respect robots.txt and site terms.")
        self.footer_reminder.setStyleSheet("color: #777777; padding-left: 10px; font-style: italic;")
        self.status_bar.addWidget(self.footer_reminder)

    def on_nav_changed(self, row: int) -> None:
        if 0 <= row < self.stacked_widget.count():
            self.stacked_widget.setCurrentIndex(row)

    def update_status_chip(self, model_name: str, temp: float, tok_sec: float) -> None:
        self.status_chip.setText(f"llama.cpp: {model_name} | Temp: {temp:.1f} | {tok_sec:.1f} tok/s")

    def check_first_run_model(self) -> None:
        settings = get_settings()
        has_model = False
        try:
            m_path = settings.get_model_path(require_exists=True)
            if m_path and m_path.exists():
                has_model = True
        except Exception:
            has_model = False

        if not has_model:
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Peke - Local Model Configuration")
            msg_box.setIcon(QMessageBox.Icon.Information)
            msg_box.setText("Welcome to Peke Desktop Workbench!")
            msg_box.setInformativeText(
                "Peke uses local llama.cpp GGUF model files for offline, private LLM data extraction.\n\n"
                "No model file is currently configured. Would you like to select a local .gguf file now?"
            )
            choose_btn = msg_box.addButton("Choose Model File...", QMessageBox.ButtonRole.AcceptRole)
            msg_box.addButton("Skip for now", QMessageBox.ButtonRole.RejectRole)
            msg_box.exec()

            if msg_box.clickedButton() == choose_btn:
                file_path, _ = QFileDialog.getOpenFileName(
                    self, "Select llama.cpp GGUF Model", "", "GGUF Models (*.gguf);;All Files (*)"
                )
                if file_path:
                    self.settings_manager.setValue("MODEL_PATH", file_path)
                    import os
                    os.environ["MODEL_PATH"] = file_path
                    self.update_status_chip(Path(file_path).name, 0.1, 0.0)
