"""Stealth Scraper profile editor page for Peke GUI."""

from pathlib import Path

import yaml
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from peke.profile import TargetProfile, load_profile


class ScraperPage(QWidget):
    """Stealth Scraper profile configuration page with inline YAML load/save validation."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.init_ui()

    def init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)

        title = QLabel("Stealth Scraper Profile Editor")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #2D5A4C;")
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(10)

        # Profile Name
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g. Target Web App Scraping Profile")
        form.addRow("Profile Name:", self.name_input)

        # Target URL
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://example.com/api/data")
        form.addRow("Target URL:", self.url_input)

        # Fetcher Choice
        self.fetcher_combo = QComboBox()
        self.fetcher_combo.addItems(["Fetcher", "StealthyFetcher"])
        form.addRow("Scrapling Fetcher Class:", self.fetcher_combo)

        # Delay & Max Pages
        self.spin_delay = QSpinBox()
        self.spin_delay.setRange(0, 60)
        self.spin_delay.setSuffix(" sec")
        form.addRow("Request Delay:", self.spin_delay)

        self.spin_max_pages = QSpinBox()
        self.spin_max_pages.setRange(1, 100)
        self.spin_max_pages.setValue(1)
        form.addRow("Max Pages:", self.spin_max_pages)

        layout.addLayout(form)

        # Custom Headers Table
        layout.addWidget(QLabel("Custom HTTP Headers:"))

        self.headers_table = QTableWidget(0, 2)
        self.headers_table.setHorizontalHeaderLabels(["Header Key", "Header Value"])
        self.headers_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.headers_table)

        table_btn_layout = QHBoxLayout()
        self.add_row_btn = QPushButton("Add Header")
        self.add_row_btn.clicked.connect(self.add_header_row)
        table_btn_layout.addWidget(self.add_row_btn)

        self.remove_row_btn = QPushButton("Remove Selected Header")
        self.remove_row_btn.clicked.connect(self.remove_header_row)
        table_btn_layout.addWidget(self.remove_row_btn)

        table_btn_layout.addStretch()
        layout.addLayout(table_btn_layout)

        # Inline Error Label
        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #F44747; font-weight: bold;")
        layout.addWidget(self.error_label)

        # File Actions
        file_action_layout = QHBoxLayout()
        self.open_btn = QPushButton("Open Profile YAML...")
        self.open_btn.clicked.connect(self.open_profile_yaml)
        file_action_layout.addWidget(self.open_btn)

        self.save_btn = QPushButton("Save Profile YAML...")
        self.save_btn.clicked.connect(self.save_profile_yaml)
        file_action_layout.addWidget(self.save_btn)

        layout.addLayout(file_action_layout)

    def add_header_row(self, key: str = "", value: str = "") -> None:
        row = self.headers_table.rowCount()
        self.headers_table.insertRow(row)
        self.headers_table.setItem(row, 0, QTableWidgetItem(key))
        self.headers_table.setItem(row, 1, QTableWidgetItem(value))

    def remove_header_row(self) -> None:
        row = self.headers_table.currentRow()
        if row >= 0:
            self.headers_table.removeRow(row)

    def get_headers_dict(self) -> dict[str, str]:
        headers = {}
        for row in range(self.headers_table.rowCount()):
            k_item = self.headers_table.item(row, 0)
            v_item = self.headers_table.item(row, 1)
            if k_item and k_item.text().strip():
                headers[k_item.text().strip()] = v_item.text().strip() if v_item else ""
        return headers

    def open_profile_yaml(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Profile YAML", "profiles", "YAML Files (*.yaml *.yml);;All Files (*)"
        )
        if not file_path:
            return

        try:
            profile = load_profile(file_path)
            self.name_input.setText(profile.name or "")
            self.url_input.setText(profile.url)

            idx = self.fetcher_combo.findText(profile.fetcher)
            if idx >= 0:
                self.fetcher_combo.setCurrentIndex(idx)

            self.headers_table.setRowCount(0)
            for k, v in profile.headers.items():
                self.add_header_row(k, str(v))

            self.error_label.setText("")
            QMessageBox.information(self, "Profile Loaded", f"Successfully loaded profile '{Path(file_path).name}'.")

        except Exception as e:
            self.error_label.setText(f"Profile Error: {e}")

    def save_profile_yaml(self) -> None:
        self.error_label.setText("")
        url = self.url_input.text().strip()
        if not url:
            self.error_label.setText("Validation Error: Target URL cannot be empty.")
            return

        headers = self.get_headers_dict()

        try:
            profile = TargetProfile(
                name=self.name_input.text().strip() or "Custom Target Profile",
                url=url,
                fetcher=self.fetcher_combo.currentText(),
                headers=headers,
            )
        except Exception as ve:
            self.error_label.setText(f"Validation Error: {ve}")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Profile YAML", "profiles/custom_profile.yaml", "YAML Files (*.yaml *.yml);;All Files (*)"
        )
        if file_path:
            try:
                Path(file_path).parent.mkdir(parents=True, exist_ok=True)
                with open(file_path, "w", encoding="utf-8") as f:
                    yaml.safe_dump(profile.model_dump(), f, sort_keys=False)
                QMessageBox.information(self, "Profile Saved", f"Profile successfully saved to '{file_path}'.")
            except Exception as e:
                self.error_label.setText(f"Save Error: {e}")
