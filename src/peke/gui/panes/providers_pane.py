"""Providers, Model Downloads, and Desktop Updater UI Pane."""
import logging
from typing import Any

from PySide6.QtCore import QThread, Signal, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from peke.config import load_settings, save_user_settings
from peke.gui import theme
from peke.models import DEFAULT_MODEL_FILE, DEFAULT_MODEL_REPO, ModelManager
from peke.updates import check_for_updates

logger = logging.getLogger(__name__)


class ModelDownloadWorker(QThread):
    progress = Signal(int, int, float, float)
    finished_ok = Signal(str)
    failed = Signal(str)

    def __init__(self, repo: str, file: str, parent=None) -> None:
        super().__init__(parent)
        self.repo = repo
        self.file = file

    def run(self) -> None:
        mgr = ModelManager()

        def _cb(downloaded: int, total: int, speed: float, eta: float) -> None:
            self.progress.emit(downloaded, total, speed, eta)

        try:
            info = mgr.download_model(repo=self.repo, file=self.file, progress_callback=_cb)
            self.finished_ok.emit(info.local_path)
        except Exception as exc:
            self.failed.emit(str(exc))


class UpdateCheckWorker(QThread):
    result_ready = Signal(object)

    def run(self) -> None:
        res = check_for_updates()
        self.result_ready.emit(res)


class ProvidersPane(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.settings = load_settings()

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

        # 2. Managed GGUF Model Downloader Card
        card2 = QFrame()
        card2.setStyleSheet(f"QFrame {{ background: {theme.SURFACE}; border-radius: 12px; padding: 16px; }}")
        c2_layout = QVBoxLayout(card2)

        c2_title = QLabel("Managed GGUF Model Manager")
        c2_title.setStyleSheet("font-size: 16px; font-weight: bold;")
        c2_layout.addWidget(c2_title)

        model_form = QFormLayout()
        self.repo_input = QLineEdit(DEFAULT_MODEL_REPO)
        self.file_input = QLineEdit(DEFAULT_MODEL_FILE)
        model_form.addRow("Repository:", self.repo_input)
        model_form.addRow("GGUF File:", self.file_input)
        c2_layout.addLayout(model_form)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        c2_layout.addWidget(self.progress_bar)

        self.download_status = QLabel("")
        c2_layout.addWidget(self.download_status)

        dl_btn = QPushButton("Download Model")
        dl_btn.clicked.connect(self._start_download)
        c2_layout.addWidget(dl_btn)

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

    def _save_provider_settings(self) -> None:
        idx = self.provider_combo.currentIndex()
        kinds = ["local_builtin", "ollama", "openrouter", "custom_openai"]
        kind = kinds[idx]

        save_user_settings({
            "PROVIDER_MAIN_KIND": kind,
            "OLLAMA_BASE_URL": self.ollama_url_input.text(),
            "OLLAMA_MODEL": self.ollama_model_input.text(),
        })
        self.download_status.setText(f"Saved main provider setting: {kind}")

    def _start_download(self) -> None:
        repo = self.repo_input.text().strip()
        file = self.file_input.text().strip()
        if not repo or not file:
            return

        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.download_status.setText("Starting download...")

        self.worker = ModelDownloadWorker(repo, file)
        self.worker.progress.connect(self._on_download_progress)
        self.worker.finished_ok.connect(self._on_download_success)
        self.worker.failed.connect(self._on_download_failure)
        self.worker.start()

    @Slot(int, int, float, float)
    def _on_download_progress(self, downloaded: int, total: int, speed: float, eta: float) -> None:
        if total > 0:
            pct = int((downloaded / total) * 100)
            self.progress_bar.setValue(pct)
            mb = downloaded / (1024 * 1024)
            total_mb = total / (1024 * 1024)
            speed_mb = speed / (1024 * 1024)
            self.download_status.setText(f"Downloaded {mb:.1f} / {total_mb:.1f} MB ({pct}%) - {speed_mb:.1f} MB/s - ETA: {eta:.0f}s")

    @Slot(str)
    def _on_download_success(self, local_path: str) -> None:
        self.progress_bar.setValue(100)
        self.download_status.setText(f"Model downloaded and ready: {local_path}")
        save_user_settings({"MODEL_PATH": local_path})

    @Slot(str)
    def _on_download_failure(self, error: str) -> None:
        self.progress_bar.setVisible(False)
        self.download_status.setText(f"Download error: {error}")

    def _check_updates(self) -> None:
        self.update_status_label.setText("Checking GitHub Releases...")
        self.update_worker = UpdateCheckWorker()
        self.update_worker.result_ready.connect(self._on_update_result)
        self.update_worker.start()

    @Slot(object)
    def _on_update_result(self, result: Any) -> None:
        self.update_status_label.setText(result.message)
