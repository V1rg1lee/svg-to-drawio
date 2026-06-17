"""Shared style and marker helpers for SVG element emitters."""

from __future__ import annotations

from collections.abc import Sequence
from xml.etree.ElementTree import Element

from ..cell_factory import make_bounds_vertex
from ..compatibility import note_filter_usage
from ..emitter_context import EmitterContext
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


def add_filter_styles(builder: StyleBuilder, ctx: EmitterContext, filter_ref: str | None) -> StyleBuilder:
    """Append filter-related style entries when the SVG element references one."""
    entries = ctx.defs.resolve_filter_entries(filter_ref)
    if entries:
        ctx.report.record_feature_observation(note_filter_usage(native=True))
    return builder.extend_pairs(entries)


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
