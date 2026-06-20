"""Shared file-system conversion service used by both the CLI and desktop app."""

from __future__ import annotations

import concurrent.futures
import importlib.util
import json
import os
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from os import PathLike, makedirs, path
from threading import Event, Lock
from typing import Any, Literal

from . import __version__
from .conversion_cache import ConversionCache, default_manifest_path
from .converter import Converter
from .diagnostics import ConversionReport
from .rendering_options import RenderingOptions

Reporter = Callable[["ConversionEvent"], None]
WatchBackend = Literal["auto", "poll", "event"]


class ConversionEventKind(StrEnum):
    """High-level events emitted while converting files."""

    DISCOVERED = "discovered"
    STARTED = "started"
    CONVERTED = "converted"
    SKIPPED = "skipped"
    FAILED = "failed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


@dataclass(frozen=True)
class ConversionOptions:
    """User-configurable settings for a batch conversion run."""

    output_dir: str | None = None
    recursive: bool = False
    overwrite: bool = False
    flatten: bool = False
    max_elements: int | None = None
    use_cache: bool = True
    rendering: RenderingOptions = field(default_factory=RenderingOptions)


@dataclass(frozen=True)
class ConversionJob:
    """One concrete SVG-to-draw.io conversion to execute."""

    source_path: str
    output_path: str


@dataclass(frozen=True)
class ConversionSummary:
    """Final counters for one batch conversion run."""

    total: int
    converted: int
    skipped: int
    failed: int
    cancelled: bool = False
    reports: list[ConversionReport] = field(default_factory=list)

    @property
    def exit_code(self) -> int:
        """Return the CLI-style exit code for the completed batch."""
        return 1 if self.failed else 0

    def to_status_line(self) -> str:
        """Render a stable human-readable batch summary."""
        suffix = " before cancellation" if self.cancelled else ""
        return f"Summary: {self.converted} converted, {self.skipped} skipped, {self.failed} failed{suffix}"

    def to_dict(self) -> dict[str, object]:
        """Serialize the batch summary into a JSON-friendly dictionary."""
        return {
            "total": self.total,
            "converted": self.converted,
            "skipped": self.skipped,
            "failed": self.failed,
            "cancelled": self.cancelled,
            "reports": [report.to_dict() for report in self.reports],
        }


@dataclass(frozen=True)
class ConversionEvent:
    """Progress event emitted during a batch conversion run."""

    kind: ConversionEventKind
    message: str
    completed: int
    total: int
    source_path: str | None = None
    output_path: str | None = None
    error: str | None = None
    summary: ConversionSummary | None = None
    report: ConversionReport | None = None


class CancellationToken:
    """Cooperative cancellation token shared between the UI thread and worker."""

    def __init__(self) -> None:
        self._event = Event()

    def cancel(self) -> None:
        """Request cancellation of the current batch."""
        self._event.set()

    def is_cancelled(self) -> bool:
        """Return whether cancellation has been requested."""
        return self._event.is_set()


def iter_svg_files(input_path: str, recursive: bool = False) -> list[str]:
    """Return every SVG represented by *input_path*."""
    if path.isfile(input_path):
        return [input_path] if input_path.lower().endswith(".svg") else []

    svg_paths: list[str] = []
    if recursive:
        for root, _, files in os.walk(input_path):
            for name in sorted(files):
                if name.lower().endswith(".svg"):
                    svg_paths.append(path.join(root, name))
        return svg_paths

    for name in sorted(os.listdir(input_path)):
        file_path = path.join(input_path, name)
        if path.isfile(file_path) and name.lower().endswith(".svg"):
            svg_paths.append(file_path)
    return svg_paths


def event_watch_available() -> bool:
    """Return whether the optional watchdog backend is available."""
    try:
        return (
            importlib.util.find_spec("watchdog.events") is not None
            and importlib.util.find_spec("watchdog.observers") is not None
        )
    except ModuleNotFoundError:
        # find_spec("pkg.submodule") raises instead of returning None when the
        # parent package itself ("watchdog") isn't installed at all.
        return False


def resolve_watch_backend(backend: WatchBackend) -> Literal["poll", "event"]:
    """Resolve the requested watch backend into a concrete implementation name."""
    if backend == "poll":
        return "poll"
    if backend == "event":
        if not event_watch_available():
            raise RuntimeError(
                "The event-driven watch backend requires the optional 'watchdog' package to be installed."
            )
        return "event"
    return "event" if event_watch_available() else "poll"


def build_output_path(
    svg_path: str,
    input_root: str | None = None,
    output_dir: str | None = None,
    namespace: str | None = None,
) -> str:
    """Compute the destination `.drawio` path for one SVG file."""
    if output_dir is None:
        return path.splitext(svg_path)[0] + ".drawio"

    if input_root and path.isdir(input_root):
        rel_path = path.relpath(svg_path, input_root)
        rel_base = path.splitext(rel_path)[0] + ".drawio"
    else:
        rel_base = path.splitext(path.basename(svg_path))[0] + ".drawio"

    if namespace:
        rel_base = path.join(namespace, rel_base)
    return path.join(output_dir, rel_base)


def _input_namespace(input_path: str) -> str:
    """Return a stable per-input namespace for multi-root output folders."""
    basename = path.basename(path.normpath(input_path))
    stem, _ = path.splitext(basename)
    return stem or basename or "input"


def _dedupe_jobs(jobs: Sequence[ConversionJob]) -> list[ConversionJob]:
    """Ensure planned output paths stay unique when multiple roots collide."""
    used: set[str] = set()
    deduped: list[ConversionJob] = []

    for job in jobs:
        candidate = job.output_path
        stem, ext = path.splitext(candidate)
        suffix = 2
        key = path.normcase(path.normpath(candidate))
        while key in used:
            candidate = f"{stem}-{suffix}{ext}"
            key = path.normcase(path.normpath(candidate))
            suffix += 1
        used.add(key)
        deduped.append(ConversionJob(source_path=job.source_path, output_path=candidate))

    return deduped


class ConversionService:
    """Shared high-level service for converting SVG files and directories."""

    def __init__(self, converter_factory: Callable[[], Converter] | None = None) -> None:
        self._converter_factory = converter_factory or Converter
        self._caches: dict[str, ConversionCache] = {}

    def _cache_for(self, output_path: str, options: ConversionOptions) -> ConversionCache:
        """Return the persistent cache object for one output location."""
        manifest_path = default_manifest_path(output_path, options.output_dir)
        cache = self._caches.get(manifest_path)
        if cache is None:
            cache = ConversionCache(manifest_path)
            self._caches[manifest_path] = cache
        return cache

    @staticmethod
    def _options_signature(options: ConversionOptions) -> str:
        """Return the content-affecting option signature for cache invalidation.

        Includes the package version so upgrading the engine invalidates old cache
        entries automatically, even when none of the other signature fields changed.
        """
        payload = {
            "engine_version": __version__,
            "flatten": options.flatten,
            "max_elements": options.max_elements,
            "rendering": options.rendering.to_dict(),
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))

    def plan(
        self,
        input_paths: Sequence[str | PathLike[str]],
        options: ConversionOptions,
    ) -> list[ConversionJob]:
        """Expand input files and directories into concrete conversion jobs."""
        if not input_paths:
            raise ValueError("At least one input path is required.")

        resolved_inputs = [path.abspath(os.fspath(item)) for item in input_paths]
        missing = [item for item in resolved_inputs if not path.exists(item)]
        if missing:
            raise FileNotFoundError(missing[0])

        namespace_outputs = options.output_dir is not None and len(resolved_inputs) > 1
        jobs: list[ConversionJob] = []

        for resolved_input in resolved_inputs:
            svg_paths = iter_svg_files(resolved_input, recursive=options.recursive)
            input_root = resolved_input if path.isdir(resolved_input) else None
            namespace = _input_namespace(resolved_input) if namespace_outputs else None
            jobs.extend(
                ConversionJob(
                    source_path=svg_path,
                    output_path=build_output_path(
                        svg_path,
                        input_root=input_root,
                        output_dir=options.output_dir,
                        namespace=namespace,
                    ),
                )
                for svg_path in svg_paths
            )

        return _dedupe_jobs(jobs)

    def convert(
        self,
        input_paths: Sequence[str | PathLike[str]],
        options: ConversionOptions,
        *,
        reporter: Reporter | None = None,
        cancellation_token: CancellationToken | None = None,
    ) -> ConversionSummary:
        """Convert every planned SVG and emit progress events along the way."""
        jobs = self.plan(input_paths, options)
        total = len(jobs)

        self._report(
            reporter,
            ConversionEventKind.DISCOVERED,
            "No SVG files found." if total == 0 else f"Found {total} SVG file(s) to convert.",
            completed=0,
            total=total,
        )

        converted = 0
        skipped = 0
        failed = 0
        cancelled = False
        reports: list[ConversionReport] = []
        options_signature = self._options_signature(options)

        for index, job in enumerate(jobs, start=1):
            if cancellation_token and cancellation_token.is_cancelled():
                cancelled = True
                break

            self._report(
                reporter,
                ConversionEventKind.STARTED,
                f"[{index}/{total}] Converting: {job.source_path}",
                completed=index - 1,
                total=total,
                source_path=job.source_path,
                output_path=job.output_path,
            )

            out_dir = path.dirname(job.output_path)
            if out_dir and not path.isdir(out_dir):
                makedirs(out_dir, exist_ok=True)

            if options.use_cache:
                cached_report = self._cache_for(job.output_path, options).get_cached_report(
                    job.source_path,
                    job.output_path,
                    options_signature=options_signature,
                )
                if cached_report is not None:
                    skipped += 1
                    reports.append(cached_report)
                    self._report(
                        reporter,
                        ConversionEventKind.SKIPPED,
                        f"Skipped unchanged (cache): {path.basename(job.source_path)}  ->  {job.output_path}",
                        completed=index,
                        total=total,
                        source_path=job.source_path,
                        output_path=job.output_path,
                        report=cached_report,
                    )
                    continue

            if path.exists(job.output_path) and not options.overwrite:
                skipped += 1
                self._report(
                    reporter,
                    ConversionEventKind.SKIPPED,
                    f"Skipped existing: {path.basename(job.source_path)}  ->  {job.output_path}",
                    completed=index,
                    total=total,
                    source_path=job.source_path,
                    output_path=job.output_path,
                )
                continue

            try:
                converter = self._converter_factory()
                written = converter.convert_file(
                    job.source_path,
                    out_path=job.output_path,
                    flatten=options.flatten,
                    max_elements=options.max_elements,
                    rendering_options=options.rendering,
                )
                report = converter.get_report()
            except Exception as exc:  # pragma: no cover - intentionally user-facing
                failed += 1
                report = ConversionReport(source_path=job.source_path, output_path=job.output_path)
                report.add_issue(
                    "conversion-failed",
                    "error",
                    f"Conversion failed: {exc}",
                )
                reports.append(report)
                self._report(
                    reporter,
                    ConversionEventKind.FAILED,
                    f"Failed: {job.source_path}  ({exc})",
                    completed=index,
                    total=total,
                    source_path=job.source_path,
                    output_path=job.output_path,
                    error=str(exc),
                    report=report,
                )
                continue

            converted += 1
            reports.append(report)
            if options.use_cache:
                self._cache_for(job.output_path, options).update(
                    job.source_path,
                    written,
                    options_signature=options_signature,
                    report=report,
                )
            self._report(
                reporter,
                ConversionEventKind.CONVERTED,
                f"Converted: {job.source_path}  ->  {written}",
                completed=index,
                total=total,
                source_path=job.source_path,
                output_path=written,
                report=report,
            )

        if cancellation_token and cancellation_token.is_cancelled():
            cancelled = True
            completed = converted + skipped + failed
            self._report(
                reporter,
                ConversionEventKind.CANCELLED,
                f"Cancellation requested after {completed} processed file(s).",
                completed=completed,
                total=total,
            )

        summary = ConversionSummary(
            total=total,
            converted=converted,
            skipped=skipped,
            failed=failed,
            cancelled=cancelled,
            reports=reports,
        )
        self._report(
            reporter,
            ConversionEventKind.COMPLETED,
            summary.to_status_line(),
            completed=converted + skipped + failed,
            total=total,
            summary=summary,
        )
        return summary

    def convert_parallel(
        self,
        input_paths: Sequence[str | PathLike[str]],
        options: ConversionOptions,
        *,
        max_workers: int = 4,
        reporter: Reporter | None = None,
        cancellation_token: CancellationToken | None = None,
    ) -> ConversionSummary:
        """Convert every planned SVG in parallel while keeping batch semantics stable."""
        jobs = self.plan(input_paths, options)
        total = len(jobs)

        self._report(
            reporter,
            ConversionEventKind.DISCOVERED,
            "No SVG files found." if total == 0 else f"Found {total} SVG file(s) to convert.",
            completed=0,
            total=total,
        )
        if total == 0:
            summary = ConversionSummary(total=0, converted=0, skipped=0, failed=0, reports=[])
            self._report(
                reporter,
                ConversionEventKind.COMPLETED,
                summary.to_status_line(),
                completed=0,
                total=0,
                summary=summary,
            )
            return summary

        lock = Lock()
        counts: dict[str, int] = {"done": 0, "converted": 0, "skipped": 0, "failed": 0}
        reports: list[ConversionReport] = []
        options_signature = self._options_signature(options)

        def run_one(job: ConversionJob) -> None:
            if cancellation_token and cancellation_token.is_cancelled():
                return

            with lock:
                progress = counts["done"]
            self._report(
                reporter,
                ConversionEventKind.STARTED,
                f"Converting: {path.basename(job.source_path)}",
                completed=progress,
                total=total,
                source_path=job.source_path,
                output_path=job.output_path,
            )

            out_dir = path.dirname(job.output_path)
            if out_dir and not path.isdir(out_dir):
                makedirs(out_dir, exist_ok=True)

            if options.use_cache:
                cached_report = self._cache_for(job.output_path, options).get_cached_report(
                    job.source_path,
                    job.output_path,
                    options_signature=options_signature,
                )
                if cached_report is not None:
                    with lock:
                        counts["done"] += 1
                        counts["skipped"] += 1
                        completed = counts["done"]
                        reports.append(cached_report)
                    self._report(
                        reporter,
                        ConversionEventKind.SKIPPED,
                        f"Skipped unchanged (cache): {path.basename(job.source_path)}  ->  {job.output_path}",
                        completed=completed,
                        total=total,
                        source_path=job.source_path,
                        output_path=job.output_path,
                        report=cached_report,
                    )
                    return

            if path.exists(job.output_path) and not options.overwrite:
                with lock:
                    counts["done"] += 1
                    counts["skipped"] += 1
                    completed = counts["done"]
                self._report(
                    reporter,
                    ConversionEventKind.SKIPPED,
                    f"Skipped existing: {path.basename(job.source_path)}  ->  {job.output_path}",
                    completed=completed,
                    total=total,
                    source_path=job.source_path,
                    output_path=job.output_path,
                )
                return

            try:
                converter = self._converter_factory()
                result = converter.convert_file_result(
                    job.source_path,
                    out_path=job.output_path,
                    flatten=options.flatten,
                    max_elements=options.max_elements,
                    rendering_options=options.rendering,
                )
                report = result.report
                if options.use_cache:
                    self._cache_for(job.output_path, options).update(
                        job.source_path,
                        result.output_path or job.output_path,
                        options_signature=options_signature,
                        report=report,
                    )
                with lock:
                    counts["done"] += 1
                    counts["converted"] += 1
                    completed = counts["done"]
                    reports.append(report)
                self._report(
                    reporter,
                    ConversionEventKind.CONVERTED,
                    f"Converted: {path.basename(job.source_path)}  ->  {result.output_path}",
                    completed=completed,
                    total=total,
                    source_path=job.source_path,
                    output_path=result.output_path,
                    report=report,
                )
            except Exception as exc:  # pragma: no cover - user-facing
                report = ConversionReport(source_path=job.source_path, output_path=job.output_path)
                report.add_issue("conversion-failed", "error", f"Conversion failed: {exc}")
                with lock:
                    counts["done"] += 1
                    counts["failed"] += 1
                    completed = counts["done"]
                    reports.append(report)
                self._report(
                    reporter,
                    ConversionEventKind.FAILED,
                    f"Failed: {path.basename(job.source_path)}  ({exc})",
                    completed=completed,
                    total=total,
                    source_path=job.source_path,
                    output_path=job.output_path,
                    error=str(exc),
                    report=report,
                )

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = [pool.submit(run_one, job) for job in jobs]
            concurrent.futures.wait(futures)

        cancelled = bool(cancellation_token and cancellation_token.is_cancelled())
        if cancelled:
            self._report(
                reporter,
                ConversionEventKind.CANCELLED,
                f"Cancellation requested after {counts['done']} processed file(s).",
                completed=counts["done"],
                total=total,
            )

        summary = ConversionSummary(
            total=total,
            converted=counts["converted"],
            skipped=counts["skipped"],
            failed=counts["failed"],
            cancelled=cancelled,
            reports=reports,
        )
        self._report(
            reporter,
            ConversionEventKind.COMPLETED,
            summary.to_status_line(),
            completed=counts["done"],
            total=total,
            summary=summary,
        )
        return summary

    def _report(
        self,
        reporter: Reporter | None,
        kind: ConversionEventKind,
        message: str,
        *,
        completed: int,
        total: int,
        source_path: str | None = None,
        output_path: str | None = None,
        error: str | None = None,
        summary: ConversionSummary | None = None,
        report: ConversionReport | None = None,
    ) -> None:
        """Emit one progress event when a reporter callback is configured."""
        if reporter is None:
            return
        reporter(
            ConversionEvent(
                kind=kind,
                message=message,
                completed=completed,
                total=total,
                source_path=source_path,
                output_path=output_path,
                error=error,
                summary=summary,
                report=report,
            )
        )


def watch_svg_files(
    input_paths: Sequence[str | PathLike[str]],
    options: ConversionOptions,
    reporter: Reporter | None = None,
    poll_interval: float = 1.0,
    stop_event: Event | None = None,
    backend: WatchBackend = "auto",
) -> None:
    """Watch SVG files for modifications and re-convert when changes are detected.

    Runs an initial conversion of all discovered files, then either uses an
    event-driven watcher when available or falls back to polling.
    """
    resolved_backend = resolve_watch_backend(backend)
    if resolved_backend == "event":
        _watch_svg_files_event(input_paths, options, reporter=reporter, stop_event=stop_event)
        return

    _watch_svg_files_poll(
        input_paths,
        options,
        reporter=reporter,
        poll_interval=poll_interval,
        stop_event=stop_event,
    )


def _watch_svg_files_poll(
    input_paths: Sequence[str | PathLike[str]],
    options: ConversionOptions,
    reporter: Reporter | None = None,
    poll_interval: float = 1.0,
    stop_event: Event | None = None,
) -> None:
    """Poll SVG files for modifications and re-convert when changes are detected."""
    resolved_inputs = [path.abspath(os.fspath(p)) for p in input_paths]
    service = ConversionService()

    def scan_signatures() -> dict[str, tuple[int, int]]:
        signatures: dict[str, tuple[int, int]] = {}
        for inp in resolved_inputs:
            for svg in iter_svg_files(inp, recursive=options.recursive):
                try:
                    stat = os.stat(svg)
                except OSError:
                    continue
                signatures[svg] = (int(stat.st_mtime_ns), int(stat.st_size))
        return signatures

    # Always overwrite during watch mode; user triggered an explicit watch session
    watch_opts = ConversionOptions(
        output_dir=options.output_dir,
        recursive=options.recursive,
        overwrite=True,
        flatten=options.flatten,
        max_elements=options.max_elements,
        use_cache=options.use_cache,
        rendering=options.rendering,
    )

    # Initial conversion pass
    service.convert(resolved_inputs, watch_opts, reporter=reporter)

    # Record signatures so we can detect modifications, additions, and content-size changes.
    last_snapshot = scan_signatures()

    while True:
        if stop_event and stop_event.is_set():
            break
        time.sleep(poll_interval)

        current_snapshot = scan_signatures()
        changed = [
            svg_path for svg_path, signature in current_snapshot.items() if last_snapshot.get(svg_path) != signature
        ]
        last_snapshot = current_snapshot

        if changed:
            single_opts = ConversionOptions(
                output_dir=options.output_dir,
                recursive=False,
                overwrite=True,
                flatten=options.flatten,
                max_elements=options.max_elements,
                use_cache=options.use_cache,
                rendering=options.rendering,
            )
            service.convert(changed, single_opts, reporter=reporter)


def _watch_svg_files_event(
    input_paths: Sequence[str | PathLike[str]],
    options: ConversionOptions,
    reporter: Reporter | None = None,
    stop_event: Event | None = None,
) -> None:
    """Use watchdog to re-convert SVG files as soon as the filesystem reports a change."""
    if not event_watch_available():  # pragma: no cover - guarded by resolve_watch_backend
        raise RuntimeError("The event-driven watch backend is unavailable because watchdog is not installed.")
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer

    resolved_inputs = [path.abspath(os.fspath(p)) for p in input_paths]
    service = ConversionService()
    watch_opts = ConversionOptions(
        output_dir=options.output_dir,
        recursive=options.recursive,
        overwrite=True,
        flatten=options.flatten,
        max_elements=options.max_elements,
        use_cache=options.use_cache,
        rendering=options.rendering,
    )
    service.convert(resolved_inputs, watch_opts, reporter=reporter)

    changed_paths: set[str] = set()
    changed_lock = Lock()

    class SvgWatchHandler(FileSystemEventHandler):  # type: ignore[misc]
        """Collect changed SVG paths reported by watchdog."""

        def on_any_event(self, event: Any) -> None:  # pragma: no cover - depends on watchdog runtime
            if getattr(event, "is_directory", False):
                return
            candidate = path.abspath(getattr(event, "src_path", "") or "")
            if not candidate.lower().endswith(".svg"):
                return
            with changed_lock:
                changed_paths.add(candidate)

    observer = Observer()
    handler = SvgWatchHandler()
    scheduled: set[str] = set()
    for input_path in resolved_inputs:
        watch_root = input_path if path.isdir(input_path) else path.dirname(input_path)
        watch_root = path.abspath(watch_root or ".")
        if watch_root in scheduled:
            continue
        observer.schedule(handler, watch_root, recursive=options.recursive)
        scheduled.add(watch_root)
    observer.start()

    try:
        while True:
            if stop_event and stop_event.is_set():
                break
            time.sleep(0.35)
            with changed_lock:
                batch = sorted(changed_paths)
                changed_paths.clear()
            if not batch:
                continue
            existing = [candidate for candidate in batch if path.isfile(candidate)]
            if not existing:
                continue
            single_opts = ConversionOptions(
                output_dir=options.output_dir,
                recursive=False,
                overwrite=True,
                flatten=options.flatten,
                max_elements=options.max_elements,
                use_cache=options.use_cache,
                rendering=options.rendering,
            )
            service.convert(existing, single_opts, reporter=reporter)
    finally:  # pragma: no cover - watchdog lifecycle is runtime-specific
        observer.stop()
        observer.join(timeout=2.0)
