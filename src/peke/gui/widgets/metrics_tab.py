"""Markdown summary view and execution metrics tab with QPainter sparkline."""

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from peke.extract import ExtractionResult


class SparklineWidget(QWidget):
    """Mini sparkline chart rendering tokens/sec across the last 10 runs using QPainter."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.history: list[float] = [0.0] * 10
        self.setFixedHeight(40)
        self.setMinimumWidth(150)

    def add_value(self, val: float) -> None:
        self.history.append(float(val))
        if len(self.history) > 10:
            self.history.pop(0)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()
        painter.fillRect(rect, QColor("#181818"))

        if not self.history or all(v == 0 for v in self.history):
            painter.setPen(QPen(QColor("#666666"), 1))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "No token metrics")
            return

        max_val = max(self.history) or 1.0
        min_val = min(self.history)

        w = rect.width() - 10
        h = rect.height() - 10
        step = w / max(1, len(self.history) - 1)

        points = []
        for i, val in enumerate(self.history):
            x = 5 + i * step
            norm = (val - min_val) / (max_val - min_val) if max_val > min_val else 0.5
            y = rect.height() - 5 - (norm * h)
            points.append(QPointF(x, y))

        pen = QPen(QColor("#2D5A4C"), 2)
        painter.setPen(pen)

        for i in range(len(points) - 1):
            painter.drawLine(points[i], points[i + 1])


class MetricsTabWidget(QWidget):
    """Tab displaying Markdown summary and execution metrics with sparkline."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.init_ui()

    def init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Markdown Section
        md_header = QHBoxLayout()
        md_header.addWidget(QLabel("Markdown Output Summary:"))
        md_header.addStretch()

        self.copy_md_btn = QPushButton("Copy Markdown")
        self.copy_md_btn.clicked.connect(self.copy_markdown)
        md_header.addWidget(self.copy_md_btn)

        layout.addLayout(md_header)

        self.md_view = QTextEdit()
        self.md_view.setReadOnly(True)
        self.md_view.setStyleSheet("background-color: #1E1E1E; color: #E0E0E0;")
        layout.addWidget(self.md_view)

        # Metrics Section Header
        layout.addWidget(QLabel("Pipeline Execution Metrics:"))

        grid = QGridLayout()
        grid.setSpacing(10)

        self.lbl_model = QLabel("Model: N/A")
        self.lbl_n_ctx = QLabel("n_ctx: 2048")
        self.lbl_n_gpu = QLabel("n_gpu_layers: 0")
        self.lbl_temp = QLabel("Temp: 0.1")

        self.lbl_tok_sec = QLabel("Tokens/sec: 0.0")
        self.lbl_retries = QLabel("Retries: 0")
        self.lbl_fetch_time = QLabel("Fetch time: 0.00s")
        self.lbl_total_time = QLabel("Total time: 0.00s")

        grid.addWidget(self.lbl_model, 0, 0)
        grid.addWidget(self.lbl_n_ctx, 0, 1)
        grid.addWidget(self.lbl_n_gpu, 0, 2)
        grid.addWidget(self.lbl_temp, 0, 3)

        grid.addWidget(self.lbl_tok_sec, 1, 0)
        grid.addWidget(self.lbl_retries, 1, 1)
        grid.addWidget(self.lbl_fetch_time, 1, 2)
        grid.addWidget(self.lbl_total_time, 1, 3)

        layout.addLayout(grid)

        # Sparkline Section
        spark_layout = QHBoxLayout()
        spark_layout.addWidget(QLabel("Tokens/sec History (Last 10 Runs):"))
        self.sparkline = SparklineWidget()
        spark_layout.addWidget(self.sparkline)
        spark_layout.addStretch()

        layout.addLayout(spark_layout)

    def set_extraction_result(
        self,
        res: ExtractionResult | None,
        fetch_time: float = 0.0,
        total_time: float = 0.0,
    ) -> None:
        if res is not None:
            self.md_view.setMarkdown(res.markdown_output or "")
            self.lbl_model.setText(f"Model: {res.model_name}")
            self.lbl_temp.setText(f"Temp: {res.temperature:.1f}")
            self.lbl_tok_sec.setText(f"Tokens/sec: {res.tokens_per_second:.1f}")
            self.lbl_retries.setText(f"Retries: {res.retries}")

            self.sparkline.add_value(res.tokens_per_second)
        else:
            self.md_view.clear()
            self.lbl_model.setText("Model: N/A")
            self.lbl_tok_sec.setText("Tokens/sec: 0.0")

        self.lbl_fetch_time.setText(f"Fetch time: {fetch_time:.2f}s")
        self.lbl_total_time.setText(f"Total time: {total_time:.2f}s")

    def copy_markdown(self) -> None:
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(self.md_view.toPlainText())
