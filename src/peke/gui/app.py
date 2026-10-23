"""Application entrypoint for launching the PySide6 Peke GUI."""

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from peke.gui.main_window import MainWindow


def run_gui() -> None:
    """Initialize and run the PySide6 application loop."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    # Load QSS stylesheet
    qss_file = Path(__file__).parent / "theme.qss"
    if qss_file.exists():
        with open(qss_file, encoding="utf-8") as f:
            app.setStyleSheet(f.read())

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run_gui()
