"""Optional GPU/CPU memory telemetry card; telemetry failures are harmless."""
import importlib.util

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QFrame, QLabel, QProgressBar, QVBoxLayout

from peke.gui import theme


class VramCard(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        layout = QVBoxLayout(self)
        self.label = QLabel("GPU: checking…")
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        layout.addWidget(self.label)
        layout.addWidget(self.progress)
        self.timer = QTimer(self)
        self.timer.setInterval(2000)
        self.timer.timeout.connect(self.refresh)
        self.refresh()
        self.timer.start()

    def refresh(self) -> None:
        try:
            if importlib.util.find_spec("pynvml") is not None:
                import pynvml
                pynvml.nvmlInit()
                try:
                    handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                    mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
                    used, total = int(mem.used), int(mem.total)
                    pct = int(used * 100 / total) if total else 0
                    self.label.setText(f"GPU VRAM  {used / 1e9:.1f}GB / {total / 1e9:.1f}GB")
                    self.progress.setValue(pct)
                    self.progress.setStyleSheet(f"QProgressBar::chunk {{ background:{theme.TERRACOTTA if pct > 90 else theme.SAGE}; border-radius:4px; }}")
                    return
                finally:
                    pynvml.nvmlShutdown()
        except Exception:
            # Telemetry is optional and must never break the shell.
            pass
        try:
            import psutil
            mem = psutil.virtual_memory()
            self.label.setText(f"GPU: not detected · RAM {mem.used / 1e9:.1f} / {mem.total / 1e9:.1f} GB")
            self.progress.setValue(int(mem.percent))
        except (ImportError, OSError, AttributeError):
            self.label.setText("GPU: not detected")
            self.progress.setValue(0)
