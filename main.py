"""Command-line interface for converting SVG files into editable draw.io diagrams."""

from __future__ import annotations

import argparse
import os
from collections.abc import Sequence
from os import PathLike, makedirs, path

from svg_to_drawio import convert_file


def _iter_svg_files(input_path: str, recursive: bool = False) -> list[str]:
    """Return the SVG files represented by *input_path*.

    When *input_path* points to a file, the result contains either that file or an empty
    list if it does not have an `.svg` extension. When *input_path* points to a directory,
    the function scans either the top level or the full tree depending on *recursive*.
    """
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


def _build_output_path(
    svg_path: str,
    input_root: str | None = None,
    output_dir: str | None = None,
) -> str:
    """Compute the destination `.drawio` path for a converted SVG file."""
    if output_dir is None:
        return path.splitext(svg_path)[0] + ".drawio"

    if input_root and path.isdir(input_root):
        rel_path = path.relpath(svg_path, input_root)
        rel_base = path.splitext(rel_path)[0] + ".drawio"
    else:
        rel_base = path.splitext(path.basename(svg_path))[0] + ".drawio"
    return path.join(output_dir, rel_base)


def run(
    input_path: str | PathLike[str] | None,
    output_dir: str | PathLike[str] | None = None,
    recursive: bool = False,
    overwrite: bool = False,
) -> int:
    """Run the conversion CLI logic.

    The function returns `0` when all requested conversions completed successfully and `1`
    when at least one file failed.
    """
    if not input_path:
        print("Error: no input path provided.")
        return 1

    resolved_input = path.abspath(os.fspath(input_path))
    resolved_output_dir = path.abspath(os.fspath(output_dir)) if output_dir is not None else None

    if not path.exists(resolved_input):
        print(f'Error: "{resolved_input}" does not exist.')
        return 1

    svg_paths = _iter_svg_files(resolved_input, recursive=recursive)
    if not svg_paths:
        print("No SVG files found.")
        return 0

    converted = 0
    skipped = 0
    failed = 0

    for svg_path in svg_paths:
        out_path = _build_output_path(
            svg_path,
            input_root=resolved_input if path.isdir(resolved_input) else None,
            output_dir=resolved_output_dir,
        )
        out_dir = path.dirname(out_path)
        if out_dir and not path.isdir(out_dir):
            makedirs(out_dir, exist_ok=True)

        if path.exists(out_path) and not overwrite:
            print(f"Skipped existing: {path.basename(svg_path)}  ->  {out_path}")
            skipped += 1
            continue

        try:
            written = convert_file(svg_path, out_path=out_path)
        except Exception as exc:  # pragma: no cover - intentionally user-facing
            print(f"Failed: {svg_path}  ({exc})")
            failed += 1
            continue

        print(f"Converted: {svg_path}  ->  {written}")
        converted += 1

    print(f"Summary: {converted} converted, {skipped} skipped, {failed} failed")
    return 1 if failed else 0


def build_parser() -> argparse.ArgumentParser:
    """Create and configure the command-line argument parser."""
    parser = argparse.ArgumentParser(description="Convert SVG files into editable draw.io diagrams.")
    parser.add_argument("input_path", nargs="?", help="SVG file or folder to convert")
    parser.add_argument("--output-dir", help="Write .drawio files to this directory")
    parser.add_argument("--recursive", action="store_true", help="Recursively search for SVG files in folders")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing .drawio outputs")
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
    )


if __name__ == "__main__":
    raise SystemExit(main())
