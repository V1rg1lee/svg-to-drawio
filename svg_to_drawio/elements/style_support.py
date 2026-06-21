"""Shared style and marker helpers for SVG element emitters."""

from __future__ import annotations

import math
from collections.abc import Sequence
from xml.etree.ElementTree import Element

from ..cell_factory import make_bounds_vertex
from ..compatibility import note_filter_usage
from ..emitter_context import EmitterContext
from ..issue_codes import FILTER_SIMPLIFIED_NATIVE
from ..style_builder import StyleBuilder
from ..styles import GradientStyle, gradient_entries
from ..utils import link_value, tooltip_value

Point2D = tuple[float, float]


def add_metadata_styles(builder: StyleBuilder, elem: Element, ctx: EmitterContext) -> StyleBuilder:
    """Append tooltip and link entries that apply to most emitted cells."""
    return builder.add("tooltip", tooltip_value(elem)).add("link", link_value(ctx.link_url))


def add_gradient_styles(builder: StyleBuilder, gradient: GradientStyle | None) -> StyleBuilder:
    """Append gradient-related style entries when a gradient is present."""
    return builder.extend_pairs(gradient_entries(gradient))


def add_filter_styles(
    builder: StyleBuilder,
    ctx: EmitterContext,
    elem: Element,
    filter_ref: str | None,
    *,
    fallback_color: str | None = None,
) -> StyleBuilder:
    """Append filter-related style entries when the SVG element references one."""
    resolution = ctx.defs.resolve_filter_style(filter_ref, fallback_color=fallback_color)
    if resolution is None:
        return builder

    if resolution.approximated:
        ctx.report.add_issue(
            FILTER_SIMPLIFIED_NATIVE,
            "warning",
            resolution.detail,
            element_tag=elem.tag.rsplit("}", 1)[-1],
            element_id=elem.get("id"),
        )
    ctx.report.record_feature_observation(
        note_filter_usage(
            native=not resolution.approximated,
            approximated=resolution.approximated,
            detail=resolution.detail,
        )
    )
    return builder.extend_pairs(resolution.entries)


def emit_midpoint_markers(
    ctx: EmitterContext,
    points: Sequence[Point2D],
    color: str,
    opacity: int,
    size: float = 8.0,
) -> None:
    """Emit simple midpoint marker dots for `marker-mid` support on editable edges."""
    for px, py in points:
        style = (
            StyleBuilder()
            .add_flag("ellipse")
            .add("fillColor", color)
            .add("strokeColor", color)
            .add("opacity", opacity)
            .build()
        )
        ctx.add(make_bounds_vertex(ctx, style, px - size / 2, py - size / 2, size, size))


def segment_angle_degrees(start: Point2D, end: Point2D) -> float:
    """Return the angle of a line segment in degrees."""
    return math.degrees(math.atan2(end[1] - start[1], end[0] - start[0]))


def extend_edge_endpoints(
    source: Point2D,
    target: Point2D,
    waypoints: Sequence[Point2D],
    *,
    start_extension: float = 0.0,
    end_extension: float = 0.0,
) -> tuple[Point2D, Point2D]:
    """Extend edge endpoints to preserve SVG marker tips beyond their reference points."""

    def extend(point: Point2D, neighbor: Point2D, distance: float) -> Point2D:
        dx = point[0] - neighbor[0]
        dy = point[1] - neighbor[1]
        length = math.hypot(dx, dy)
        if distance <= 0.0 or length <= 1e-9:
            return point
        return point[0] + dx / length * distance, point[1] + dy / length * distance

    source_neighbor = waypoints[0] if waypoints else target
    target_neighbor = waypoints[-1] if waypoints else source
    return (
        extend(source, source_neighbor, start_extension),
        extend(target, target_neighbor, end_extension),
    )


def add_native_arrow_styles(
    style: StyleBuilder,
    start_arrow: str,
    end_arrow: str,
) -> StyleBuilder:
    """Append draw.io arrow types with explicit fill behavior."""
    style.add("startArrow", start_arrow).add("endArrow", end_arrow)
    style.add("startFill", 0 if start_arrow == "open" else 1, when=start_arrow != "none")
    style.add("endFill", 0 if end_arrow == "open" else 1, when=end_arrow != "none")
    return style


def emit_endpoint_marker(
    ctx: EmitterContext,
    point: Point2D,
    shape: str,
    color: str,
    opacity: int,
    *,
    size: float = 10.0,
    rotation: float | None = None,
) -> None:
    """Emit a simple editable endpoint marker shape near an edge endpoint."""
    style = StyleBuilder()
    if shape == "ellipse":
        style.add_flag("ellipse")
    elif shape == "diamond":
        style.add("shape", "rhombus").add("whiteSpace", "wrap").add("html", 1)
    elif shape == "triangle":
        style.add("shape", "triangle").add("whiteSpace", "wrap").add("html", 1)
    else:
        style.add("rounded", 0).add("whiteSpace", "wrap").add("html", 1)
    style.add("fillColor", color).add("strokeColor", color).add("opacity", opacity)
    style.add("rotation", f"{rotation:.2f}", when=rotation is not None)
    ctx.add(make_bounds_vertex(ctx, style.build(), point[0] - size / 2, point[1] - size / 2, size, size))
