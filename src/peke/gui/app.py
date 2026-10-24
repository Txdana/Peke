"""GUI bootstrap, optional splash and asynchronous startup model loading."""
import logging
import os
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QSettings, QThread, Signal, Slot
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
        extractor = Extractor(load_settings())
        if extractor.settings.model_path is not None:
            try:
                extractor._model()
            except Exception as exc:
                message = f"Local model could not be loaded during startup: {exc}"
                logger.warning(message)
                self.warning.emit(message)
        self.finished.emit(extractor)


def run_gui(no_splash: bool = False) -> int:
    """Launch the desktop app while model warm-up runs outside the UI thread."""
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Peke")
    app.setOrganizationName("Peke")
    icon_png = Path(__file__).parent / "assets" / "peke.png"
    icon_svg = Path(__file__).parent / "assets" / "peke.svg"
    icon_path = icon_png if icon_png.is_file() else icon_svg
    app.setWindowIcon(QIcon(str(icon_path)))
    register_fonts()
    app.setFont(QFont("DM Sans", 10))
    app.setStyleSheet(load_stylesheet())
    window = MainWindow()
    splash_enabled = not no_splash and SplashScreen.enabled_by_setting()
    reduced_motion = os.environ.get("PEKE_REDUCED_MOTION", "").lower() in {"1", "true", "yes"}
    splash = SplashScreen(reduced_motion=reduced_motion) if splash_enabled else None
    if splash is not None:
        screen = app.primaryScreen()
        if screen is not None:
            splash.move(screen.availableGeometry().center() - splash.rect().center())
        splash.dismissed.connect(window.show)
        splash.show()

    startup_thread = QThread(app)
    startup_worker = StartupWorker()
    startup_worker.moveToThread(startup_thread)
    startup_thread.started.connect(startup_worker.run)

    def startup_ready(extractor: Extractor) -> None:
        window._extractor = extractor
        if splash is not None:
            splash.close()
        if not window.isVisible():
            window.show()
        # First-run onboarding is deliberately in-app. Never invoke CLI setup or
        # download a model automatically; the user chooses their own GGUF file.
        onboarding = QSettings("Peke", "PekeWorkbench")
        if not onboarding.value("first_run_complete", False, type=bool):
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
        startup_thread.quit()

    startup_worker.finished.connect(startup_ready)
    def show_startup_warning(message: str) -> None:
        logger.warning("%s", message)
        from datetime import datetime, timezone

        from peke.pipeline import Event

        event = Event(datetime.now(timezone.utc).isoformat(), "discover", "warn", message, "MODEL")
        window.workspace.target_page.console.append_event(event)

    startup_worker.warning.connect(show_startup_warning)
    startup_worker.finished.connect(startup_worker.deleteLater)
    startup_thread.finished.connect(startup_thread.deleteLater)
    # Keep references alive for the lifetime of the startup operation.
    app._peke_startup_thread = startup_thread
    app._peke_startup_worker = startup_worker
    startup_thread.start()
    return app.exec()
