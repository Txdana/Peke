"""Provider configuration, local GGUF selection, and desktop updater pane."""
from pathlib import Path
from typing import Any

from PySide6.QtCore import QThread, Signal, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from peke.config import load_settings, save_user_settings
from peke.gui import theme
from peke.updates import check_for_updates


class UpdateCheckWorker(QThread):
    result_ready = Signal(object)

    def run(self) -> None:
        res = check_for_updates()
        self.result_ready.emit(res)


class ProvidersPane(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(16)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(16)

        # 1. Main Provider Selection Card
        card1 = QFrame()
        card1.setStyleSheet(f"QFrame {{ background: {theme.SURFACE}; border-radius: 12px; padding: 16px; }}")
        c1_layout = QVBoxLayout(card1)

        c1_title = QLabel("AI Provider Configuration")
        c1_title.setStyleSheet("font-size: 16px; font-weight: bold;")
        c1_layout.addWidget(c1_title)

        form = QFormLayout()
        self.provider_combo = QComboBox()
        self.provider_combo.addItems([
            "Local llama.cpp (built-in)",
            "Ollama (local server)",
            "OpenRouter (cloud API)",
            "Custom OpenAI-compatible",
        ])
        form.addRow("Extraction Provider:", self.provider_combo)

        self.ollama_url_input = QLineEdit("http://127.0.0.1:11434")
        self.ollama_model_input = QLineEdit("qwen2.5:7b")
        form.addRow("Ollama Base URL:", self.ollama_url_input)
        form.addRow("Ollama Model:", self.ollama_model_input)

        self.openrouter_key_input = QLineEdit()
        self.openrouter_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.openrouter_model_input = QLineEdit("meta-llama/llama-3.3-70b-instruct")
        form.addRow("OpenRouter API Key:", self.openrouter_key_input)
        form.addRow("OpenRouter Model:", self.openrouter_model_input)

        c1_layout.addLayout(form)

        save_btn = QPushButton("Save Provider Settings")
        save_btn.clicked.connect(self._save_provider_settings)
        c1_layout.addWidget(save_btn)

        layout.addWidget(card1)

        # 2. Bring-your-own local GGUF model. No weights are downloaded here.
        card2 = QFrame()
        card2.setStyleSheet(f"QFrame {{ background: {theme.SURFACE}; border-radius: 12px; padding: 16px; }}")
        c2_layout = QVBoxLayout(card2)
        c2_title = QLabel("Local GGUF Model")
        c2_title.setStyleSheet("font-size: 16px; font-weight: bold;")
        c2_layout.addWidget(c2_title)
        model_row = QHBoxLayout()
        self.model_path_input = QLineEdit(str(load_settings().model_path or ""))
        self.model_path_input.setReadOnly(True)
        self.model_path_input.setPlaceholderText("Choose a .gguf file stored on this computer")
        choose_model_btn = QPushButton("Browse…")
        choose_model_btn.clicked.connect(self.choose_model)
        model_row.addWidget(self.model_path_input, 1)
        model_row.addWidget(choose_model_btn)
        c2_layout.addLayout(model_row)
        self.model_status = QLabel("Model weights are not downloaded automatically.")
        self.model_status.setWordWrap(True)
        c2_layout.addWidget(self.model_status)
        save_model_btn = QPushButton("Save local model")
        save_model_btn.clicked.connect(self.save_local_model)
        c2_layout.addWidget(save_model_btn)
        layout.addWidget(card2)

        # 3. Application Updater Card
        card3 = QFrame()
        card3.setStyleSheet(f"QFrame {{ background: {theme.SURFACE}; border-radius: 12px; padding: 16px; }}")
        c3_layout = QVBoxLayout(card3)

        c3_title = QLabel("Peke Application Updates")
        c3_title.setStyleSheet("font-size: 16px; font-weight: bold;")
        c3_layout.addWidget(c3_title)

        self.update_status_label = QLabel("Click 'Check for Updates' to search GitHub Releases.")
        c3_layout.addWidget(self.update_status_label)

        check_update_btn = QPushButton("Check for Updates")
        check_update_btn.clicked.connect(self._check_updates)
        c3_layout.addWidget(check_update_btn)

        layout.addWidget(card3)
        layout.addStretch(1)

        scroll.setWidget(container)
        root.addWidget(scroll)

    def choose_model(self) -> None:
        """Let the user select an existing local GGUF model from the GUI."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose local GGUF model", "", "GGUF models (*.gguf)"
        )
        if path:
            self.model_path_input.setText(path)
            self.model_status.setText("Model selected. Save it to apply the setting.")

    def save_local_model(self) -> None:
        raw_path = self.model_path_input.text().strip()
        if not raw_path:
            save_user_settings({"MODEL_PATH": ""})
            self.model_status.setText("No local model configured. Model-free extraction remains available.")
            return
        path = Path(raw_path).expanduser()
        if path.suffix.lower() != ".gguf" or not path.is_file():
            self.model_status.setText("Choose an existing .gguf model file.")
            return
        try:
            save_user_settings({"MODEL_PATH": str(path.resolve())})
            self.model_status.setText("Local model path saved. Restart Peke to load a newly selected model.")
        except (OSError, ValueError) as exc:
            self.model_status.setText(f"Could not save model path: {exc}")

    def _save_provider_settings(self) -> None:
        idx = self.provider_combo.currentIndex()
        kinds = ["local_builtin", "ollama", "openrouter", "custom_openai"]
        kind = kinds[idx]

        save_user_settings({
            "PROVIDER_MAIN_KIND": kind,
            "OLLAMA_BASE_URL": self.ollama_url_input.text(),
            "OLLAMA_MODEL": self.ollama_model_input.text(),
        })
        self.model_status.setText(f"Saved main provider setting: {kind}")

    def _check_updates(self) -> None:
        existing = getattr(self, "update_worker", None)
        if existing is not None and existing.isRunning():
            return  # replacing a running QThread would destroy it mid-run and crash
        self.update_status_label.setText("Checking GitHub Releases...")
        self.update_worker = UpdateCheckWorker(self)
        self.update_worker.result_ready.connect(self._on_update_result)
        self.update_worker.start()

    @Slot(object)
    def _on_update_result(self, result: Any) -> None:
        self.update_status_label.setText(result.message)
