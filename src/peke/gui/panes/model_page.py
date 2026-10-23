"""llama.cpp model configuration page for Peke GUI."""

import json
import os
from pathlib import Path

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


def get_user_config_dir() -> Path:
    """Return platform-appropriate user configuration directory."""
    try:
        import platformdirs
        return Path(platformdirs.user_config_dir("peke"))
    except ImportError:
        return Path.home() / ".config" / "peke"


class ModelPage(QWidget):
    """Model Pipeline settings page managing GGUF model selection and parameters."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.settings = QSettings("Peke", "Workbench")
        self.init_ui()

    def init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)

        title = QLabel("Model Pipeline Configuration (llama.cpp)")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #2D5A4C;")
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(12)

        # Model File Selection
        model_layout = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setReadOnly(True)
        model_layout.addWidget(self.path_input)

        self.browse_btn = QPushButton("Browse GGUF...")
        self.browse_btn.clicked.connect(self.browse_model)
        model_layout.addWidget(self.browse_btn)

        form.addRow("Model File Path (.gguf):", model_layout)

        # Context Size
        self.spin_n_ctx = QSpinBox()
        self.spin_n_ctx.setRange(512, 32768)
        self.spin_n_ctx.setSingleStep(512)
        self.spin_n_ctx.setValue(2048)
        form.addRow("Context Size (n_ctx):", self.spin_n_ctx)

        # GPU Layers
        self.spin_n_gpu = QSpinBox()
        self.spin_n_gpu.setRange(0, 128)
        self.spin_n_gpu.setValue(0)
        form.addRow("GPU Offload Layers (n_gpu_layers):", self.spin_n_gpu)

        # Temperature Slider (0.0 to 0.1)
        temp_layout = QHBoxLayout()
        self.temp_slider = QSlider(Qt.Orientation.Horizontal)
        self.temp_slider.setRange(0, 10)  # 0 to 10 mapped to 0.0 to 0.1
        self.temp_slider.setValue(1)

        self.temp_label = QLabel("0.10")
        self.temp_slider.valueChanged.connect(self._on_temp_changed)

        temp_layout.addWidget(self.temp_slider)
        temp_layout.addWidget(self.temp_label)
        form.addRow("LLM Temperature (0.0 - 0.1):", temp_layout)

        layout.addLayout(form)

        # Save Button
        self.save_btn = QPushButton("Save Model Configuration")
        self.save_btn.clicked.connect(self.save_configuration)
        layout.addWidget(self.save_btn)

        layout.addStretch()
        self.load_saved_values()

    def _on_temp_changed(self, val: int) -> None:
        float_val = val / 100.0
        self.temp_label.setText(f"{float_val:.2f}")

    def browse_model(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select llama.cpp GGUF Model", "", "GGUF Models (*.gguf);;All Files (*)"
        )
        if file_path:
            self.path_input.setText(file_path)

    def load_saved_values(self) -> None:
        model_path = self.settings.value("MODEL_PATH", os.getenv("MODEL_PATH", ""))
        self.path_input.setText(str(model_path))

        n_ctx = int(self.settings.value("n_ctx", 2048))
        self.spin_n_ctx.setValue(n_ctx)

        n_gpu = int(self.settings.value("n_gpu_layers", 0))
        self.spin_n_gpu.setValue(n_gpu)

        temp = float(self.settings.value("llm_temperature", 0.1))
        self.temp_slider.setValue(int(temp * 100))
        self.temp_label.setText(f"{temp:.2f}")

    def save_configuration(self) -> None:
        m_path = self.path_input.text().strip()
        n_ctx = self.spin_n_ctx.value()
        n_gpu = self.spin_n_gpu.value()
        temp = self.temp_slider.value() / 100.0

        # Save to QSettings (user config)
        self.settings.setValue("MODEL_PATH", m_path)
        self.settings.setValue("n_ctx", n_ctx)
        self.settings.setValue("n_gpu_layers", n_gpu)
        self.settings.setValue("llm_temperature", temp)

        os.environ["MODEL_PATH"] = m_path
        os.environ["LLM_TEMPERATURE"] = str(temp)

        # Save to user config file in user directory using platformdirs
        config_dir = get_user_config_dir()
        config_dir.mkdir(parents=True, exist_ok=True)
        config_file = config_dir / "model_config.json"

        cfg_data = {
            "MODEL_PATH": m_path,
            "n_ctx": n_ctx,
            "n_gpu_layers": n_gpu,
            "llm_temperature": temp,
        }
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(cfg_data, f, indent=2)

        QMessageBox.information(self, "Configuration Saved", f"Model configuration saved to '{config_file}'.")
