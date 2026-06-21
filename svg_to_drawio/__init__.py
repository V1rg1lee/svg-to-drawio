"""Public package entry points for SVG-to-draw.io conversion."""

from __future__ import annotations

from collections.abc import Sequence
from os import PathLike, fspath, path

__version__ = "3.10.0"

from .capabilities import all_capabilities, capability_descriptor, capability_keys, rendering_preflight_lines
from .compatibility import CompatibilityOverview, CompatibilityRow, FeatureObservation
from .conversion_result import ConversionResult
from .conversion_service import (
    CancellationToken,
    ConversionEvent,
    ConversionEventKind,
    ConversionOptions,
    ConversionService,
    ConversionSummary,
    MergeMode,
    event_watch_available,
    resolve_merge_output_path,
    resolve_watch_backend,
    watch_svg_files,
)
from .converter import Converter
from .diagnostics import REPORT_SCHEMA_VERSION, ConversionReport
from .post_process import PostProcessOptions
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
    post_process: PostProcessOptions | None = None,
) -> str:
    """Convert a single SVG file into a `.drawio` file and return the output path."""
    return Converter().convert_file(
        svg_path,
        out_path,
        flatten=flatten,
        max_elements=max_elements,
        rendering_options=rendering_options,
        post_process=post_process,
    )


def convert_to_string(
    svg_path: str | PathLike[str],
    *,
    flatten: bool = False,
    max_elements: int | None = None,
    rendering_options: RenderingOptions | None = None,
    post_process: PostProcessOptions | None = None,
) -> str:
    """Convert a single SVG file into draw.io XML and return the result as a string."""
    return Converter().convert_to_string(
        svg_path,
        flatten=flatten,
        max_elements=max_elements,
        rendering_options=rendering_options,
        post_process=post_process,
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
    post_process: PostProcessOptions | None = None,
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
            post_process=post_process,
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
    post_process: PostProcessOptions | None = None,
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
            post_process=post_process,
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
    post_process: PostProcessOptions | None = None,
) -> ConversionResult:
    """Convert a single SVG file and return a rich conversion result."""
    return Converter().convert_file_result(
        svg_path,
        out_path,
        flatten=flatten,
        max_elements=max_elements,
        rendering_options=rendering_options,
        post_process=post_process,
    )


def convert_to_string_result(
    svg_path: str | PathLike[str],
    *,
    flatten: bool = False,
    max_elements: int | None = None,
    rendering_options: RenderingOptions | None = None,
    post_process: PostProcessOptions | None = None,
) -> ConversionResult:
    """Convert a single SVG file to XML and return a rich conversion result."""
    return Converter().convert_to_string_result(
        svg_path,
        flatten=flatten,
        max_elements=max_elements,
        rendering_options=rendering_options,
        post_process=post_process,
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
    post_process: PostProcessOptions | None = None,
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
        post_process=post_process,
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
    post_process: PostProcessOptions | None = None,
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
        post_process=post_process,
    )


def merge_files(
    input_paths: Sequence[str | PathLike[str]],
    output_path: str | PathLike[str],
    *,
    mode: MergeMode = "pages",
    columns: int | None = None,
    output_dir: str | PathLike[str] | None = None,
    recursive: bool = False,
    overwrite: bool = False,
    flatten: bool = False,
    max_elements: int | None = None,
    rendering_options: RenderingOptions | None = None,
    post_process: PostProcessOptions | None = None,
) -> ConversionSummary:
    """Combine every SVG found in `input_paths` into one merged `.drawio` file.

    `output_path` is resolved the same way the CLI's `--merge-output` is: a relative value
    (or bare filename) is placed inside `output_dir` when given, the `.drawio` extension is
    appended automatically if missing, and an absolute path is used as-is. Existing output
    is skipped unless `overwrite=True`.
    """
    resolved_output_dir = path.abspath(fspath(output_dir)) if output_dir is not None else None
    resolved_output_path = resolve_merge_output_path(output_path, output_dir=resolved_output_dir)
    options = ConversionOptions(
        output_dir=resolved_output_dir,
        recursive=recursive,
        overwrite=overwrite,
        flatten=flatten,
        max_elements=max_elements,
        rendering=rendering_options or RenderingOptions(),
        post_process=post_process,
    )
    return ConversionService().merge(
        input_paths,
        options,
        mode=mode,
        output_path=resolved_output_path,
        columns=columns,
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
    "ConversionEvent",
    "ConversionEventKind",
    "ConversionReport",
    "ConversionService",
    "ConversionSummary",
    "Converter",
    "FeatureObservation",
    "PostProcessOptions",
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
    "event_watch_available",
    "merge_files",
    "rendering_preflight_lines",
    "rendering_preset_label",
    "rendering_preset_options",
    "resolve_watch_backend",
    "watch_svg_files",
]
