"""Phase 3 profile, model and schema settings pages."""
import json
from pathlib import Path

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from peke.config import load_settings, save_user_settings
from peke.gui import theme
from peke.profile import Profile, ProfileError, load_profile
from peke.schemas import get_schema, list_schemas


def _card_page(title: str, page: QWidget | None = None) -> tuple[QWidget, QVBoxLayout]:
    page = page or QWidget()
    layout = QVBoxLayout(page)
    layout.setContentsMargins(24, 24, 24, 24)
    heading = QLabel(title)
    heading.setStyleSheet("font-family:'Fraunces',serif;font-size:22px;font-weight:700")
    layout.addWidget(heading)
    return page, layout


class ScraperSettingsPage(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        page, layout = _card_page("Stealth Scraper", self)
        form = QFormLayout()
        self.fetcher = QComboBox()
        self.fetcher.addItems(["stealthy", "basic"])
        self.delay = QLineEdit("1.0")
        self.max_pages = QSpinBox()
        self.max_pages.setRange(1, 100)
        self.max_pages.setValue(1)
        self.headers = QTableWidget(0, 2)
        self.headers.setHorizontalHeaderLabels(["Header", "Value"])
        self.profile_url = QLineEdit("https://example.com")
        form.addRow("Target URL", self.profile_url)
        form.addRow("Fetcher", self.fetcher)
        form.addRow("Request delay (seconds)", self.delay)
        form.addRow("Max pages", self.max_pages)
        layout.addLayout(form)
        layout.addWidget(QLabel("Request headers"))
        layout.addWidget(self.headers, 1)
        buttons = QHBoxLayout()
        self.add_header = QPushButton("Add header")
        self.add_header.clicked.connect(self._add_header)
        self.open_button = QPushButton("Open profile")
        self.open_button.clicked.connect(self.open_profile)
        self.save_button = QPushButton("Save profile")
        self.save_button.clicked.connect(self.save_profile)
        buttons.addWidget(self.add_header)
        buttons.addStretch(1)
        buttons.addWidget(self.open_button)
        buttons.addWidget(self.save_button)
        layout.addLayout(buttons)
        self.error = QLabel("")
        self.error.setStyleSheet(f"color:{theme.TERRACOTTA_TEXT}")
        self.error.setWordWrap(True)
        layout.addWidget(self.error)
        self._add_header()

    def _add_header(self) -> None:
        row = self.headers.rowCount()
        self.headers.insertRow(row)
        self.headers.setItem(row, 0, QTableWidgetItem(""))
        self.headers.setItem(row, 1, QTableWidgetItem(""))

    def _profile_dict(self) -> dict:
        headers = {}
        for row in range(self.headers.rowCount()):
            key = self.headers.item(row, 0).text().strip() if self.headers.item(row, 0) else ""
            value = self.headers.item(row, 1).text() if self.headers.item(row, 1) else ""
            if key:
                headers[key] = value
        return {
            "name": "GUI target",
            "url": self.profile_url.text().strip(),
            "fetcher": self.fetcher.currentText(),
            "headers": headers,
            "params": {},
            "method": "GET",
            "schema_name": "Article",
            "mode": "auto",
            "max_pages": self.max_pages.value(),
        }

    def open_profile(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open Peke profile", "profiles", "YAML profiles (*.yaml *.yml)")
        if not path:
            return
        try:
            profile = load_profile(path)
            self.profile_url.setText(profile.url)
            self.fetcher.setCurrentText(profile.fetcher)
            self.headers.setRowCount(0)
            for key, value in profile.headers.items():
                row = self.headers.rowCount()
                self.headers.insertRow(row)
                self.headers.setItem(row, 0, QTableWidgetItem(key))
                self.headers.setItem(row, 1, QTableWidgetItem(value))
            self.max_pages.setValue(profile.max_pages)
            self.error.setText("")
            QSettings("Peke", "PekeWorkbench").setValue("active_profile", str(path))
        except (ProfileError, OSError, ValueError) as exc:
            self.error.setText(str(exc))

    def save_profile(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save Peke profile", "profiles/target.yaml", "YAML profiles (*.yaml *.yml)")
        if not path:
            return
        try:
            import yaml

            delay_value = float(self.delay.text().strip())
            if delay_value < 0:
                raise ValueError("Request delay must be zero or greater")
            profile = Profile.model_validate(self._profile_dict())
            save_user_settings({"REQUEST_DELAY_SECONDS": delay_value})
            Path(path).write_text(yaml.safe_dump(profile.model_dump(mode="json"), sort_keys=False), encoding="utf-8")
            self.error.setText(f"Profile saved: {path}")
            QSettings("Peke", "PekeWorkbench").setValue("active_profile", path)
        except (ValueError, OSError, ImportError) as exc:
            self.error.setText(f"Profile validation/save error: {exc}")


class ModelSettingsPage(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        page, layout = _card_page("Model Pipeline · llama.cpp", self)
        self.model_path = QLineEdit(str(load_settings().model_path or ""))
        self.model_path.setReadOnly(True)
        choose = QPushButton("Choose GGUF model…")
        choose.clicked.connect(self.choose_model)
        row = QHBoxLayout()
        row.addWidget(self.model_path, 1)
        row.addWidget(choose)
        layout.addLayout(row)
        form = QFormLayout()
        self.n_ctx = QSpinBox()
        self.n_ctx.setRange(512, 262144)
        self.n_ctx.setValue(load_settings().n_ctx)
        self.gpu_layers = QSpinBox()
        self.gpu_layers.setRange(0, 999)
        self.gpu_layers.setValue(load_settings().n_gpu_layers)
        self.temperature = QSlider()
        self.temperature.setOrientation(Qt.Orientation.Horizontal)
        self.temperature.setRange(0, 10)
        self.temperature.setValue(int(load_settings().temperature * 100))
        self.temperature.setAccessibleName("LLM temperature")
        self.temp_label = QLabel(f"{self.temperature.value()/100:.2f}")
        self.temperature.valueChanged.connect(lambda v: self.temp_label.setText(f"{v/100:.2f}"))
        temp_row = QHBoxLayout()
        temp_row.addWidget(self.temperature, 1)
        temp_row.addWidget(self.temp_label)
        self.rea_command = QLineEdit(load_settings().rea_command or "")
        self.rea_command.setPlaceholderText("rea (installed local CLI; no auto-install)")
        self.rea_command.setAccessibleName("REA CLI command")
        self.rea_cdp_endpoint = QLineEdit(load_settings().rea_cdp_endpoint)
        self.rea_cdp_endpoint.setPlaceholderText("http://127.0.0.1:9222")
        self.rea_cdp_endpoint.setAccessibleName("REA browser debugging endpoint")
        form.addRow("Context size", self.n_ctx)
        form.addRow("GPU layers", self.gpu_layers)
        form.addRow("Temperature", temp_row)
        form.addRow("REA CLI command (optional)", self.rea_command)
        form.addRow("Chrome CDP endpoint", self.rea_cdp_endpoint)
        layout.addLayout(form)
        model_value = Path(self.model_path.text()).expanduser() if self.model_path.text() else None
        model_is_valid = bool(model_value and model_value.is_file() and model_value.suffix.lower() == ".gguf")
        self.status = QLabel("Local GGUF model file found" if model_is_valid else "No valid local model configured; choose a local .gguf file.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        rea_help = QLabel("REA attaches to an already-running Chrome-family browser. Start it with remote debugging enabled, open the target page, then use the same loopback CDP endpoint here. Peke will reuse that connection while scraping.")
        rea_help.setWordWrap(True)
        layout.addWidget(rea_help)
        save = QPushButton("Save model settings")
        save.clicked.connect(self.save_settings)
        layout.addWidget(save)
        layout.addStretch(1)
        self.setLayout(layout)

    def choose_model(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Choose local GGUF model", "", "GGUF models (*.gguf)")
        if path:
            self.model_path.setText(path)
            self.status.setText("Model selected. Save settings to apply.")

    def save_settings(self) -> None:
        try:
            model_text = self.model_path.text().strip()
            if model_text:
                model_path = Path(model_text).expanduser()
                if model_path.suffix.lower() != ".gguf":
                    raise ValueError("Model file must have a .gguf extension.")
                if not model_path.is_file():
                    raise ValueError("Selected model file does not exist.")
                model_text = str(model_path)
            rea_command = self.rea_command.text().strip()
            values = {
                "MODEL_PATH": model_text,
                "N_CTX": self.n_ctx.value(),
                "N_GPU_LAYERS": self.gpu_layers.value(),
                "TEMPERATURE": self.temperature.value() / 100,
                "REA_COMMAND": rea_command,
                "REA_CDP_ENDPOINT": self.rea_cdp_endpoint.text().strip() or "http://127.0.0.1:9222",
            }
            save_user_settings(values)
            self.status.setText(f"Settings saved. Restart Peke to apply model settings.")
        except (ImportError, OSError, ValueError) as exc:
            self.status.setText(f"Could not save settings: {exc}")


class SchemaSettingsPage(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        page, layout = _card_page("JSON Schemas", self)
        self.schemas = QComboBox()
        self.schemas.addItems(list_schemas())
        self.schemas.currentTextChanged.connect(self.preview_schema)
        choose = QPushButton("Load schema from file…")
        choose.clicked.connect(self.load_schema)
        top = QHBoxLayout()
        top.addWidget(self.schemas, 1)
        top.addWidget(choose)
        layout.addLayout(top)
        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setStyleSheet(f"font-family:'IBM Plex Mono',monospace;background:{theme.SURFACE}")
        layout.addWidget(self.preview, 1)
        self.error = QLabel("")
        self.error.setWordWrap(True)
        layout.addWidget(self.error)
        settings = QSettings("Peke", "PekeWorkbench")
        active = settings.value("active_schema", "Article")
        if active not in list_schemas():
            active = "Article"
        self.schemas.setCurrentText(active)
        self.preview_schema(active)

    def preview_schema(self, name: str) -> None:
        try:
            model = get_schema(name)
            self.preview.setPlainText(json.dumps(model.model_json_schema(), indent=2))
            self.error.setText("")
            QSettings("Peke", "PekeWorkbench").setValue("active_schema", name)
        except (ValueError, OSError) as exc:
            self.error.setText(str(exc))

    def load_schema(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Load Pydantic schema", "", "Python files (*.py)")
        if not path:
            return
        from PySide6.QtWidgets import QInputDialog, QMessageBox

        answer = QMessageBox.warning(
            self,
            "Run Python schema code?",
            "A custom schema is executable Python code and will run inside Peke. "
            "Only continue if you wrote this file or have audited it. Untrusted schema "
            "files can access local files and execute arbitrary code.",
            QMessageBox.StandardButton.Continue | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Continue:
            return
        class_name, ok = QInputDialog.getText(self, "Schema class", "Pydantic model class name:")
        if not ok or not class_name.strip():
            return
        name = f"{path}:{class_name.strip()}"
        try:
            get_schema(name)
            self.schemas.addItem(name)
            self.schemas.setCurrentText(name)
            self.error.setText("Schema loaded and validated.")
        except (ValueError, OSError) as exc:
            self.error.setText(f"Schema rejected: {exc}")
