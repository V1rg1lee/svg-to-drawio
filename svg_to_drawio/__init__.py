"""Public package entry points for SVG-to-draw.io conversion."""

from __future__ import annotations

from os import PathLike

from .converter import Converter


def convert_file(svg_path: str | PathLike[str], out_path: str | PathLike[str] | None = None) -> str:
    """Convert a single SVG file into a `.drawio` file and return the output path."""
    return Converter().convert_file(svg_path, out_path)
