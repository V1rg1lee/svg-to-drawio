"""Shared helpers for primitive shape emitters."""

from __future__ import annotations

from collections.abc import Sequence
from xml.etree.ElementTree import Element

from ..cell_factory import make_box_vertex
from ..element_geometry import bounds_from_points
from ..emitter_context import EmitterContext
from ..path_utils import (
    PathCommand,
    commands_bbox,
    make_stencil_style_from_commands,
    make_stencil_style_from_xml,
    path_commands,
)
from ..rendering_options import normalize_filter_ref
from ..style_builder import StyleBuilder
from ..styles import GradientStyle
from ..transforms import Matrix, apply_pt
from .style_support import add_filter_styles, add_gradient_styles, add_metadata_styles

Point2D = tuple[float, float]


def multi_stop_filter_refs(ctx: EmitterContext, filter_ref: str | None) -> tuple[str | None, str | None]:
    """Return the filter refs used for approximation support checks and emitted children."""
    normalized = normalize_filter_ref(filter_ref)
    if normalized is None:
        return None, None
    if ctx.rendering_options.filter_policy != "prefer-native":
        return normalized, None
    return None, normalized if ctx.defs.supports_filter(normalized) else None


def emit_polygon_stencil(
    ctx: EmitterContext,
    elem: Element,
    corners: Sequence[Point2D],
    fill: str | None,
    gradient: GradientStyle | None,
    stroke: str | None,
    stroke_width: float,
    opacity: int,
    fill_opacity: int,
    stroke_opacity: int,
    dash: str = "",
    filter_ref: str | None = None,
) -> None:
    """Emit a closed polygon as a draw.io stencil when no native shape fits."""
    box = bounds_from_points(corners)

    def norm_x(x: float) -> float:
        return (x - box.x) / box.width * 100

    def norm_y(y: float) -> float:
        return (y - box.y) / box.height * 100

    path_xml = f'<move x="{norm_x(corners[0][0]):.2f}" y="{norm_y(corners[0][1]):.2f}"/>'
    for corner_x, corner_y in corners[1:]:
        path_xml += f'<line x="{norm_x(corner_x):.2f}" y="{norm_y(corner_y):.2f}"/>'
    path_xml += "<close/>"

    xml = (
        '<shape w="100" h="100" aspect="variable" strokewidth="inherit">'
        f"<background><path>{path_xml}</path><fillstroke/></background></shape>"
    )
    stencil_style = make_stencil_style_from_xml(xml, fill, stroke, stroke_width, opacity)
    if not stencil_style:
        return

    style = StyleBuilder().extend_raw(stencil_style)
    style.add("fillOpacity", fill_opacity).add("strokeOpacity", stroke_opacity)
    add_gradient_styles(style, gradient)
    style.extend_raw(dash)
    add_metadata_styles(style, elem, ctx)
    add_filter_styles(style, ctx, elem, filter_ref, fallback_color=fill if fill != "none" else stroke)
    ctx.add(make_box_vertex(ctx, style.build(), box))


def emit_stencil_commands(
    ctx: EmitterContext,
    elem: Element,
    commands: Sequence[PathCommand],
    fill: str | None,
    gradient: GradientStyle | None,
    stroke: str | None,
    stroke_width: float,
    opacity: int,
    fill_opacity: int,
    stroke_opacity: int,
    dash: str = "",
    fill_rule: str = "nonzero",
    linecap: str = "flat",
    linejoin: str = "miter",
    filter_ref: str | None = None,
) -> None:
    """Emit a shape from parsed path commands."""
    bbox = commands_bbox(commands)
    if not bbox:
        return
    bx, by, bw, bh = bbox
    stencil_style = make_stencil_style_from_commands(
        commands,
        bx,
        by,
        bw,
        bh,
        fill,
        stroke,
        stroke_width,
        opacity,
        fill_rule=fill_rule,
        linecap=linecap,
        linejoin=linejoin,
    )
    if not stencil_style:
        return

    style = StyleBuilder().extend_raw(stencil_style)
    style.add("fillOpacity", fill_opacity).add("strokeOpacity", stroke_opacity)
    add_gradient_styles(style, gradient)
    style.extend_raw(dash)
    add_metadata_styles(style, elem, ctx)
    add_filter_styles(style, ctx, elem, filter_ref, fallback_color=fill if fill != "none" else stroke)
    box = bounds_from_points(((bx, by), (bx + bw, by + bh)))
    ctx.add(make_box_vertex(ctx, style.build(), box))


def emit_transformed_path_stencil(
    ctx: EmitterContext,
    elem: Element,
    path_data: str,
    matrix: Matrix,
    fill: str | None,
    gradient: GradientStyle | None,
    stroke: str | None,
    stroke_width: float,
    opacity: int,
    fill_opacity: int,
    stroke_opacity: int,
    dash: str = "",
    linecap: str = "flat",
    linejoin: str = "miter",
    filter_ref: str | None = None,
) -> None:
    """Transform a primitive into path commands and render it as a stencil."""
    commands = path_commands(path_data, point_transform=lambda x, y: apply_pt(matrix, x, y))
    emit_stencil_commands(
        ctx,
        elem,
        commands,
        fill,
        gradient,
        stroke,
        stroke_width,
        opacity,
        fill_opacity,
        stroke_opacity,
        dash,
        linecap=linecap,
        linejoin=linejoin,
        filter_ref=filter_ref,
    )
