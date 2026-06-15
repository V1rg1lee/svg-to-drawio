"""Public package entry points for SVG-to-draw.io conversion."""

from __future__ import annotations

from os import PathLike

__version__ = "3.1.0"

from .conversion_service import CancellationToken, ConversionOptions, ConversionService, ConversionSummary
from .converter import Converter


def convert_file(svg_path: str | PathLike[str], out_path: str | PathLike[str] | None = None) -> str:
    """Convert a single SVG file into a `.drawio` file and return the output path."""
    return Converter().convert_file(svg_path, out_path)


def convert_to_string(
    svg_path: str | PathLike[str],
    *,
    flatten: bool = False,
    max_elements: int | None = None,
) -> str:
    """Convert a single SVG file into draw.io XML and return the result as a string."""
    return Converter().convert_to_string(svg_path, flatten=flatten, max_elements=max_elements)


__all__ = [
    "CancellationToken",
    "ConversionOptions",
    "ConversionService",
    "ConversionSummary",
    "Converter",
    "convert_file",
    "convert_to_string",
]
