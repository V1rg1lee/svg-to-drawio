"""Command-line interface for converting SVG files into editable draw.io diagrams."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from os import PathLike, path
from typing import Literal, cast

from . import REPORT_SCHEMA_VERSION, __version__
from .capabilities import capability_keys
from .conversion_service import (
    ConversionEvent,
    ConversionEventKind,
    ConversionOptions,
    ConversionService,
    ConversionSummary,
    resolve_watch_backend,
)
from .converter import Converter
from .diagnostics import ConversionReport
from .quality_gates import QualityGateOptions, evaluate_quality_gates, validate_required_capabilities
from .rendering_options import (
    RenderingOptions,
    as_filter_policy,
    as_gradient_policy,
    as_text_metrics_policy,
)


def _print_compatibility(report: ConversionReport, *, show_all_rows: bool) -> None:
    """Print a short, non-technical compatibility summary for one converted file."""
    rows = report.compatibility_matrix
    if not rows:
        return

    overview = report.compatibility_overview
    print(f"  Compatibility: {overview.headline}")
    relevant_rows = rows if show_all_rows else [row for row in rows if row.status != "native"]
    for row in relevant_rows[:5]:
        print(f"  - {row.label}: {row.status_label}. {row.message}")
    remaining = len(relevant_rows) - 5
    if remaining > 0:
        print(f"  - {remaining} more compatibility detail row(s) omitted for brevity.")


def run(
    input_path: str | PathLike[str] | Sequence[str | PathLike[str]] | None,
    output_dir: str | PathLike[str] | None = None,
    recursive: bool = False,
    overwrite: bool = False,
    stdout: bool = False,
    watch: bool = False,
    flatten: bool = False,
    max_elements: int | None = None,
    report_json: str | PathLike[str] | None = None,
    analyze: bool = False,
    use_cache: bool = True,
    gradient_policy: str = "auto",
    filter_policy: str = "auto",
    text_metrics_policy: str = "auto",
    fail_on_warning: bool = False,
    fail_on_fallback: bool = False,
    min_score: int | None = None,
    require_native: Sequence[str] = (),
    workers: int = 1,
    watch_backend: str = "auto",
) -> int:
    """Run the conversion CLI logic and return an exit code (0 = success, 1 = error)."""
    if input_path is None:
        print("Error: no input path provided.")
        return 1

    if isinstance(input_path, (str, os.PathLike)):
        raw_inputs = [input_path]
    else:
        raw_inputs = list(input_path)

    if not raw_inputs:
        print("Error: no input path provided.")
        return 1

    resolved_inputs = [path.abspath(os.fspath(item)) for item in raw_inputs]
    resolved_output_dir = path.abspath(os.fspath(output_dir)) if output_dir is not None else None

    missing = [item for item in resolved_inputs if not path.exists(item)]
    if missing:
        print(f'Error: "{missing[0]}" does not exist.')
        return 1

    rendering_options = RenderingOptions(
        gradient_policy=as_gradient_policy(gradient_policy),
        filter_policy=as_filter_policy(filter_policy),
        text_metrics_policy=as_text_metrics_policy(text_metrics_policy),
    )
    try:
        required_native = validate_required_capabilities(list(require_native))
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    quality_options = QualityGateOptions(
        fail_on_warning=fail_on_warning,
        fail_on_fallback=fail_on_fallback,
        min_score=min_score,
        require_native=required_native,
    )

    if stdout:
        if len(resolved_inputs) != 1 or path.isdir(resolved_inputs[0]):
            print("Error: --stdout requires exactly one SVG file, not multiple inputs or a directory.", file=sys.stderr)
            return 1

        try:
            xml = Converter().convert_to_string(
                resolved_inputs[0],
                flatten=flatten,
                max_elements=max_elements,
                rendering_options=rendering_options,
            )
        except Exception as exc:
            print(f'Error: failed to convert "{resolved_inputs[0]}": {exc}', file=sys.stderr)
            return 1
        sys.stdout.write(xml)
        return 0

    options = ConversionOptions(
        output_dir=resolved_output_dir,
        recursive=recursive,
        overwrite=overwrite,
        flatten=flatten,
        max_elements=max_elements,
        use_cache=use_cache,
        rendering=rendering_options,
    )

    def batch_payload(
        mode: str,
        reports: list[ConversionReport],
        summary: ConversionSummary | None = None,
    ) -> dict[str, object]:
        payload: dict[str, object] = {
            "report_schema_version": REPORT_SCHEMA_VERSION,
            "mode": mode,
            "reports": [report.to_dict() for report in reports],
        }
        if summary is not None:
            payload["summary"] = summary.to_dict()
        return payload

    def write_report(payload: dict[str, object]) -> None:
        if report_json is None:
            return
        target = path.abspath(os.fspath(report_json))
        if path.isdir(target):
            target = path.join(target, "svg-to-drawio-report.json")
        target_dir = path.dirname(target)
        if target_dir and not path.isdir(target_dir):
            os.makedirs(target_dir, exist_ok=True)
        with open(target, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
        print(f"Report written to: {target}")

    if analyze:
        service = ConversionService()
        jobs = service.plan(resolved_inputs, options)
        reports: list[ConversionReport] = []
        failures = 0

        if not jobs:
            print("No SVG files found.")
            write_report(batch_payload("analyze", reports))
            return 0

        print(f"Analyzing {len(jobs)} SVG file(s)...")
        for job in jobs:
            try:
                file_report = Converter().analyze_file(
                    job.source_path,
                    flatten=flatten,
                    max_elements=max_elements,
                    rendering_options=rendering_options,
                )
                file_report.output_path = job.output_path
            except Exception as exc:
                failures += 1
                file_report = ConversionReport(
                    source_path=job.source_path,
                    output_path=job.output_path,
                    analyze_only=True,
                )
                file_report.add_issue("analysis-failed", "error", f"Analysis failed: {exc}")
            reports.append(file_report)
            print(f"{job.source_path}: {file_report.short_status()}")
            _print_compatibility(file_report, show_all_rows=True)
            for issue in file_report.issues:
                print(f"  - {issue.severity.upper()}: {issue.message}")

        print(f"Analysis summary: {len(reports) - failures} analyzed, {failures} failed.")
        violations = evaluate_quality_gates(reports, quality_options)
        for violation in violations:
            print(f"QUALITY GATE: {violation.message}")
        write_report(batch_payload("analyze", reports))
        return 1 if failures or violations else 0

    def emit_progress(event: ConversionEvent) -> None:
        if event.kind in {
            ConversionEventKind.CONVERTED,
            ConversionEventKind.SKIPPED,
            ConversionEventKind.FAILED,
            ConversionEventKind.CANCELLED,
        }:
            print(event.message)
            if event.report and event.report.issues:
                print(f"  Diagnostics: {event.report.short_status()}")
            if event.report and event.kind in {ConversionEventKind.CONVERTED, ConversionEventKind.SKIPPED}:
                _print_compatibility(event.report, show_all_rows=False)

    if watch:
        from .conversion_service import watch_svg_files

        resolved_watch_backend = cast(Literal["auto", "poll", "event"], watch_backend)
        backend_name = resolve_watch_backend(resolved_watch_backend)
        watched_label = resolved_inputs[0] if len(resolved_inputs) == 1 else f"{len(resolved_inputs)} input path(s)"
        print(f'Watching "{watched_label}" for changes using the {backend_name} backend... (Ctrl+C to stop)')
        try:
            watch_svg_files(resolved_inputs, options, reporter=emit_progress, backend=resolved_watch_backend)
        except KeyboardInterrupt:
            print("\nWatch mode stopped.")
        return 0

    service = ConversionService()
    if workers > 1:
        summary = service.convert_parallel(resolved_inputs, options, reporter=emit_progress, max_workers=workers)
    else:
        summary = service.convert(resolved_inputs, options, reporter=emit_progress)
    write_report(batch_payload("convert", summary.reports, summary))
    if summary.total == 0:
        print("No SVG files found.")
        return 0

    print(summary.to_status_line())
    violations = evaluate_quality_gates(summary.reports, quality_options)
    for violation in violations:
        print(f"QUALITY GATE: {violation.message}")
    return 1 if summary.failed or violations else 0


def build_parser() -> argparse.ArgumentParser:
    """Create and configure the command-line argument parser."""
    parser = argparse.ArgumentParser(description="Convert SVG files into editable draw.io diagrams.")
    parser.add_argument("--version", action="version", version=f"svg-to-drawio {__version__}")
    parser.add_argument("input_path", nargs="*", help="One or more SVG files or folders to convert")
    parser.add_argument("--output-dir", help="Write .drawio files to this directory")
    parser.add_argument("--recursive", action="store_true", help="Recursively search for SVG files in folders")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing .drawio outputs")
    parser.add_argument("--stdout", action="store_true", help="Write draw.io XML to stdout (single file only)")
    parser.add_argument("--watch", action="store_true", help="Re-convert SVG files when they change")
    parser.add_argument("--flatten", action="store_true", help="Dissolve SVG groups; emit all shapes at root level")
    parser.add_argument(
        "--analyze",
        action="store_true",
        help="Analyze compatibility and diagnostics without writing output files",
    )
    parser.add_argument("--report-json", help="Write a structured JSON conversion report to this file")
    parser.add_argument(
        "--no-cache",
        action="store_false",
        dest="use_cache",
        help="Disable the persistent incremental cache",
    )
    parser.add_argument(
        "--max-elements",
        type=int,
        default=None,
        metavar="N",
        help="Warn and truncate output after N drawable elements (useful for very large SVGs)",
    )
    parser.add_argument(
        "--gradient-policy",
        choices=("auto", "prefer-native", "prefer-fallback"),
        default="auto",
        help="Choose how multi-stop gradients trade editability against visual fidelity",
    )
    parser.add_argument(
        "--filter-policy",
        choices=("auto", "prefer-native", "force-fallback"),
        default="auto",
        help="Choose whether SVG filters prefer native editability or embedded SVG fallback",
    )
    parser.add_argument(
        "--text-metrics-policy",
        choices=("auto", "system", "heuristic"),
        default="auto",
        help="Choose how text bounds are measured when sizing draw.io text cells",
    )
    parser.add_argument("--workers", type=int, default=1, metavar="N", help="Convert files in parallel with N workers")
    parser.add_argument(
        "--watch-backend",
        choices=("auto", "poll", "event"),
        default="auto",
        help="Choose the filesystem watch backend when --watch is enabled",
    )
    parser.add_argument(
        "--fail-on-warning",
        action="store_true",
        help="Exit with code 1 if any converted file reports at least one warning",
    )
    parser.add_argument(
        "--fail-on-fallback",
        action="store_true",
        help="Exit with code 1 if any converted file uses embedded SVG fallback",
    )
    parser.add_argument(
        "--min-score",
        type=int,
        default=None,
        metavar="N",
        help="Exit with code 1 if any converted file scores below N compatibility points",
    )
    parser.add_argument(
        "--require-native",
        nargs="*",
        default=(),
        metavar="CAPABILITY",
        help=(
            f"Require selected capability families to remain fully native. Valid keys: {', '.join(capability_keys())}"
        ),
    )
    parser.set_defaults(use_cache=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point used by the console script and local wrappers."""
    parser = build_parser()
    args = parser.parse_args(argv)
    input_path = args.input_path or [input("Enter SVG file or folder path: ").strip()]
    return run(
        input_path,
        output_dir=args.output_dir,
        recursive=args.recursive,
        overwrite=args.overwrite,
        stdout=args.stdout,
        watch=args.watch,
        flatten=args.flatten,
        max_elements=args.max_elements,
        report_json=args.report_json,
        analyze=args.analyze,
        use_cache=args.use_cache,
        gradient_policy=args.gradient_policy,
        filter_policy=args.filter_policy,
        text_metrics_policy=args.text_metrics_policy,
        fail_on_warning=args.fail_on_warning,
        fail_on_fallback=args.fail_on_fallback,
        min_score=args.min_score,
        require_native=args.require_native,
        workers=max(1, int(args.workers)),
        watch_backend=args.watch_backend,
    )


__all__ = ["build_parser", "main", "run"]
