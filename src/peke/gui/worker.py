"""Pipeline background QThread worker for Peke GUI."""

import time
from typing import Any

from PySide6.QtCore import QThread, Signal

from peke.pipeline import Pipeline, PipelineEvent, PipelineResult


class PipelineWorker(QThread):
    """Background worker thread executing Peke Pipeline with cancellation support and cached LLM."""

    sig_event_emitted = Signal(object)  # PipelineEvent
    sig_finished = Signal(object)      # PipelineResult or None
    sig_cancelled = Signal()

    _cached_extractor: Any = None  # Class-level cache to keep llama.cpp model loaded between runs

    def __init__(
        self,
        target_input: Any,
        fetcher_type: str = "Fetcher",
        schema_name: str = "Article",
        parent: QThread | None = None,
    ) -> None:
        super().__init__(parent)
        self.target_input = target_input
        self.fetcher_type = fetcher_type
        self.schema_name = schema_name
        self.is_cancelled = False

    def cancel(self) -> None:
        """Signal worker to cancel pipeline execution at next check."""
        self.is_cancelled = True

    def run(self) -> None:
        """Execute pipeline in worker thread."""
        time.time()

        def event_callback(event: PipelineEvent) -> None:
            if not self.is_cancelled:
                self.sig_event_emitted.emit(event)

        pipeline = Pipeline(
            event_callback=event_callback,
            extractor_override=PipelineWorker._cached_extractor,
        )

        try:
            result: PipelineResult = pipeline.run(
                self.target_input, schema_override=self.schema_name
            )

            if self.is_cancelled:
                self.sig_cancelled.emit()
                return

            self.sig_finished.emit(result)

        except Exception as e:
            if self.is_cancelled:
                self.sig_cancelled.emit()
            else:
                err_event = PipelineEvent(
                    timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
                    stage="PIPELINE",
                    level="ERROR",
                    message=f"Pipeline execution error: {e}",
                )
                self.sig_event_emitted.emit(err_event)
                self.sig_finished.emit(None)

    @classmethod
    def unload_cached_model(cls) -> None:
        """Unload and clear cached LLM instance on app shutdown."""
        cls._cached_extractor = None
