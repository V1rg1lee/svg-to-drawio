"""Background workers for desktop batch conversions."""

from __future__ import annotations

import warnings
from threading import Event

from PySide6.QtCore import QObject, Signal, Slot
from svg_to_drawio.conversion_service import (
    CancellationToken,
    ConversionEvent,
    ConversionEventKind,
    ConversionOptions,
    ConversionService,
    ConversionSummary,
    event_watch_available,
    watch_svg_files,
)
from svg_to_drawio.diagnostics import ConversionReport


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
            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore",
                    message=r"SVG has more than .* drawable elements; output truncated\.",
                    category=RuntimeWarning,
                )
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


class ParallelConversionWorker(QObject):
    """Convert SVG files in parallel using a thread pool."""

    event_emitted = Signal(object)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, input_paths: list[str], options: ConversionOptions, max_workers: int = 4) -> None:
        super().__init__()
        self._input_paths = input_paths
        self._options = options
        self._max_workers = max_workers
        self._token = CancellationToken()

    @Slot()
    def run(self) -> None:
        """Plan jobs then convert them in parallel, emitting progress signals."""
        try:
            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore",
                    message=r"SVG has more than .* drawable elements; output truncated\.",
                    category=RuntimeWarning,
                )
                summary = ConversionService().convert_parallel(
                    self._input_paths,
                    self._options,
                    max_workers=self._max_workers,
                    reporter=self._emit_event,
                    cancellation_token=self._token,
                )
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.finished.emit(summary)

    def request_cancel(self) -> None:
        """Signal all in-flight jobs to stop after their current file."""
        self._token.cancel()

    def _emit_event(self, event: ConversionEvent) -> None:
        """Forward service events through a Qt signal."""
        self.event_emitted.emit(event)


class WatchConversionWorker(QObject):
    """Continuously convert queued SVGs whenever they change on disk."""

    event_emitted = Signal(object)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, input_paths: list[str], options: ConversionOptions) -> None:
        super().__init__()
        self._input_paths = input_paths
        self._options = options
        self._stop_event = Event()
        self._converted = 0
        self._skipped = 0
        self._failed = 0
        self._reports: list[ConversionReport] = []

    @Slot()
    def run(self) -> None:
        """Run the initial conversion, then stay alive until cancellation is requested."""
        try:
            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore",
                    message=r"SVG has more than .* drawable elements; output truncated\.",
                    category=RuntimeWarning,
                )
                watch_svg_files(
                    self._input_paths,
                    self._options,
                    reporter=self._emit_event,
                    stop_event=self._stop_event,
                    backend="event" if event_watch_available() else "poll",
                )
        except Exception as exc:  # pragma: no cover - driven by GUI/runtime behavior
            self.failed.emit(str(exc))
            return

        total = self._converted + self._skipped + self._failed
        summary = ConversionSummary(
            total=total,
            converted=self._converted,
            skipped=self._skipped,
            failed=self._failed,
            cancelled=True,
            reports=list(self._reports),
        )
        self.finished.emit(summary)

    def request_cancel(self) -> None:
        """Stop the watch loop after the current poll / conversion cycle finishes."""
        self._stop_event.set()

    def _emit_event(self, event: ConversionEvent) -> None:
        """Track watch-session totals and forward each event to the UI thread."""
        if event.kind == ConversionEventKind.CONVERTED:
            self._converted += 1
        elif event.kind == ConversionEventKind.SKIPPED:
            self._skipped += 1
        elif event.kind == ConversionEventKind.FAILED:
            self._failed += 1
        if event.report is not None:
            self._reports.append(event.report)
        self.event_emitted.emit(event)
