"""Background worker for desktop batch conversions."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot
from svg_to_drawio.conversion_service import (
    CancellationToken,
    ConversionEvent,
    ConversionOptions,
    ConversionService,
)


class ConversionWorker(QObject):
    """Run one conversion batch in a worker thread."""

    event_emitted = Signal(object)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        input_paths: list[str],
        options: ConversionOptions,
        service: ConversionService | None = None,
    ) -> None:
        super().__init__()
        self._input_paths = input_paths
        self._options = options
        self._service = service or ConversionService()
        self._token = CancellationToken()

    @Slot()
    def run(self) -> None:
        """Execute the batch conversion and forward progress signals."""
        try:
            summary = self._service.convert(
                self._input_paths,
                self._options,
                reporter=self._emit_event,
                cancellation_token=self._token,
            )
        except Exception as exc:  # pragma: no cover - driven by GUI interactions
            self.failed.emit(str(exc))
            return
        self.finished.emit(summary)

    def request_cancel(self) -> None:
        """Ask the worker to stop before starting the next file."""
        self._token.cancel()

    def _emit_event(self, event: ConversionEvent) -> None:
        """Forward service events through a Qt signal."""
        self.event_emitted.emit(event)
