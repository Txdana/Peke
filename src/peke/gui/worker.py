"""Pipeline worker executed on a dedicated QThread."""
import threading
from pathlib import Path

from PySide6.QtCore import QObject, QSettings, Signal, Slot

from peke.config import load_settings
from peke.extract import Extractor
from peke.pipeline import Pipeline
from peke.profile import Profile, ProfileError, load_profile


class PipelineWorker(QObject):
    event = Signal(object)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, url: str, fetcher: str, parent=None, extractor: Extractor | None = None) -> None:
        super().__init__(parent)
        self.url = url
        self.fetcher = fetcher
        self._cancel_requested = threading.Event()
        self.extractor = extractor

    def cancel(self) -> None:
        self._cancel_requested.set()

    @Slot()
    def run(self) -> None:
        if self._cancel_requested.is_set():
            self.failed.emit("Pipeline cancelled before it started.")
            return
        try:
            settings = QSettings("Peke", "PekeWorkbench")
            selected = settings.value("selected_endpoint", {})
            if not isinstance(selected, dict):
                selected = {}
            saved_path = str(settings.value("active_profile", ""))
            profile = None
            if saved_path and Path(saved_path).is_file():
                try:
                    profile = load_profile(saved_path).model_copy(update={"url": self.url, "fetcher": self.fetcher})
                    if selected and self.url.endswith(str(selected.get("path", "\0"))):
                        profile = profile.model_copy(update={"mode": "api", "method": selected.get("method", "GET"),
                                                             "params": selected.get("params", {}),
                                                             "headers": selected.get("headers", {})})
                except (ProfileError, OSError, ValueError):
                    profile = None
            if profile is None:
                profile = Profile(name="GUI target", url=self.url, fetcher=self.fetcher,
                                  schema_name=str(settings.value("active_schema", "Article")),
                                  mode="api" if selected and self.url.endswith(str(selected.get("path", "\0"))) else "auto",
                                  method=str(selected.get("method", "GET")), params=selected.get("params", {}),
                                  headers=selected.get("headers", {}))
            pipeline = Pipeline(settings=load_settings(), on_event=self.event.emit, extractor=self.extractor,
                                cancel_check=self._cancel_requested.is_set)
            self.extractor = pipeline.extractor
            if self._cancel_requested.is_set():
                self.failed.emit("Pipeline cancelled before fetching.")
                return
            result = pipeline.run(profile)
            if self._cancel_requested.is_set():
                self.failed.emit("Cancellation requested; an active network/model call may finish before cancellation takes effect.")
            else:
                self.finished.emit(result)
        except Exception as exc:
            self.failed.emit(f"Pipeline failed: {exc}")
