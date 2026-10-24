"""Import and instantiate the desktop window without entering the event loop."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from peke.gui.main_window import MainWindow


def main() -> int:
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("Peke-smoke-test")
    window = MainWindow()
    assert window is not None
    window.close()
    app.processEvents()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
