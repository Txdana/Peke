"""Tabbed JSON, Markdown and metrics output panel."""
import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QPainter, QPen, QPalette
from PySide6.QtWidgets import QFileDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QTabWidget, QTextBrowser, QVBoxLayout, QWidget
from peke.gui import theme
from peke.gui.widgets.json_view import JsonView


class OutputPanel(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("outputPanel")
        self.setMinimumWidth(360)
        self.setMaximumWidth(420)
        self.last_json = "[]"
        self.last_markdown = "# Peke output\n\nRun a pipeline to see extracted records."
        self.metrics: dict = {}
        self.model_name = "no model"
        self._throughput_history: list[float] = []
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)
        actions = QHBoxLayout()
        actions.addStretch(1)
        self.copy_button = QPushButton("Copy JSON")
        self.copy_button.setAccessibleName("Copy JSON to clipboard")
        self.copy_button.clicked.connect(self.copy_json)
        self.copy_md_button = QPushButton("Copy Markdown")
        self.copy_md_button.clicked.connect(self.copy_markdown)
        self.export_button = QPushButton("Export")
        self.export_button.setAccessibleName("Export output")
        self.export_button.clicked.connect(self.export_output)
        actions.addWidget(self.copy_button)
        actions.addWidget(self.copy_md_button)
        actions.addWidget(self.export_button)
        root.addLayout(actions)
        self.tabs = QTabWidget()
        self.json_view = JsonView()
        self.markdown_view = QTextBrowser()
        self.markdown_view.setOpenExternalLinks(True)
        self.metrics_view = QWidget()
        self.metrics_layout = QVBoxLayout(self.metrics_view)
        self.metrics_layout.setContentsMargins(12, 14, 12, 12)
        self.tabs.addTab(self.json_view, "Structured Output (JSON)")
        self.tabs.addTab(self.markdown_view, "Markdown Summary")
        self.tabs.addTab(self.metrics_view, "Model Metrics")
        root.addWidget(self.tabs, 1)
        self.status = QLabel("llama.cpp: no model | Temp: 0.1 | 0 tok/s")
        self.status.setStyleSheet(f"background:{theme.SAGE};color:white;border-radius:10px;padding:9px;font-family:'IBM Plex Mono',monospace;font-size:10px")
        root.addWidget(self.status)
        self.set_result(None)

    def set_result(self, result) -> None:
        if result is not None:
            self.last_json = json.dumps([r.model_dump(mode="json") for r in result.records], indent=2, ensure_ascii=False)
            self.last_markdown = result.markdown_summary or "# Peke output\n\nNo records extracted."
            self.metrics = result.metrics or {}
            self.model_name = str(self.metrics.get("model_name", "no model"))
        self.json_view.set_json(self.last_json)
        self.markdown_view.setMarkdown(self.last_markdown)
        while self.metrics_layout.count():
            item = self.metrics_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        size_bytes = int(self.metrics.get("model_size_bytes", 0) or 0)
        speed = float(self.metrics.get("tokens_per_second", 0) or 0)
        if result is not None:
            self._throughput_history.append(speed)
            self._throughput_history = self._throughput_history[-10:]
        rows = [("Model", self.model_name), ("GGUF size", f"{size_bytes / 1e9:.2f} GB" if size_bytes else "—"),
                ("Context (n_ctx)", str(self.metrics.get("n_ctx", "—"))),
                ("GPU layers", str(self.metrics.get("n_gpu_layers", "—"))),
                ("Temperature", str(self.metrics.get("temperature", 0.1))),
                ("Prompt tokens", str(self.metrics.get("prompt_tokens", 0))),
                ("Completion tokens", str(self.metrics.get("completion_tokens", 0))),
                ("Tokens / sec", str(self.metrics.get("tokens_per_second", 0))),
                ("Retries used", str(self.metrics.get("retries", 0))),
                ("Fetch time", f"{self.metrics.get('fetch_ms', 0)} ms"),
                ("Total time", f"{self.metrics.get('elapsed_ms', 0)} ms"),
                ("Valid / invalid", f"{self.metrics.get('records_valid', 0)} / {self.metrics.get('records_invalid', 0)}")]
        for name, value in rows:
            line = QHBoxLayout()
            label = QLabel(name)
            label.setStyleSheet(f"color:{theme.MUTED_TEXT}")
            value_label = QLabel(value)
            value_label.setStyleSheet("font-weight:700")
            line.addWidget(label)
            line.addStretch(1)
            line.addWidget(value_label)
            self.metrics_layout.addLayout(line)
        self.sparkline = TokenSparkline()
        self.sparkline.set_values(self._throughput_history)
        self.metrics_layout.addWidget(self.sparkline)
        self.metrics_layout.addStretch(1)
        self.status.setText(f"llama.cpp: {self.model_name} | Temp: {self.metrics.get('temperature', 0.1)} | {self.metrics.get('tokens_per_second', 0)} tok/s")

    def copy_json(self) -> None:
        QGuiApplication.clipboard().setText(self.last_json)

    def copy_markdown(self) -> None:
        QGuiApplication.clipboard().setText(self.last_markdown)

    def export_output(self) -> None:
        selected = self.tabs.currentIndex()
        suffix = "md" if selected == 1 else "json"
        path, _ = QFileDialog.getSaveFileName(self, "Export Peke output", f"peke-output.{suffix}", "Markdown (*.md);;JSON (*.json)")
        if not path:
            return
        content = self.last_markdown if Path(path).suffix.lower() == ".md" or selected == 1 else self.last_json
        try:
            Path(path).write_text(content + "\n", encoding="utf-8")
        except OSError as exc:
            self.status.setText(f"Export failed: {exc}")

# Kept dependency-free: a tiny QPainter sparkline for recent run throughput.
class TokenSparkline(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.values: list[float] = []
        self.setMinimumHeight(42)

    def set_values(self, values: list[float]) -> None:
        self.values = values[-10:]
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QGuiApplication.palette().color(QPalette.ColorRole.Mid), 1))
        painter.drawText(0, 12, "Tokens/sec · last 10 runs")
        if len(self.values) < 2:
            painter.drawText(0, 32, "Run the pipeline to build a trend")
            return
        maximum = max(max(self.values), 1.0)
        width = max(1, self.width() - 8)
        height = max(1, self.height() - 22)
        points = []
        for index, value in enumerate(self.values):
            x = 4 + index * width / (len(self.values) - 1)
            y = 18 + height * (1 - value / maximum)
            points.append((int(x), int(y)))
        painter.setPen(QPen(QGuiApplication.palette().color(QPalette.ColorRole.Highlight), 2))
        for first, second in zip(points, points[1:]):
            painter.drawLine(first[0], first[1], second[0], second[1])
