"""Command-line interface for converting SVG files into editable draw.io diagrams."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from os import PathLike, path

import svg_to_drawio
from svg_to_drawio.conversion_service import (
    ConversionEvent,
    ConversionEventKind,
    ConversionOptions,
    ConversionService,
    ConversionSummary,
)
from svg_to_drawio.converter import Converter
from svg_to_drawio.diagnostics import ConversionReport
from svg_to_drawio.rendering_options import (
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
    input_path: str | PathLike[str] | None,
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
) -> int:
    """Run the conversion CLI logic and return an exit code (0 = success, 1 = error)."""
    if not input_path:
        print("Error: no input path provided.")
        return 1

    resolved_input = path.abspath(os.fspath(input_path))
    resolved_output_dir = path.abspath(os.fspath(output_dir)) if output_dir is not None else None

    if not path.exists(resolved_input):
        print(f'Error: "{resolved_input}" does not exist.')
        return 1

    rendering_options = RenderingOptions(
        gradient_policy=as_gradient_policy(gradient_policy),
        filter_policy=as_filter_policy(filter_policy),
        text_metrics_policy=as_text_metrics_policy(text_metrics_policy),
    )

    # --stdout: write draw.io XML to stdout; single file only
    if stdout:
        if path.isdir(resolved_input):
            print("Error: --stdout requires a single SVG file, not a directory.", file=sys.stderr)
            return 1

        xml = Converter().convert_to_string(
            resolved_input,
            flatten=flatten,
            max_elements=max_elements,
            rendering_options=rendering_options,
        )
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
        jobs = service.plan([resolved_input], options)
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
        write_report(batch_payload("analyze", reports))
        return 1 if failures else 0

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

    # --watch: run initial conversion then poll for changes
    if watch:
        from svg_to_drawio.conversion_service import watch_svg_files

        print(f'Watching "{resolved_input}" for changes... (Ctrl+C to stop)')
        try:
            watch_svg_files([resolved_input], options, reporter=emit_progress)
        except KeyboardInterrupt:
            print("\nWatch mode stopped.")
        return 0

    service = ConversionService()
    summary = service.convert([resolved_input], options, reporter=emit_progress)
    write_report(batch_payload("convert", summary.reports, summary))
    if summary.total == 0:
        print("No SVG files found.")
        return 0

    print(summary.to_status_line())
    return summary.exit_code


def build_parser() -> argparse.ArgumentParser:
    """Create and configure the command-line argument parser."""
    parser = argparse.ArgumentParser(description="Convert SVG files into editable draw.io diagrams.")
    parser.add_argument("--version", action="version", version=f"svg-to-drawio {svg_to_drawio.__version__}")
    parser.add_argument("input_path", nargs="?", help="SVG file or folder to convert")
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
    parser.set_defaults(use_cache=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point used by both `python main.py` and tests."""
    parser = build_parser()
    args = parser.parse_args(argv)
    input_path = args.input_path or input("Enter SVG file or folder path: ").strip()
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
    )


if __name__ == "__main__":
    raise SystemExit(main())
