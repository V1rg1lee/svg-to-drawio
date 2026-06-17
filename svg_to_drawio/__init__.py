"""Public package entry points for SVG-to-draw.io conversion."""

from __future__ import annotations

from os import PathLike

__version__ = "3.3.0"

from .compatibility import CompatibilityOverview, CompatibilityRow, FeatureObservation
from .conversion_service import CancellationToken, ConversionOptions, ConversionService, ConversionSummary
from .converter import Converter
from .diagnostics import ConversionReport
from .rendering_options import RenderingOptions


def convert_file(
    svg_path: str | PathLike[str],
    out_path: str | PathLike[str] | None = None,
    *,
    flatten: bool = False,
    max_elements: int | None = None,
    rendering_options: RenderingOptions | None = None,
) -> str:
    """Convert a single SVG file into a `.drawio` file and return the output path."""
    return Converter().convert_file(
        svg_path,
        out_path,
        flatten=flatten,
        max_elements=max_elements,
        rendering_options=rendering_options,
    )


def convert_to_string(
    svg_path: str | PathLike[str],
    *,
    flatten: bool = False,
    max_elements: int | None = None,
    rendering_options: RenderingOptions | None = None,
) -> str:
    """Convert a single SVG file into draw.io XML and return the result as a string."""
    return Converter().convert_to_string(
        svg_path,
        flatten=flatten,
        max_elements=max_elements,
        rendering_options=rendering_options,
    )


def analyze_file(
    svg_path: str | PathLike[str],
    *,
    flatten: bool = False,
    max_elements: int | None = None,
    rendering_options: RenderingOptions | None = None,
) -> ConversionReport:
    """Analyze one SVG file and return a structured diagnostics report."""
    return Converter().analyze_file(
        svg_path,
        flatten=flatten,
        max_elements=max_elements,
        rendering_options=rendering_options,
    )


__all__ = [
    "CancellationToken",
    "CompatibilityOverview",
    "CompatibilityRow",
    "ConversionOptions",
    "ConversionReport",
    "ConversionService",
    "ConversionSummary",
    "Converter",
    "FeatureObservation",
    "RenderingOptions",
    "analyze_file",
    "convert_file",
    "convert_to_string",
]
