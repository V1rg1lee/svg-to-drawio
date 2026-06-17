"""Background workers for desktop batch conversions."""

from __future__ import annotations

import concurrent.futures
from os import makedirs
from os import path as osp
from threading import Event, Lock

from PySide6.QtCore import QObject, Signal, Slot
from svg_to_drawio.conversion_service import (
    CancellationToken,
    ConversionEvent,
    ConversionEventKind,
    ConversionJob,
    ConversionOptions,
    ConversionService,
    ConversionSummary,
    watch_svg_files,
)
from svg_to_drawio.converter import Converter
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
        service = ConversionService()
        options_signature = service._options_signature(self._options)
        try:
            jobs = service.plan(self._input_paths, self._options)
        except Exception as exc:
            self.failed.emit(str(exc))
            return

        total = len(jobs)
        self.event_emitted.emit(
            ConversionEvent(
                kind=ConversionEventKind.DISCOVERED,
                message="No SVG files found." if total == 0 else f"Found {total} SVG file(s) to convert.",
                completed=0,
                total=total,
            )
        )

        if total == 0:
            summary = ConversionSummary(total=0, converted=0, skipped=0, failed=0, reports=[])
            self.finished.emit(summary)
            return

        lock = Lock()
        counts: dict[str, int] = {"done": 0, "converted": 0, "skipped": 0, "failed": 0}
        reports: list[ConversionReport] = []

        def run_one(job: ConversionJob) -> None:
            if self._token.is_cancelled():
                return

            with lock:
                prog = counts["done"]
            self.event_emitted.emit(
                ConversionEvent(
                    kind=ConversionEventKind.STARTED,
                    message=f"Converting: {osp.basename(job.source_path)}",
                    completed=prog,
                    total=total,
                    source_path=job.source_path,
                    output_path=job.output_path,
                )
            )

            out_dir = osp.dirname(job.output_path)
            if out_dir and not osp.isdir(out_dir):
                makedirs(out_dir, exist_ok=True)

            if self._options.use_cache:
                cached_report = service._cache_for(job.output_path, self._options).get_cached_report(
                    job.source_path,
                    job.output_path,
                    options_signature=options_signature,
                )
                if cached_report is not None:
                    with lock:
                        counts["done"] += 1
                        counts["skipped"] += 1
                        prog = counts["done"]
                        reports.append(cached_report)
                    self.event_emitted.emit(
                        ConversionEvent(
                            kind=ConversionEventKind.SKIPPED,
                            message=(
                                f"Skipped unchanged (cache): {osp.basename(job.source_path)}  ->  {job.output_path}"
                            ),
                            completed=prog,
                            total=total,
                            source_path=job.source_path,
                            output_path=job.output_path,
                            report=cached_report,
                        )
                    )
                    return

            if osp.exists(job.output_path) and not self._options.overwrite:
                with lock:
                    counts["done"] += 1
                    counts["skipped"] += 1
                    prog = counts["done"]
                self.event_emitted.emit(
                    ConversionEvent(
                        kind=ConversionEventKind.SKIPPED,
                        message=f"Skipped existing: {osp.basename(job.source_path)}  ->  {job.output_path}",
                        completed=prog,
                        total=total,
                        source_path=job.source_path,
                        output_path=job.output_path,
                    )
                )
                return

            try:
                converter = Converter()
                written = converter.convert_file(
                    job.source_path,
                    out_path=job.output_path,
                    flatten=self._options.flatten,
                    max_elements=self._options.max_elements,
                    rendering_options=self._options.rendering,
                )
                report = converter.get_report()
                if self._options.use_cache:
                    service._cache_for(job.output_path, self._options).update(
                        job.source_path,
                        written,
                        options_signature=options_signature,
                        report=report,
                    )
                with lock:
                    counts["done"] += 1
                    counts["converted"] += 1
                    prog = counts["done"]
                    reports.append(report)
                self.event_emitted.emit(
                    ConversionEvent(
                        kind=ConversionEventKind.CONVERTED,
                        message=f"Converted: {osp.basename(job.source_path)}  ->  {written}",
                        completed=prog,
                        total=total,
                        source_path=job.source_path,
                        output_path=written,
                        report=report,
                    )
                )
            except Exception as exc:
                report = ConversionReport(source_path=job.source_path, output_path=job.output_path)
                report.add_issue("conversion-failed", "error", f"Conversion failed: {exc}")
                with lock:
                    counts["done"] += 1
                    counts["failed"] += 1
                    prog = counts["done"]
                    reports.append(report)
                self.event_emitted.emit(
                    ConversionEvent(
                        kind=ConversionEventKind.FAILED,
                        message=f"Failed: {osp.basename(job.source_path)}  ({exc})",
                        completed=prog,
                        total=total,
                        source_path=job.source_path,
                        error=str(exc),
                        report=report,
                    )
                )

        with concurrent.futures.ThreadPoolExecutor(max_workers=self._max_workers) as pool:
            futures = [pool.submit(run_one, job) for job in jobs]
            concurrent.futures.wait(futures)

        cancelled = self._token.is_cancelled()
        if cancelled:
            self.event_emitted.emit(
                ConversionEvent(
                    kind=ConversionEventKind.CANCELLED,
                    message=f"Cancelled after {counts['done']} file(s).",
                    completed=counts["done"],
                    total=total,
                )
            )

        summary = ConversionSummary(
            total=total,
            converted=counts["converted"],
            skipped=counts["skipped"],
            failed=counts["failed"],
            cancelled=cancelled,
            reports=reports,
        )
        self.finished.emit(summary)

    def request_cancel(self) -> None:
        """Signal all in-flight jobs to stop after their current file."""
        self._token.cancel()


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
            watch_svg_files(
                self._input_paths,
                self._options,
                reporter=self._emit_event,
                stop_event=self._stop_event,
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
