"""Emitters for SVG primitive shapes."""

from __future__ import annotations

from xml.etree.ElementTree import Element

from ..cell_factory import make_bounds_vertex, make_box_vertex, make_edge
from ..compatibility import note_gradient_usage, note_marker_usage, note_shape_usage
from ..element_geometry import ellipse_bounds, has_shear, line_endpoints, rect_bounds, rect_corners
from ..emitter_context import EmitterContext
from ..path_utils import make_stencil_style_from_commands
from ..rendering_options import normalize_filter_ref
from ..style_builder import StyleBuilder
from ..styles import get_visual, opacity_pct
from ..transforms import Matrix, stroke_scale
from ..utils import parse_length
from .gradient_approx import (
    ShapeSpec,
    emit_multi_stop_gradient_approximation,
    supports_multi_stop_gradient_approximation,
)
from .shape_paths import ellipse_path_d, rounded_rect_path_d
from .shape_support import emit_polygon_stencil, emit_transformed_path_stencil
from .style_support import add_filter_styles, add_gradient_styles, add_metadata_styles


def _multi_stop_filter_refs(ctx: EmitterContext, filter_ref: str | None) -> tuple[str | None, str | None]:
    """Return the filter refs used for approximation support checks and emitted children."""
    normalized = normalize_filter_ref(filter_ref)
    if normalized is None:
        return None, None
    if ctx.rendering_options.filter_policy != "prefer-native":
        return normalized, None
    return None, normalized if ctx.defs.supports_filter(normalized) else None


def emit_line(ctx: EmitterContext, elem: Element, matrix: Matrix, css: dict[str, str] | None = None) -> None:
    """Emit an SVG `<line>`."""
    visual = get_visual(elem, css)
    (x1, y1), (x2, y2) = line_endpoints(
        matrix,
        parse_length(elem.get("x1")),
        parse_length(elem.get("y1")),
        parse_length(elem.get("x2")),
        parse_length(elem.get("y2")),
    )
    stroke_color = visual["stroke"] or "#000000"
    opacity = opacity_pct(visual["opacity"])
    stroke_opacity = opacity_pct(visual["stroke_opacity"])
    stroke_width = visual["stroke_width"] * stroke_scale(matrix)
    start_arrow = ctx.defs.resolve_marker(visual["marker_start"])
    end_arrow = ctx.defs.resolve_marker(visual["marker_end"])
    linecap = visual["linecap"]
    if start_arrow != "none" or end_arrow != "none":
        ctx.report.record_feature_observation(note_marker_usage())

    # Non-flat linecap without markers: emit as a stencil vertex so draw.io's
    # stencil renderer applies strokelinecap from the XML. Edge connectors do not
    # support linecap, so this is the only way to render round/square caps.
    if linecap != "flat" and start_arrow == "none" and end_arrow == "none":
        pad = stroke_width / 2
        bx = min(x1, x2) - pad
        by = min(y1, y2) - pad
        bw = max(abs(x2 - x1) + stroke_width, 1.0)
        bh = max(abs(y2 - y1) + stroke_width, 1.0)
        cmds = [("move", ((x1, y1),)), ("line", ((x2, y2),))]
        stencil_style = make_stencil_style_from_commands(
            cmds, bx, by, bw, bh, "none", stroke_color, stroke_width, opacity, linecap=linecap
        )
        if stencil_style:
            ctx.report.record_feature_observation(note_shape_usage(approximated=True))
            style = StyleBuilder().extend_raw(stencil_style)
            style.add("strokeOpacity", stroke_opacity)
            style.extend_raw(visual["dash_style"])
            add_metadata_styles(style, elem, ctx)
            add_filter_styles(style, ctx, visual["filter"])
            ctx.add(make_bounds_vertex(ctx, style.build(), bx, by, bw, bh))
        return

    ctx.report.record_feature_observation(note_shape_usage(approximated=False))
    style = StyleBuilder()
    style.add("rounded", 0)
    style.add("startArrow", start_arrow).add("endArrow", end_arrow).add("html", 1)
    style.add("strokeColor", stroke_color).add("strokeWidth", f"{stroke_width:.2f}")
    style.add("opacity", opacity).add("strokeOpacity", stroke_opacity)
    style.extend_raw(visual["dash_style"])
    add_metadata_styles(style, elem, ctx)
    add_filter_styles(style, ctx, visual["filter"])
    ctx.add(make_edge(ctx, style.build(), (x1, y1), (x2, y2)))


def emit_circle(ctx: EmitterContext, elem: Element, matrix: Matrix, css: dict[str, str] | None = None) -> None:
    """Emit an SVG `<circle>`."""
    visual = get_visual(elem, css)
    cx0 = parse_length(elem.get("cx"))
    cy0 = parse_length(elem.get("cy"))
    radius = parse_length(elem.get("r"))
    fill, gradient = ctx.defs.resolve_fill(visual["fill"] or "none")
    stroke = visual["stroke"] or "none"
    opacity = opacity_pct(visual["opacity"])
    fill_opacity = opacity_pct(visual["fill_opacity"])
    stroke_opacity = opacity_pct(visual["stroke_opacity"])
    stroke_width = visual["stroke_width"] * stroke_scale(matrix)
    approx_support_filter, approx_style_filter = _multi_stop_filter_refs(ctx, visual["filter"])

    if supports_multi_stop_gradient_approximation("circle", matrix, gradient, filter_ref=approx_support_filter):
        assert gradient is not None
        ctx.report.record_feature_observation(note_shape_usage(approximated=False))
        ctx.report.record_feature_observation(note_gradient_usage(approximated=True))
        emit_multi_stop_gradient_approximation(
            ctx,
            elem,
            matrix,
            ShapeSpec("ellipse", cx0 - radius, cy0 - radius, radius * 2, radius * 2),
            gradient,
            stroke=stroke,
            stroke_width=stroke_width,
            opacity=opacity,
            fill_opacity=fill_opacity,
            stroke_opacity=stroke_opacity,
            dash=visual["dash_style"],
            filter_ref=approx_style_filter,
        )
        return

    if has_shear(matrix):
        ctx.report.record_feature_observation(note_shape_usage(approximated=True))
        if gradient is not None:
            ctx.report.record_feature_observation(note_gradient_usage(approximated=False))
        emit_transformed_path_stencil(
            ctx,
            elem,
            ellipse_path_d(cx0, cy0, radius, radius),
            matrix,
            fill,
            gradient,
            stroke,
            stroke_width,
            opacity,
            fill_opacity,
            stroke_opacity,
            visual["dash_style"],
            linecap=visual["linecap"],
            linejoin=visual["linejoin"],
            filter_ref=visual["filter"],
        )
        return

    ctx.report.record_feature_observation(note_shape_usage(approximated=False))
    if gradient is not None:
        ctx.report.record_feature_observation(note_gradient_usage(approximated=False))
    box = ellipse_bounds(matrix, cx0, cy0, radius, radius)
    rotation = box.rotation_if_visible() if box.has_distinct_axes() else None
    rotation_style = f"{rotation:.2f}" if rotation is not None else None

    style = StyleBuilder()
    style.add_flag("ellipse").add("whiteSpace", "wrap").add("html", 1)
    style.add("fillColor", fill).add("strokeColor", stroke).add("strokeWidth", stroke_width)
    style.add("opacity", opacity).add("fillOpacity", fill_opacity).add("strokeOpacity", stroke_opacity)
    add_gradient_styles(style, gradient)
    style.extend_raw(visual["dash_style"])
    style.add("rotation", rotation_style, when=rotation_style is not None)
    add_metadata_styles(style, elem, ctx)
    add_filter_styles(style, ctx, visual["filter"])

    ctx.add(make_box_vertex(ctx, style.build(), box))


def emit_ellipse(ctx: EmitterContext, elem: Element, matrix: Matrix, css: dict[str, str] | None = None) -> None:
    """Emit an SVG `<ellipse>`."""
    visual = get_visual(elem, css)
    cx0 = parse_length(elem.get("cx"))
    cy0 = parse_length(elem.get("cy"))
    rx0 = parse_length(elem.get("rx"))
    ry0 = parse_length(elem.get("ry"))
    fill, gradient = ctx.defs.resolve_fill(visual["fill"] or "none")
    stroke = visual["stroke"] or "none"
    opacity = opacity_pct(visual["opacity"])
    fill_opacity = opacity_pct(visual["fill_opacity"])
    stroke_opacity = opacity_pct(visual["stroke_opacity"])
    stroke_width = visual["stroke_width"] * stroke_scale(matrix)
    approx_support_filter, approx_style_filter = _multi_stop_filter_refs(ctx, visual["filter"])

    if supports_multi_stop_gradient_approximation("ellipse", matrix, gradient, filter_ref=approx_support_filter):
        assert gradient is not None
        ctx.report.record_feature_observation(note_shape_usage(approximated=False))
        ctx.report.record_feature_observation(note_gradient_usage(approximated=True))
        emit_multi_stop_gradient_approximation(
            ctx,
            elem,
            matrix,
            ShapeSpec("ellipse", cx0 - rx0, cy0 - ry0, rx0 * 2, ry0 * 2),
            gradient,
            stroke=stroke,
            stroke_width=stroke_width,
            opacity=opacity,
            fill_opacity=fill_opacity,
            stroke_opacity=stroke_opacity,
            dash=visual["dash_style"],
            filter_ref=approx_style_filter,
        )
        return

    if has_shear(matrix):
        ctx.report.record_feature_observation(note_shape_usage(approximated=True))
        if gradient is not None:
            ctx.report.record_feature_observation(note_gradient_usage(approximated=False))
        emit_transformed_path_stencil(
            ctx,
            elem,
            ellipse_path_d(cx0, cy0, rx0, ry0),
            matrix,
            fill,
            gradient,
            stroke,
            stroke_width,
            opacity,
            fill_opacity,
            stroke_opacity,
            visual["dash_style"],
            linecap=visual["linecap"],
            linejoin=visual["linejoin"],
            filter_ref=visual["filter"],
        )
        return

    ctx.report.record_feature_observation(note_shape_usage(approximated=False))
    if gradient is not None:
        ctx.report.record_feature_observation(note_gradient_usage(approximated=False))
    box = ellipse_bounds(matrix, cx0, cy0, rx0, ry0)
    rotation = box.rotation_if_visible()
    rotation_style = f"{rotation:.2f}" if rotation is not None else None

    style = StyleBuilder()
    style.add_flag("ellipse").add("whiteSpace", "wrap").add("html", 1)
    style.add("fillColor", fill).add("strokeColor", stroke).add("strokeWidth", stroke_width)
    style.add("opacity", opacity).add("fillOpacity", fill_opacity).add("strokeOpacity", stroke_opacity)
    add_gradient_styles(style, gradient)
    style.extend_raw(visual["dash_style"])
    style.add("rotation", rotation_style, when=rotation_style is not None)
    add_metadata_styles(style, elem, ctx)
    add_filter_styles(style, ctx, visual["filter"])

    ctx.add(make_box_vertex(ctx, style.build(), box))


def emit_rect(ctx: EmitterContext, elem: Element, matrix: Matrix, css: dict[str, str] | None = None) -> None:
    """Emit an SVG `<rect>`."""
    visual = get_visual(elem, css)
    x0 = parse_length(elem.get("x"))
    y0 = parse_length(elem.get("y"))
    width0 = parse_length(elem.get("width"))
    height0 = parse_length(elem.get("height"))
    rx = parse_length(elem.get("rx", "0")) or 0.0
    ry = parse_length(elem.get("ry", "0")) or 0.0
    if rx <= 0 < ry:
        rx = ry
    if ry <= 0 < rx:
        ry = rx

    fill, gradient = ctx.defs.resolve_fill(visual["fill"] or "#ffffff")
    stroke = visual["stroke"] or "none"
    opacity = opacity_pct(visual["opacity"])
    fill_opacity = opacity_pct(visual["fill_opacity"])
    stroke_opacity = opacity_pct(visual["stroke_opacity"])
    stroke_width = visual["stroke_width"] * stroke_scale(matrix)
    approx_support_filter, approx_style_filter = _multi_stop_filter_refs(ctx, visual["filter"])

    if supports_multi_stop_gradient_approximation("rect", matrix, gradient, filter_ref=approx_support_filter):
        assert gradient is not None
        ctx.report.record_feature_observation(note_shape_usage(approximated=False))
        ctx.report.record_feature_observation(note_gradient_usage(approximated=True))
        emit_multi_stop_gradient_approximation(
            ctx,
            elem,
            matrix,
            ShapeSpec("rect", x0, y0, width0, height0, rx=rx, ry=ry),
            gradient,
            stroke=stroke,
            stroke_width=stroke_width,
            opacity=opacity,
            fill_opacity=fill_opacity,
            stroke_opacity=stroke_opacity,
            dash=visual["dash_style"],
            filter_ref=approx_style_filter,
        )
        return

    if has_shear(matrix):
        ctx.report.record_feature_observation(note_shape_usage(approximated=True))
        if gradient is not None:
            ctx.report.record_feature_observation(note_gradient_usage(approximated=False))
        if rx > 0 or ry > 0:
            emit_transformed_path_stencil(
                ctx,
                elem,
                rounded_rect_path_d(x0, y0, width0, height0, rx, ry),
                matrix,
                fill,
                gradient,
                stroke,
                stroke_width,
                opacity,
                fill_opacity,
                stroke_opacity,
                visual["dash_style"],
                linecap=visual["linecap"],
                linejoin=visual["linejoin"],
                filter_ref=visual["filter"],
            )
            return
        corners = rect_corners(matrix, x0, y0, width0, height0)
        emit_polygon_stencil(
            ctx,
            elem,
            corners,
            fill,
            gradient,
            stroke,
            stroke_width,
            opacity,
            fill_opacity,
            stroke_opacity,
            visual["dash_style"],
            filter_ref=visual["filter"],
        )
        return

    ctx.report.record_feature_observation(note_shape_usage(approximated=False))
    if gradient is not None:
        ctx.report.record_feature_observation(note_gradient_usage(approximated=False))
    box = rect_bounds(matrix, x0, y0, width0, height0)
    rotation = box.rotation_if_visible()
    rotation_style = f"{rotation:.2f}" if rotation is not None else None

    style = StyleBuilder()
    if rx > 0 or ry > 0:
        shorter_side = min(width0, height0) if width0 > 0 and height0 > 0 else 1.0
        arc_pct = min(50, round(max(rx, ry) / shorter_side * 100))
        style.add("rounded", 1).add("arcSize", arc_pct)
    else:
        style.add("rounded", 0)
    style.add("whiteSpace", "wrap").add("html", 1)
    style.add("fillColor", fill).add("strokeColor", stroke).add("strokeWidth", stroke_width)
    style.add("opacity", opacity).add("fillOpacity", fill_opacity).add("strokeOpacity", stroke_opacity)
    add_gradient_styles(style, gradient)
    style.extend_raw(visual["dash_style"])
    style.add("rotation", rotation_style, when=rotation_style is not None)
    add_metadata_styles(style, elem, ctx)
    add_filter_styles(style, ctx, visual["filter"])

    ctx.add(make_box_vertex(ctx, style.build(), box))
