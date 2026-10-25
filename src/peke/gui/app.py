"""GUI bootstrap, optional splash and asynchronous startup model loading."""
from __future__ import annotations

import faulthandler
import logging
import os
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QSettings, QThread, QTimer, Signal, Slot
from PySide6.QtGui import QFont, QFontDatabase, QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from peke.config import load_settings
from peke.extract import Extractor
from peke.gui.main_window import MainWindow
from peke.gui.splash import SplashScreen
from peke.gui.theme import load_stylesheet

logger = logging.getLogger(__name__)


def register_fonts() -> None:
    """Register bundled font files where present; Qt/system fonts remain fallback."""
    fonts_dir = Path(__file__).parent / "assets" / "fonts"
    if fonts_dir.exists():
        for path in fonts_dir.glob("*.*"):
            if path.suffix.lower() in {".ttf", ".otf"}:
                if QFontDatabase.addApplicationFont(str(path)) < 0:
                    logger.warning("Could not register font %s; using system fallback", path.name)


class StartupWorker(QObject):
    """Warm the configured local model off the GUI thread when one is configured."""
    finished = Signal(object)
    warning = Signal(str)

    @Slot()
    def run(self) -> None:
        extractor = None
        try:
            extractor = Extractor(load_settings())
            if extractor.settings.model_path is not None:
                try:
                    extractor._model()
                except Exception as exc:
                    message = f"Local model could not be loaded during startup: {exc}"
                    logger.warning(message)
                    self.warning.emit(message)
        except Exception as exc:  # noqa: BLE001 - startup must always hand control back
            logger.exception("Startup worker failed")
            self.warning.emit(f"Startup warm-up failed: {exc}")
        finally:
            # Always report back, otherwise the splash would wait forever.
            self.finished.emit(extractor)


class StartupBridge(QObject):
    """Receives startup results on the GUI thread.

    Qt only runs a slot in the receiver's thread when the receiver is a QObject that
    lives there. A plain Python function connected to a signal emitted by the worker
    thread is called *on the worker thread*, and touching widgets from there freezes
    or blanks the window. Keeping the handlers on this QObject (created on the GUI
    thread) makes Qt queue the calls onto the GUI event loop.
    """

    def __init__(self, window: MainWindow, splash: SplashScreen | None, thread: QThread) -> None:
        super().__init__()
        self._window = window
        self._splash = splash
        self._thread = thread
        self._shown = False

    def _show_window(self) -> None:
        # Show the main window BEFORE closing the splash. If the splash is the only
        # visible top-level window when it closes, Qt's quitOnLastWindowClosed ends the
        # event loop and the app exits silently with code 0 (nothing ever appears).
        if not self._window.isVisible():
            self._window.show()
        self._window.raise_()
        self._window.activateWindow()
        if self._splash is not None:
            self._splash.close()
        app = QApplication.instance()
        if app is not None:
            app.setQuitOnLastWindowClosed(True)
        self._shown = True
        faulthandler.cancel_dump_traceback_later()

    @Slot(object)
    def on_ready(self, extractor) -> None:
        if extractor is not None:
            self._window._extractor = extractor
        self._show_window()
        self._thread.quit()
        # Let the window paint first, then show the first-run dialog.
        QTimer.singleShot(0, self._maybe_show_welcome)

    @Slot(str)
    def on_warning(self, message: str) -> None:
        logger.warning("%s", message)
        from datetime import datetime, timezone

        from peke.pipeline import Event

        event = Event(datetime.now(timezone.utc).isoformat(), "discover", "warn", message, "MODEL")
        self._window.workspace.target_page.console.append_event(event)

    @Slot()
    def on_timeout(self) -> None:
        """Failsafe: never leave the user staring at a splash/black screen."""
        if not self._shown:
            logger.error("Startup did not finish in time; showing the main window anyway")
            self._show_window()

    def _maybe_show_welcome(self) -> None:
        window = self._window
        # First-run onboarding is deliberately in-app. Never invoke CLI setup or
        # download a model automatically; the user chooses their own GGUF file.
        onboarding = QSettings("Peke", "PekeWorkbench")
        if onboarding.value("first_run_complete", False, type=bool):
            return
        welcome = QMessageBox(window)
        welcome.setWindowTitle("Welcome to Peke")
        welcome.setIcon(QMessageBox.Icon.Information)
        welcome.setText("Welcome to Peke")
        welcome.setInformativeText(
            "Peke is ready to use. You can run supported deterministic extraction "
            "without a language model. For local AI extraction, open Providers → Local GGUF Model "
            "and choose a .gguf model already on your computer. Peke will not "
            "download model weights automatically."
        )
        choose_model = welcome.addButton("Choose model…", QMessageBox.ButtonRole.ActionRole)
        welcome.addButton("Continue", QMessageBox.ButtonRole.AcceptRole)
        welcome.exec()
        onboarding.setValue("first_run_complete", True)
        if welcome.clickedButton() == choose_model:
            window.workspace.setCurrentWidget(window.workspace.providers_page)
            chooser = getattr(window.workspace.providers_page, "choose_model", None)
            if callable(chooser):
                chooser()


def _install_qt_logging() -> None:
    """Route Qt's own warnings (plugin, OpenGL, font errors) into the Python log."""
    from PySide6.QtCore import QtMsgType, qInstallMessageHandler

    levels = {
        QtMsgType.QtDebugMsg: logging.DEBUG,
        QtMsgType.QtInfoMsg: logging.INFO,
        QtMsgType.QtWarningMsg: logging.WARNING,
        QtMsgType.QtCriticalMsg: logging.ERROR,
        QtMsgType.QtFatalMsg: logging.CRITICAL,
    }

    def handler(mode, context, message) -> None:
        logging.getLogger("qt").log(levels.get(mode, logging.WARNING), "%s", message)

    qInstallMessageHandler(handler)


def _set_windows_app_id() -> None:
    """Give Windows a stable taskbar identity (icon grouping, notifications)."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Peke.PekeWorkbench")
    except (AttributeError, OSError):
        pass


STARTUP_TIMEOUT_MS = 10_000


def run_gui(no_splash: bool = False) -> int:
    """Launch the desktop app while model warm-up runs outside the UI thread."""
    _set_windows_app_id()
    _install_qt_logging()
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Peke")
    app.setOrganizationName("Peke")
    # Fusion renders QSS predictably; native Windows 11 style + heavy QSS is glitchy/slow.
    # TagStudio (a shipping PySide6 + PyInstaller app) does the same.
    app.setStyle("Fusion")
    icon_png = Path(__file__).parent / "assets" / "peke.png"
    icon_svg = Path(__file__).parent / "assets" / "peke.svg"
    icon_path = icon_png if icon_png.is_file() else icon_svg
    app.setWindowIcon(QIcon(str(icon_path)))
    register_fonts()
    app.setFont(QFont("DM Sans", 10))
    app.setStyleSheet(load_stylesheet())
    # Do not let closing the splash (a top-level window) end the app before the main
    # window exists; StartupBridge re-enables this once the main window is visible.
    app.setQuitOnLastWindowClosed(False)
    # Show the splash FIRST, then build the heavy main window, so the user sees
    # something immediately instead of several seconds of nothing (cold frozen start).
    splash_enabled = not no_splash and SplashScreen.enabled_by_setting()
    reduced_motion = os.environ.get("PEKE_REDUCED_MOTION", "").lower() in {"1", "true", "yes"}
    splash = SplashScreen(reduced_motion=reduced_motion) if splash_enabled else None
    if splash is not None:
        screen = app.primaryScreen()
        if screen is not None:
            splash.move(screen.availableGeometry().center() - splash.rect().center())
        splash.show()
        app.processEvents()
    window = MainWindow()
    if splash is not None:
        splash.dismissed.connect(window.show)

    startup_thread = QThread(app)
    startup_worker = StartupWorker()
    startup_worker.moveToThread(startup_thread)
    bridge = StartupBridge(window, splash, startup_thread)  # created on the GUI thread
    startup_thread.started.connect(startup_worker.run)
    startup_worker.warning.connect(bridge.on_warning)
    startup_worker.finished.connect(bridge.on_ready)
    startup_worker.finished.connect(startup_worker.deleteLater)
    startup_thread.finished.connect(startup_thread.deleteLater)
    # Keep references alive for the lifetime of the startup operation.
    app._peke_startup_thread = startup_thread
    app._peke_startup_worker = startup_worker
    app._peke_startup_bridge = bridge
    QTimer.singleShot(STARTUP_TIMEOUT_MS, bridge.on_timeout)
    startup_thread.start()
    return app.exec()
