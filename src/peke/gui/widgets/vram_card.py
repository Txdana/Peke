"""GPU VRAM / RAM monitoring widget for Peke GUI."""

import logging

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar, QVBoxLayout, QWidget

logger = logging.getLogger(__name__)


class VramCardWidget(QWidget):
    """Monitors GPU VRAM (via pynvml) or CPU RAM fallback (via psutil) every 2 seconds.

    Progress bar uses sage color (#2D5A4C) normally and turns terracotta (#B04A24) above 90%.
    Never raises exceptions if GPU/pynvml is unavailable.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.pynvml_available = False
        self.psutil_available = False
        self._init_libraries()
        self.init_ui()

        # Timer polling every 2000 ms (2 sec)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_metrics)
        self.timer.start(2000)
        self.update_metrics()

    def _init_libraries(self) -> None:
        try:
            import pynvml
            pynvml.nvmlInit()
            self.pynvml_available = True
        except Exception:
            self.pynvml_available = False

        try:
            self.psutil_available = True
        except Exception:
            self.psutil_available = False

    def init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        card_frame = QFrame()
        card_frame.setStyleSheet("background-color: #252526; border-radius: 6px; border: 1px solid #333333;")
        frame_layout = QVBoxLayout(card_frame)

        # Header Label
        header_layout = QHBoxLayout()
        self.title_label = QLabel("GPU VRAM Usage")
        self.title_label.setStyleSheet("font-weight: bold; color: #2D5A4C;")
        header_layout.addWidget(self.title_label)

        header_layout.addStretch()

        self.value_label = QLabel("Initializing...")
        self.value_label.setStyleSheet("color: #CCCCCC;")
        header_layout.addWidget(self.value_label)

        frame_layout.addLayout(header_layout)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(12)
        self.progress_bar.setTextVisible(False)
        self._set_bar_color("#2D5A4C")

        frame_layout.addWidget(self.progress_bar)
        layout.addWidget(card_frame)

    def _set_bar_color(self, hex_color: str) -> None:
        self.progress_bar.setStyleSheet(
            f"QProgressBar {{ border: none; background-color: #1E1E1E; border-radius: 3px; }}"
            f"QProgressBar::chunk {{ background-color: {hex_color}; border-radius: 3px; }}"
        )

    def update_metrics(self) -> None:
        """Poll GPU or CPU memory and update progress bar."""
        if self.pynvml_available:
            try:
                import pynvml
                handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                used_gb = info.used / (1024**3)
                total_gb = info.total / (1024**3)
                pct = int((info.used / info.total) * 100) if info.total > 0 else 0

                self.title_label.setText("GPU VRAM Usage")
                self.value_label.setText(f"{used_gb:.1f} GB / {total_gb:.1f} GB ({pct}%)")
                self.progress_bar.setValue(pct)

                if pct >= 90:
                    self._set_bar_color("#B04A24")  # Terracotta color above 90%
                else:
                    self._set_bar_color("#2D5A4C")  # Sage color
                return
            except Exception:
                pass

        # CPU RAM fallback
        if self.psutil_available:
            try:
                import psutil
                mem = psutil.virtual_memory()
                used_gb = mem.used / (1024**3)
                total_gb = mem.total / (1024**3)
                pct = int(mem.percent)

                self.title_label.setText("CPU RAM Usage (GPU: not detected)")
                self.value_label.setText(f"{used_gb:.1f} GB / {total_gb:.1f} GB ({pct}%)")
                self.progress_bar.setValue(pct)

                if pct >= 90:
                    self._set_bar_color("#B04A24")
                else:
                    self._set_bar_color("#2D5A4C")
                return
            except Exception:
                pass

        self.title_label.setText("GPU: not detected")
        self.value_label.setText("N/A")
        self.progress_bar.setValue(0)
