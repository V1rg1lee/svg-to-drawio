"""Command-line interface for converting SVG files into editable draw.io diagrams."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from os import PathLike, path

import svg_to_drawio
from svg_to_drawio.conversion_service import ConversionEvent, ConversionEventKind, ConversionOptions, ConversionService


def run(
    input_path: str | PathLike[str] | None,
    output_dir: str | PathLike[str] | None = None,
    recursive: bool = False,
    overwrite: bool = False,
    stdout: bool = False,
    watch: bool = False,
    flatten: bool = False,
    max_elements: int | None = None,
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

    # --stdout: write draw.io XML to stdout; single file only
    if stdout:
        if path.isdir(resolved_input):
            print("Error: --stdout requires a single SVG file, not a directory.", file=sys.stderr)
            return 1
        from svg_to_drawio.converter import Converter

        xml = Converter().convert_to_string(resolved_input, flatten=flatten, max_elements=max_elements)
        sys.stdout.write(xml)
        return 0

    options = ConversionOptions(
        output_dir=resolved_output_dir,
        recursive=recursive,
        overwrite=overwrite,
        flatten=flatten,
        max_elements=max_elements,
    )

    def report(event: ConversionEvent) -> None:
        if event.kind in {
            ConversionEventKind.CONVERTED,
            ConversionEventKind.SKIPPED,
            ConversionEventKind.FAILED,
            ConversionEventKind.CANCELLED,
        }:
            print(event.message)

    # --watch: run initial conversion then poll for changes
    if watch:
        from svg_to_drawio.conversion_service import watch_svg_files

        print(f'Watching "{resolved_input}" for changes... (Ctrl+C to stop)')
        try:
            watch_svg_files([resolved_input], options, reporter=report)
        except KeyboardInterrupt:
            print("\nWatch mode stopped.")
        return 0

    service = ConversionService()
    summary = service.convert([resolved_input], options, reporter=report)
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
        "--max-elements",
        type=int,
        default=None,
        metavar="N",
        help="Warn and truncate output after N drawable elements (useful for very large SVGs)",
    )
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
    )


if __name__ == "__main__":
    raise SystemExit(main())
