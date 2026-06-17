"""Emitters for SVG polylines and polygons."""

from __future__ import annotations

import re
from xml.etree.ElementTree import Element

from ..cell_factory import make_box_vertex, make_edge
from ..compatibility import note_marker_usage, note_shape_usage
from ..element_geometry import bounds_from_points
from ..emitter_context import EmitterContext
from ..path_utils import make_stencil_style_from_xml
from ..style_builder import StyleBuilder
from ..styles import get_visual, opacity_pct
from ..transforms import Matrix, apply_pt, stroke_scale
from .style_support import (
    add_filter_styles,
    add_metadata_styles,
    emit_endpoint_marker,
    emit_midpoint_markers,
    segment_angle_degrees,
)

_POINT_RE = re.compile(r"[-\d.eE+]+")


def emit_polyline(
    ctx: EmitterContext,
    elem: Element,
    matrix: Matrix,
    closed: bool = False,
    css: dict[str, str] | None = None,
) -> None:
    """Emit an SVG `<polyline>` or `<polygon>`."""
    visual = get_visual(elem, css)
    coords = _POINT_RE.findall(elem.get("points", ""))
    points = [apply_pt(matrix, float(coords[i]), float(coords[i + 1])) for i in range(0, len(coords) - 1, 2)]
    if len(points) < 2:
        return

    ctx.report.record_feature_observation(note_shape_usage(approximated=False))
    stroke_color = visual["stroke"] or "#000000"
    fill = visual["fill"] or "none"
    opacity = opacity_pct(visual["opacity"])
    fill_opacity = opacity_pct(visual["fill_opacity"])
    stroke_opacity = opacity_pct(visual["stroke_opacity"])
    stroke_width = visual["stroke_width"] * stroke_scale(matrix)

    if closed and fill != "none":
        box = bounds_from_points(points)
        first_x = (points[0][0] - box.x) / box.width * 100
        first_y = (points[0][1] - box.y) / box.height * 100
        path_parts = [f'<move x="{first_x:.2f}" y="{first_y:.2f}"/>']
        path_parts.extend(
            f'<line x="{(px - box.x) / box.width * 100:.2f}" y="{(py - box.y) / box.height * 100:.2f}"/>'
            for px, py in points[1:]
        )
        path_parts.append("<close/>")
        xml = (
            '<shape w="100" h="100" aspect="variable" strokewidth="inherit">'
            f"<background><path>{''.join(path_parts)}</path><fillstroke/></background></shape>"
        )
        stencil_style = make_stencil_style_from_xml(xml, fill, stroke_color, stroke_width, opacity)
        if not stencil_style:
            return
        style = StyleBuilder().extend_raw(stencil_style)
        style.add("fillOpacity", fill_opacity).add("strokeOpacity", stroke_opacity)
        style.extend_raw(visual["dash_style"])
        add_metadata_styles(style, elem, ctx)
        add_filter_styles(style, ctx, visual["filter"])
        ctx.add(make_box_vertex(ctx, style.build(), box))
        return

    start_arrow = ctx.defs.resolve_marker(visual["marker_start"])
    end_arrow = ctx.defs.resolve_marker(visual["marker_end"])
    start_shape = ctx.defs.resolve_custom_marker_shape(visual["marker_start"])
    end_shape = ctx.defs.resolve_custom_marker_shape(visual["marker_end"])
    if start_shape is not None:
        start_arrow = "none"
    if end_shape is not None:
        end_arrow = "none"
    if start_arrow != "none" or end_arrow != "none" or visual.get("marker_mid") or start_shape or end_shape:
        ctx.report.record_feature_observation(note_marker_usage())
    src, *mid, tgt = points
    style = StyleBuilder()
    style.add("rounded", 1 if visual["linejoin"] == "round" else 0)
    style.add("lineCap", visual["linecap"], when=visual["linecap"] != "flat")
    style.add("lineJoin", visual["linejoin"], when=visual["linejoin"] != "miter")
    style.add("startArrow", start_arrow).add("endArrow", end_arrow).add("html", 1)
    style.add("strokeColor", stroke_color).add("strokeWidth", stroke_width)
    style.add("opacity", opacity).add("strokeOpacity", stroke_opacity)
    style.extend_raw(visual["dash_style"])
    add_metadata_styles(style, elem, ctx)
    add_filter_styles(style, ctx, visual["filter"])
    ctx.add(make_edge(ctx, style.build(), src, tgt, waypoints=mid))

    marker_size = max(stroke_width * 4.0, 8.0)
    if start_shape is not None:
        emit_endpoint_marker(
            ctx,
            src,
            start_shape,
            stroke_color,
            opacity,
            size=marker_size,
            rotation=segment_angle_degrees(src, mid[0] if mid else tgt) + 180.0,
        )
    if end_shape is not None:
        emit_endpoint_marker(
            ctx,
            tgt,
            end_shape,
            stroke_color,
            opacity,
            size=marker_size,
            rotation=segment_angle_degrees(mid[-1] if mid else src, tgt),
        )
    if visual.get("marker_mid") and mid:
        emit_midpoint_markers(ctx, mid, stroke_color, opacity)
