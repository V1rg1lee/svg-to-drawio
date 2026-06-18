"""Public package entry points for SVG-to-draw.io conversion."""

from __future__ import annotations

from os import PathLike

__version__ = "3.5.0"

from .capabilities import all_capabilities, capability_descriptor, capability_keys, rendering_preflight_lines
from .compatibility import CompatibilityOverview, CompatibilityRow, FeatureObservation
from .conversion_result import ConversionResult
from .conversion_service import CancellationToken, ConversionOptions, ConversionService, ConversionSummary
from .converter import Converter
from .diagnostics import REPORT_SCHEMA_VERSION, ConversionReport
from .quality_gates import QualityGateOptions, QualityGateViolation, evaluate_quality_gates
from .rendering_options import (
    RenderingOptions,
    detect_rendering_preset,
    rendering_preset_label,
    rendering_preset_options,
)


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


def convert_svg_string(
    svg_text: str,
    *,
    base_dir: str | PathLike[str] | None = None,
    title: str = "diagram",
    source_label: str | None = None,
    flatten: bool = False,
    max_elements: int | None = None,
    rendering_options: RenderingOptions | None = None,
) -> str:
    """Convert SVG markup already loaded in memory into draw.io XML."""
    return (
        Converter()
        .convert_svg_string_result(
            svg_text,
            base_dir=base_dir,
            title=title,
            source_label=source_label,
            flatten=flatten,
            max_elements=max_elements,
            rendering_options=rendering_options,
        )
        .xml
    )


def convert_svg_bytes(
    svg_bytes: bytes,
    *,
    base_dir: str | PathLike[str] | None = None,
    title: str = "diagram",
    source_label: str | None = None,
    flatten: bool = False,
    max_elements: int | None = None,
    rendering_options: RenderingOptions | None = None,
) -> str:
    """Convert SVG bytes already loaded in memory into draw.io XML."""
    return (
        Converter()
        .convert_svg_bytes_result(
            svg_bytes,
            base_dir=base_dir,
            title=title,
            source_label=source_label,
            flatten=flatten,
            max_elements=max_elements,
            rendering_options=rendering_options,
        )
        .xml
    )


def convert_file_result(
    svg_path: str | PathLike[str],
    out_path: str | PathLike[str] | None = None,
    *,
    flatten: bool = False,
    max_elements: int | None = None,
    rendering_options: RenderingOptions | None = None,
) -> ConversionResult:
    """Convert a single SVG file and return a rich conversion result."""
    return Converter().convert_file_result(
        svg_path,
        out_path,
        flatten=flatten,
        max_elements=max_elements,
        rendering_options=rendering_options,
    )


def convert_to_string_result(
    svg_path: str | PathLike[str],
    *,
    flatten: bool = False,
    max_elements: int | None = None,
    rendering_options: RenderingOptions | None = None,
) -> ConversionResult:
    """Convert a single SVG file to XML and return a rich conversion result."""
    return Converter().convert_to_string_result(
        svg_path,
        flatten=flatten,
        max_elements=max_elements,
        rendering_options=rendering_options,
    )


def convert_svg_string_result(
    svg_text: str,
    *,
    base_dir: str | PathLike[str] | None = None,
    title: str = "diagram",
    source_label: str | None = None,
    flatten: bool = False,
    max_elements: int | None = None,
    rendering_options: RenderingOptions | None = None,
) -> ConversionResult:
    """Convert SVG markup already loaded in memory and return a rich conversion result."""
    return Converter().convert_svg_string_result(
        svg_text,
        base_dir=base_dir,
        title=title,
        source_label=source_label,
        flatten=flatten,
        max_elements=max_elements,
        rendering_options=rendering_options,
    )


def convert_svg_bytes_result(
    svg_bytes: bytes,
    *,
    base_dir: str | PathLike[str] | None = None,
    title: str = "diagram",
    source_label: str | None = None,
    flatten: bool = False,
    max_elements: int | None = None,
    rendering_options: RenderingOptions | None = None,
) -> ConversionResult:
    """Convert SVG bytes already loaded in memory and return a rich conversion result."""
    return Converter().convert_svg_bytes_result(
        svg_bytes,
        base_dir=base_dir,
        title=title,
        source_label=source_label,
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
    "__version__",
    "REPORT_SCHEMA_VERSION",
    "ConversionResult",
    "CancellationToken",
    "CompatibilityOverview",
    "CompatibilityRow",
    "QualityGateOptions",
    "QualityGateViolation",
    "ConversionOptions",
    "ConversionReport",
    "ConversionService",
    "ConversionSummary",
    "Converter",
    "FeatureObservation",
    "RenderingOptions",
    "all_capabilities",
    "analyze_file",
    "capability_descriptor",
    "capability_keys",
    "convert_file",
    "convert_file_result",
    "convert_to_string",
    "convert_to_string_result",
    "convert_svg_bytes",
    "convert_svg_bytes_result",
    "convert_svg_string",
    "convert_svg_string_result",
    "detect_rendering_preset",
    "evaluate_quality_gates",
    "rendering_preflight_lines",
    "rendering_preset_label",
    "rendering_preset_options",
]
