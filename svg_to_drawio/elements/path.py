"""Emitters for SVG path elements."""

from __future__ import annotations

import re
from xml.etree.ElementTree import Element

from ..cell_factory import make_bounds_vertex, make_edge
from ..emitter_context import EmitterContext
from ..path_utils import commands_bbox, make_stencil_style_from_commands, path_commands, sample_open_path
from ..style_builder import StyleBuilder
from ..styles import VisualStyle, get_visual, opacity_pct
from ..transforms import Matrix, apply_pt, stroke_scale
from .style_support import add_filter_styles, add_gradient_styles, add_metadata_styles, emit_midpoint_markers


def _is_closed(path_data: str | None) -> bool:
    """Return whether the path contains a close command."""
    path_text = path_data or ""
    return any(char in path_text for char in ("Z", "z"))


def _has_curve_commands(path_data: str | None) -> bool:
    """Return whether the path contains Bezier or arc commands."""
    return bool(re.search(r"[CcSsQqTtAa]", path_data or ""))


def _emit_open_path_as_edge(
    ctx: EmitterContext,
    elem: Element,
    path_data: str,
    matrix: Matrix,
    visual: VisualStyle,
) -> None:
    """Render an open unfilled path as a draw.io edge with sampled waypoints."""
    points_t = [apply_pt(matrix, px, py) for px, py in sample_open_path(path_data)]
    if len(points_t) < 2:
        return

    stroke_color = visual["stroke"] or "#000000"
    opacity = opacity_pct(visual["opacity"])
    stroke_opacity = opacity_pct(visual["stroke_opacity"])
    stroke_width = visual["stroke_width"] * stroke_scale(matrix)
    start_arrow = ctx.defs.resolve_marker(visual["marker_start"])
    end_arrow = ctx.defs.resolve_marker(visual["marker_end"])

    src, *mid, tgt = points_t
    style = StyleBuilder()
    style.add("rounded", 1 if visual["linejoin"] == "round" else 0, when=not (_has_curve_commands(path_data) and mid))
    style.add("lineCap", visual["linecap"], when=visual["linecap"] != "flat")
    style.add("lineJoin", visual["linejoin"], when=visual["linejoin"] != "miter")
    style.add("curved", 1, when=_has_curve_commands(path_data) and bool(mid))
    style.add("startArrow", start_arrow).add("endArrow", end_arrow).add("html", 1)
    style.add("strokeColor", stroke_color).add("strokeWidth", stroke_width)
    style.add("opacity", opacity).add("strokeOpacity", stroke_opacity)
    style.extend_raw(visual["dash_style"])
    add_metadata_styles(style, elem, ctx)
    add_filter_styles(style, ctx, visual["filter"])
    ctx.add(make_edge(ctx, style.build(), src, tgt, waypoints=mid))

    if visual.get("marker_mid") and mid:
        emit_midpoint_markers(ctx, mid, stroke_color, opacity)


def emit_path(ctx: EmitterContext, elem: Element, matrix: Matrix, css: dict[str, str] | None = None) -> None:
    """Emit an SVG `<path>`."""
    visual = get_visual(elem, css)
    path_data = elem.get("d", "")
    if not path_data:
        return

    fill, gradient = ctx.defs.resolve_fill(visual["fill"] or "none")

    has_markers = visual["marker_start"] or visual["marker_end"] or visual["marker_mid"]
    if fill == "none" and has_markers:
        _emit_open_path_as_edge(ctx, elem, path_data, matrix, visual)
        return

    commands = path_commands(path_data, point_transform=lambda x, y: apply_pt(matrix, x, y))
    if not commands:
        return
    bbox = commands_bbox(commands)
    if not bbox:
        return
    bx, by, bw, bh = bbox

    stroke_color = visual["stroke"] or "#000000"
    opacity = opacity_pct(visual["opacity"])
    fill_opacity = opacity_pct(visual["fill_opacity"])
    stroke_opacity = opacity_pct(visual["stroke_opacity"])
    stroke_width = visual["stroke_width"] * stroke_scale(matrix)
    fill_rule = visual.get("fill_rule", "nonzero")

    stencil_style = make_stencil_style_from_commands(
        commands,
        bx,
        by,
        bw,
        bh,
        fill,
        stroke_color,
        stroke_width,
        opacity,
        fill_rule=fill_rule,
        linecap=visual["linecap"],
        linejoin=visual["linejoin"],
    )
    if not stencil_style:
        return

    style = StyleBuilder().extend_raw(stencil_style)
    style.add("fillOpacity", fill_opacity).add("strokeOpacity", stroke_opacity)
    add_gradient_styles(style, gradient)
    style.extend_raw(visual["dash_style"])
    add_metadata_styles(style, elem, ctx)
    add_filter_styles(style, ctx, visual["filter"])
    ctx.add(make_bounds_vertex(ctx, style.build(), bx, by, bw, bh))
