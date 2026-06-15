"""Shared file-system conversion service used by both the CLI and desktop app."""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from os import PathLike, makedirs, path
from threading import Event

from .converter import Converter

Reporter = Callable[["ConversionEvent"], None]


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

    @property
    def exit_code(self) -> int:
        """Return the CLI-style exit code for the completed batch."""
        return 1 if self.failed else 0

    def to_status_line(self) -> str:
        """Render a stable human-readable batch summary."""
        suffix = " before cancellation" if self.cancelled else ""
        return f"Summary: {self.converted} converted, {self.skipped} skipped, {self.failed} failed{suffix}"


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
                written = self._converter_factory().convert_file(
                    job.source_path,
                    out_path=job.output_path,
                    flatten=options.flatten,
                    max_elements=options.max_elements,
                )
            except Exception as exc:  # pragma: no cover - intentionally user-facing
                failed += 1
                self._report(
                    reporter,
                    ConversionEventKind.FAILED,
                    f"Failed: {job.source_path}  ({exc})",
                    completed=index,
                    total=total,
                    source_path=job.source_path,
                    output_path=job.output_path,
                    error=str(exc),
                )
                continue

            converted += 1
            self._report(
                reporter,
                ConversionEventKind.CONVERTED,
                f"Converted: {job.source_path}  ->  {written}",
                completed=index,
                total=total,
                source_path=job.source_path,
                output_path=written,
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
            )
        )


def watch_svg_files(
    input_paths: Sequence[str | PathLike[str]],
    options: ConversionOptions,
    reporter: Reporter | None = None,
    poll_interval: float = 1.0,
    stop_event: Event | None = None,
) -> None:
    """Poll SVG files for modifications and re-convert when changes are detected.

    Runs an initial conversion of all discovered files, then loops (sleeping
    *poll_interval* seconds between checks) until *stop_event* is set or a
    ``KeyboardInterrupt`` is raised by the caller.
    """
    resolved_inputs = [path.abspath(os.fspath(p)) for p in input_paths]
    last_mtimes: dict[str, float] = {}
    service = ConversionService()

    # Always overwrite during watch mode; user triggered an explicit watch session
    watch_opts = ConversionOptions(
        output_dir=options.output_dir,
        recursive=options.recursive,
        overwrite=True,
        flatten=options.flatten,
        max_elements=options.max_elements,
    )

    # Initial conversion pass
    service.convert(resolved_inputs, watch_opts, reporter=reporter)

    # Record mtimes so we can detect subsequent changes
    for inp in resolved_inputs:
        for svg in iter_svg_files(inp, recursive=options.recursive):
            try:
                last_mtimes[svg] = os.stat(svg).st_mtime
            except OSError:
                pass

    while True:
        if stop_event and stop_event.is_set():
            break
        time.sleep(poll_interval)

        changed: list[str] = []
        for inp in resolved_inputs:
            for svg in iter_svg_files(inp, recursive=options.recursive):
                try:
                    mtime = os.stat(svg).st_mtime
                except OSError:
                    continue
                if last_mtimes.get(svg) != mtime:
                    last_mtimes[svg] = mtime
                    changed.append(svg)

        if changed:
            single_opts = ConversionOptions(
                output_dir=options.output_dir,
                recursive=False,
                overwrite=True,
                flatten=options.flatten,
                max_elements=options.max_elements,
            )
            service.convert(changed, single_opts, reporter=reporter)
