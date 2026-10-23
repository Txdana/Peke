"""Startup splash banner widget for Peke GUI."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class SplashWidget(QWidget):
    """Terminal-styled banner widget displayed at launch or standard view header."""

    def __init__(self, mcp_active: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.init_ui(mcp_active)

    def init_ui(self, mcp_active: bool) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        mcp_chip = "[MCP Active]" if mcp_active else "[MCP Off]"
        banner_text = f"""
┌──────────────────────────────────────────────────────┐
│  PEKE  {mcp_chip:<12}                local: llama.cpp  │
└──────────────────────────────────────────────────────┘
  │
  ├── [01] REA Analysis  ──▶  Discovered Endpoint
  ├── [02] Scrapling     ──▶  Cloudflare Bypassed
  └── [03] Local SLM     ──▶  Clean JSON Formatted
"""
        label = QLabel(banner_text)
        label.setStyleSheet("font-family: monospace; color: #2D5A4C; font-weight: bold;")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)
