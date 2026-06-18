"""Native approximations for SVG multi-stop gradients on simple shapes."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from xml.etree.ElementTree import Element

from ..cell_factory import make_bounds_vertex, make_box_vertex
from ..drawio_model import Cell, group_bbox, shift_cells
from ..element_geometry import ellipse_bounds, has_shear, rect_bounds
from ..emitter_context import EmitterContext
from ..polygon_clip import clip_polygon_strip, commands_to_polygon
from ..style_builder import StyleBuilder
from ..styles import GradientStyle
from ..transforms import Matrix, apply_pt
from .shape_support import emit_polygon_stencil, emit_stencil_commands
from .style_support import add_filter_styles, add_metadata_styles

Point2D = tuple[float, float]

_APPROXIMATION_TAGS: frozenset[str] = frozenset({"rect", "circle", "ellipse"})
_LINEAR_PATH_TAGS: frozenset[str] = frozenset({"path"})
_RADIAL_MAX_STEPS = 96  # hard cap: beyond this, file size / render cost outweigh quality gains
_RADIAL_MIN_STEPS = 16  # floor: even tiny shapes get at least 16 rings
_RADIAL_TARGET_PX = 1.5  # target ring width in SVG units - keeps steps sub-pixel at normal zoom
_SAMPLES_PER_CURVE = 32  # linear bands: samples per edge for arc approximation in rounded corners
_BAND_OVERLAP = 0.002  # linear bands: normalized overlap to prevent sub-pixel anti-aliasing gaps


@dataclass(frozen=True)
class ShapeSpec:
    """Axis-aligned local geometry for one shape that can receive a native gradient approximation."""

    kind: str
    x: float
    y: float
    width: float
    height: float
    rx: float = 0.0
    ry: float = 0.0

    @property
    def cx(self) -> float:
        """Return the center x coordinate."""
        return self.x + self.width / 2

    @property
    def cy(self) -> float:
        """Return the center y coordinate."""
        return self.y + self.height / 2

    def scaled(self, ratio: float) -> ShapeSpec:
        """Return a centered copy scaled uniformly around the shape center."""
        ratio = max(0.0, min(1.0, ratio))
        new_width = self.width * ratio
        new_height = self.height * ratio
        return ShapeSpec(
            kind=self.kind,
            x=self.cx - new_width / 2,
            y=self.cy - new_height / 2,
            width=new_width,
            height=new_height,
            rx=self.rx * ratio,
            ry=self.ry * ratio,
        )


def is_multi_stop_gradient(gradient: GradientStyle | None) -> bool:
    """Return whether a resolved gradient contains more than two color stops."""
    return gradient is not None and len(gradient["stops"]) > 2


def supports_multi_stop_gradient_approximation(
    tag: str,
    matrix: Matrix,
    gradient: GradientStyle | None,
    *,
    filter_ref: str | None = None,
) -> bool:
    """Return whether a simple shape can be approximated natively instead of falling back to SVG."""
    if gradient is None or not is_multi_stop_gradient(gradient) or filter_ref:
        return False
    if has_shear(matrix):
        return False
    if tag in _APPROXIMATION_TAGS:
        return True
    if tag in _LINEAR_PATH_TAGS and gradient["kind"] == "linear":
        return True
    return False


def emit_multi_stop_gradient_approximation(
    ctx: EmitterContext,
    elem: Element,
    matrix: Matrix,
    spec: ShapeSpec,
    gradient: GradientStyle,
    *,
    stroke: str,
    stroke_width: float,
    opacity: int,
    fill_opacity: int,
    stroke_opacity: int,
    dash: str = "",
    filter_ref: str | None = None,
) -> None:
    """Approximate a multi-stop gradient with grouped native vector children."""
    group_id = ctx.next_id()
    child_cells: list[Cell] = []
    child_ctx = replace(ctx.with_parent(group_id), add_cell=child_cells.append)

    if gradient["kind"] == "radial":
        _emit_radial_layers(
            child_ctx,
            elem,
            matrix,
            spec,
            gradient,
            opacity=opacity,
            fill_opacity=fill_opacity,
            filter_ref=filter_ref,
        )
    else:
        _emit_linear_bands(
            child_ctx,
            elem,
            matrix,
            spec,
            gradient,
            opacity=opacity,
            fill_opacity=fill_opacity,
            filter_ref=filter_ref,
        )

    if stroke != "none" and stroke_width > 0:
        _emit_shape_stroke_overlay(
            child_ctx,
            elem,
            matrix,
            spec,
            stroke=stroke,
            stroke_width=stroke_width,
            opacity=opacity,
            stroke_opacity=stroke_opacity,
            dash=dash,
            filter_ref=filter_ref,
        )

    if not child_cells:
        return

    direct_children = [cell for cell in child_cells if cell.parent == group_id]
    gx, gy, gw, gh = group_bbox(direct_children)
    ctx.add(make_bounds_vertex(ctx, "group;", gx, gy, gw, gh, cell_id=group_id))
    shift_cells(direct_children, gx, gy)
    for cell in child_cells:
        ctx.add(cell)


def _emit_linear_bands(
    ctx: EmitterContext,
    elem: Element,
    matrix: Matrix,
    spec: ShapeSpec,
    gradient: GradientStyle,
    *,
    opacity: int,
    fill_opacity: int,
    filter_ref: str | None = None,
) -> None:
    """Approximate one linear multi-stop gradient using two-color gradient bands.

    Each band covers exactly one stop interval and carries a draw.io two-color gradient,
    so the result is mathematically exact rather than a staircase of solid slices.
    """
    stops = gradient["stops"]
    direction = gradient["direction"]
    vertical = direction in {"east", "west"}
    reverse = direction in {"west", "north"}
    # Physical gradient direction within each band (always flows left→right or top→bottom)
    band_dir = "east" if vertical else "south"

    for i in range(len(stops) - 1):
        left_stop = stops[i]
        right_stop = stops[i + 1]

        if reverse:
            # Reversed directions (west, north): stop offsets increase toward the physical start.
            phys_start = 1.0 - right_stop["offset"]
            phys_end = 1.0 - left_stop["offset"]
            fill_color = right_stop["color"]
            grad_color = left_stop["color"]
        else:
            phys_start = left_stop["offset"]
            phys_end = right_stop["offset"]
            fill_color = left_stop["color"]
            grad_color = right_stop["color"]

        if phys_end - phys_start <= 1e-6:
            continue

        # Extend non-last bands slightly to fill the sub-pixel anti-aliasing gap at the junction.
        phys_end_draw = min(phys_end + _BAND_OVERLAP, 1.0) if i < len(stops) - 2 else phys_end

        polygon = _band_polygon(spec, phys_start, phys_end_draw, vertical=vertical)
        if len(polygon) < 3:
            continue

        transformed = [apply_pt(matrix, px, py) for px, py in polygon]

        band_gradient: GradientStyle = {
            "color": fill_color,
            "color2": grad_color,
            "direction": band_dir,
            "kind": "linear",
            "stops": [
                {"offset": 0.0, "color": fill_color},
                {"offset": 1.0, "color": grad_color},
            ],
        }

        emit_polygon_stencil(
            ctx,
            elem,
            transformed,
            fill_color,
            band_gradient,
            "none",
            1.0,
            opacity,
            fill_opacity,
            100,
            filter_ref=filter_ref,
        )


def _emit_radial_layers(
    ctx: EmitterContext,
    elem: Element,
    matrix: Matrix,
    spec: ShapeSpec,
    gradient: GradientStyle,
    *,
    opacity: int,
    fill_opacity: int,
    filter_ref: str | None = None,
) -> None:
    """Approximate one radial multi-stop gradient using concentric shape layers."""
    steps = _radial_step_count(gradient, spec)
    for band_index in range(steps, 0, -1):
        ratio = band_index / steps
        offset = (band_index - 0.5) / steps
        color = _color_at_offset(gradient, offset)
        _emit_filled_shape(
            ctx,
            elem,
            matrix,
            spec.scaled(ratio),
            color=color,
            opacity=opacity,
            fill_opacity=fill_opacity,
            filter_ref=filter_ref,
        )


def _emit_filled_shape(
    ctx: EmitterContext,
    elem: Element,
    matrix: Matrix,
    spec: ShapeSpec,
    *,
    color: str,
    opacity: int,
    fill_opacity: int,
    filter_ref: str | None = None,
) -> None:
    """Emit one fill-only simple shape child."""
    if spec.width <= 0 or spec.height <= 0:
        return

    style = StyleBuilder()
    if spec.kind == "ellipse":
        box = ellipse_bounds(matrix, spec.cx, spec.cy, spec.width / 2, spec.height / 2)
        rotation = box.rotation_if_visible()
        style.add_flag("ellipse")
    else:
        box = rect_bounds(matrix, spec.x, spec.y, spec.width, spec.height)
        rotation = box.rotation_if_visible()
        if spec.rx > 0 or spec.ry > 0:
            shorter_side = min(spec.width, spec.height) if spec.width > 0 and spec.height > 0 else 1.0
            arc_pct = min(50, round(max(spec.rx, spec.ry) / shorter_side * 100))
            style.add("rounded", 1).add("arcSize", arc_pct)
        else:
            style.add("rounded", 0)
    rotation_style = f"{rotation:.2f}" if rotation is not None else None
    style.add("whiteSpace", "wrap").add("html", 1)
    style.add("fillColor", color).add("strokeColor", "none").add("strokeWidth", 1.0)
    style.add("opacity", opacity).add("fillOpacity", fill_opacity).add("strokeOpacity", 100)
    style.add("rotation", rotation_style, when=rotation_style is not None)
    add_metadata_styles(style, elem, ctx)
    add_filter_styles(style, ctx, elem, filter_ref, fallback_color=color)
    ctx.add(make_box_vertex(ctx, style.build(), box))


def _emit_shape_stroke_overlay(
    ctx: EmitterContext,
    elem: Element,
    matrix: Matrix,
    spec: ShapeSpec,
    *,
    stroke: str,
    stroke_width: float,
    opacity: int,
    stroke_opacity: int,
    dash: str,
    filter_ref: str | None = None,
) -> None:
    """Emit a fill-less stroke overlay so the approximated gradient keeps the original outline."""
    style = StyleBuilder()
    if spec.kind == "ellipse":
        box = ellipse_bounds(matrix, spec.cx, spec.cy, spec.width / 2, spec.height / 2)
        rotation = box.rotation_if_visible()
        style.add_flag("ellipse")
    else:
        box = rect_bounds(matrix, spec.x, spec.y, spec.width, spec.height)
        rotation = box.rotation_if_visible()
        if spec.rx > 0 or spec.ry > 0:
            shorter_side = min(spec.width, spec.height) if spec.width > 0 and spec.height > 0 else 1.0
            arc_pct = min(50, round(max(spec.rx, spec.ry) / shorter_side * 100))
            style.add("rounded", 1).add("arcSize", arc_pct)
        else:
            style.add("rounded", 0)
    rotation_style = f"{rotation:.2f}" if rotation is not None else None
    style.add("whiteSpace", "wrap").add("html", 1)
    style.add("fillColor", "none").add("strokeColor", stroke).add("strokeWidth", stroke_width)
    style.add("opacity", opacity).add("fillOpacity", 100).add("strokeOpacity", stroke_opacity)
    style.extend_raw(dash)
    style.add("rotation", rotation_style, when=rotation_style is not None)
    add_metadata_styles(style, elem, ctx)
    add_filter_styles(style, ctx, elem, filter_ref, fallback_color=stroke)
    ctx.add(make_box_vertex(ctx, style.build(), box))


def _radial_step_count(gradient: GradientStyle, spec: ShapeSpec) -> int:
    """Return the number of concentric rings for one radial gradient approximation.

    Ring count is adaptive: driven by the shape's radius so each ring stays below
    _RADIAL_TARGET_PX wide at normal zoom, while respecting a per-stop-interval
    minimum and a hard performance cap.
    """
    radius = max(spec.width, spec.height) / 2
    steps_from_size = max(1, round(radius / _RADIAL_TARGET_PX))
    steps_from_stops = (len(gradient["stops"]) - 1) * 4
    return min(_RADIAL_MAX_STEPS, max(_RADIAL_MIN_STEPS, steps_from_size, steps_from_stops))


def _band_polygon(spec: ShapeSpec, start: float, end: float, *, vertical: bool) -> list[Point2D]:
    """Return one band polygon in local shape coordinates."""
    if vertical:
        x0 = spec.x + spec.width * start
        x1 = spec.x + spec.width * end
        return _vertical_band_polygon(spec, x0, x1)
    y0 = spec.y + spec.height * start
    y1 = spec.y + spec.height * end
    return _horizontal_band_polygon(spec, y0, y1)


def _vertical_band_polygon(spec: ShapeSpec, x0: float, x1: float) -> list[Point2D]:
    """Return the polygon for a vertical band clipped to the current shape."""
    x0 = max(spec.x, min(spec.x + spec.width, x0))
    x1 = max(spec.x, min(spec.x + spec.width, x1))
    if x1 - x0 <= 1e-6:
        return []
    xs = _sample_axis(x0, x1)
    top = [(px, _shape_top(spec, px)) for px in xs]
    bottom = [(px, _shape_bottom(spec, px)) for px in reversed(xs)]
    return top + bottom


def _horizontal_band_polygon(spec: ShapeSpec, y0: float, y1: float) -> list[Point2D]:
    """Return the polygon for a horizontal band clipped to the current shape."""
    y0 = max(spec.y, min(spec.y + spec.height, y0))
    y1 = max(spec.y, min(spec.y + spec.height, y1))
    if y1 - y0 <= 1e-6:
        return []
    ys = _sample_axis(y0, y1)
    left = [(_shape_left(spec, py), py) for py in ys]
    right = [(_shape_right(spec, py), py) for py in reversed(ys)]
    return left + right


def _sample_axis(start: float, end: float) -> list[float]:
    """Return evenly spaced sample points across one interval, including its endpoints."""
    return [start + (end - start) * index / (_SAMPLES_PER_CURVE - 1) for index in range(_SAMPLES_PER_CURVE)]


def _shape_top(spec: ShapeSpec, px: float) -> float:
    """Return the top boundary of one simple shape at x=px."""
    if spec.kind == "ellipse":
        return spec.cy - (spec.height / 2) * _ellipse_term(spec, px)
    if spec.rx <= 0 or spec.ry <= 0:
        return spec.y
    left_limit = spec.x + spec.rx
    right_limit = spec.x + spec.width - spec.rx
    if px < left_limit:
        return _rounded_corner_y(spec.x + spec.rx, spec.y + spec.ry, spec.rx, spec.ry, px, upper=True)
    if px > right_limit:
        return _rounded_corner_y(spec.x + spec.width - spec.rx, spec.y + spec.ry, spec.rx, spec.ry, px, upper=True)
    return spec.y


def _shape_bottom(spec: ShapeSpec, px: float) -> float:
    """Return the bottom boundary of one simple shape at x=px."""
    if spec.kind == "ellipse":
        return spec.cy + (spec.height / 2) * _ellipse_term(spec, px)
    if spec.rx <= 0 or spec.ry <= 0:
        return spec.y + spec.height
    left_limit = spec.x + spec.rx
    right_limit = spec.x + spec.width - spec.rx
    if px < left_limit:
        return _rounded_corner_y(
            spec.x + spec.rx,
            spec.y + spec.height - spec.ry,
            spec.rx,
            spec.ry,
            px,
            upper=False,
        )
    if px > right_limit:
        return _rounded_corner_y(
            spec.x + spec.width - spec.rx,
            spec.y + spec.height - spec.ry,
            spec.rx,
            spec.ry,
            px,
            upper=False,
        )
    return spec.y + spec.height


def _shape_left(spec: ShapeSpec, py: float) -> float:
    """Return the left boundary of one simple shape at y=py."""
    if spec.kind == "ellipse":
        return spec.cx - (spec.width / 2) * _ellipse_term(spec, py, horizontal=False)
    if spec.rx <= 0 or spec.ry <= 0:
        return spec.x
    top_limit = spec.y + spec.ry
    bottom_limit = spec.y + spec.height - spec.ry
    if py < top_limit:
        return _rounded_corner_x(spec.x + spec.rx, spec.y + spec.ry, spec.rx, spec.ry, py, left_side=True)
    if py > bottom_limit:
        return _rounded_corner_x(
            spec.x + spec.rx,
            spec.y + spec.height - spec.ry,
            spec.rx,
            spec.ry,
            py,
            left_side=True,
        )
    return spec.x


def _shape_right(spec: ShapeSpec, py: float) -> float:
    """Return the right boundary of one simple shape at y=py."""
    if spec.kind == "ellipse":
        return spec.cx + (spec.width / 2) * _ellipse_term(spec, py, horizontal=False)
    if spec.rx <= 0 or spec.ry <= 0:
        return spec.x + spec.width
    top_limit = spec.y + spec.ry
    bottom_limit = spec.y + spec.height - spec.ry
    if py < top_limit:
        return _rounded_corner_x(
            spec.x + spec.width - spec.rx,
            spec.y + spec.ry,
            spec.rx,
            spec.ry,
            py,
            left_side=False,
        )
    if py > bottom_limit:
        return _rounded_corner_x(
            spec.x + spec.width - spec.rx,
            spec.y + spec.height - spec.ry,
            spec.rx,
            spec.ry,
            py,
            left_side=False,
        )
    return spec.x + spec.width


def _ellipse_term(spec: ShapeSpec, axis_value: float, *, horizontal: bool = True) -> float:
    """Return the normalized ellipse term used for local boundary reconstruction."""
    radius = spec.width / 2 if horizontal else spec.height / 2
    center = spec.cx if horizontal else spec.cy
    if radius <= 0:
        return 0.0
    normalized = (axis_value - center) / radius
    return math.sqrt(max(0.0, 1.0 - normalized * normalized))


def _rounded_corner_y(cx: float, cy: float, rx: float, ry: float, px: float, *, upper: bool) -> float:
    """Return the top or bottom y coordinate on one rounded rectangle corner arc."""
    if rx <= 0 or ry <= 0:
        return cy
    normalized = max(-1.0, min(1.0, (px - cx) / rx))
    delta = ry * math.sqrt(max(0.0, 1.0 - normalized * normalized))
    return cy - delta if upper else cy + delta


def _rounded_corner_x(cx: float, cy: float, rx: float, ry: float, py: float, *, left_side: bool) -> float:
    """Return the left or right x coordinate on one rounded rectangle corner arc."""
    if rx <= 0 or ry <= 0:
        return cx
    normalized = max(-1.0, min(1.0, (py - cy) / ry))
    delta = rx * math.sqrt(max(0.0, 1.0 - normalized * normalized))
    return cx - delta if left_side else cx + delta


def _color_at_offset(gradient: GradientStyle, offset: float) -> str:
    """Return the interpolated stop color for one normalized gradient offset."""
    stops = gradient["stops"]
    if not stops:
        return gradient["color"]
    if offset <= stops[0]["offset"]:
        return stops[0]["color"]
    if offset >= stops[-1]["offset"]:
        return stops[-1]["color"]

    for left, right in zip(stops, stops[1:]):
        if left["offset"] <= offset <= right["offset"]:
            span = right["offset"] - left["offset"]
            blend = 0.0 if span <= 1e-9 else (offset - left["offset"]) / span
            return _blend_hex(left["color"], right["color"], blend)
    return stops[-1]["color"]


def _blend_hex(left: str, right: str, blend: float) -> str:
    """Blend two `#rrggbb` colors linearly in RGB space."""
    blend = max(0.0, min(1.0, blend))
    left_rgb = _hex_to_rgb(left)
    right_rgb = _hex_to_rgb(right)
    mixed = tuple(round(lv + (rv - lv) * blend) for lv, rv in zip(left_rgb, right_rgb))
    return "#{:02x}{:02x}{:02x}".format(*mixed)


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    """Parse one normalized `#rrggbb` color string."""
    text = color.strip()
    if len(text) == 7 and text.startswith("#"):
        return int(text[1:3], 16), int(text[3:5], 16), int(text[5:7], 16)
    return 0, 0, 0


def emit_path_multi_stop_gradient_approximation(
    ctx: EmitterContext,
    elem: Element,
    commands: list,
    bbox: tuple[float, float, float, float],
    gradient: GradientStyle,
    *,
    stroke: str,
    stroke_width: float,
    opacity: int,
    fill_opacity: int,
    stroke_opacity: int,
    fill_rule: str = "nonzero",
    linecap: str = "flat",
    linejoin: str = "miter",
    dash: str = "",
    filter_ref: str | None = None,
) -> None:
    """Approximate a multi-stop linear gradient on an arbitrary closed path.

    Converts the path to a dense polygon (sampling Bézier curves), then clips
    each gradient band using Sutherland–Hodgman and emits it as a native
    draw.io two-color gradient stencil.  A stroke-only stencil is emitted last
    to restore the original outline above the filled bands.
    """
    polygon = commands_to_polygon(list(commands))
    if len(polygon) < 3:
        return

    bx, by, bw, bh = bbox

    group_id = ctx.next_id()
    child_cells: list[Cell] = []
    child_ctx = replace(ctx.with_parent(group_id), add_cell=child_cells.append)

    stops = gradient["stops"]
    direction = gradient["direction"]
    vertical = direction in {"east", "west"}
    reverse = direction in {"west", "north"}
    band_dir = "east" if vertical else "south"
    n = len(stops) - 1

    for i in range(n):
        left_stop = stops[i]
        right_stop = stops[i + 1]

        if reverse:
            phys_start = 1.0 - right_stop["offset"]
            phys_end = 1.0 - left_stop["offset"]
            fill_color = right_stop["color"]
            grad_color = left_stop["color"]
        else:
            phys_start = left_stop["offset"]
            phys_end = right_stop["offset"]
            fill_color = left_stop["color"]
            grad_color = right_stop["color"]

        if phys_end - phys_start <= 1e-6:
            continue

        phys_end_draw = min(phys_end + _BAND_OVERLAP, 1.0) if i < n - 1 else phys_end

        if vertical:
            lo = bx + bw * phys_start
            hi = bx + bw * phys_end_draw
        else:
            lo = by + bh * phys_start
            hi = by + bh * phys_end_draw

        clipped = clip_polygon_strip(polygon, lo, hi, vertical=vertical)
        if len(clipped) < 3:
            continue

        band_gradient: GradientStyle = {
            "color": fill_color,
            "color2": grad_color,
            "direction": band_dir,
            "kind": "linear",
            "stops": [
                {"offset": 0.0, "color": fill_color},
                {"offset": 1.0, "color": grad_color},
            ],
        }

        emit_polygon_stencil(
            child_ctx,
            elem,
            clipped,
            fill_color,
            band_gradient,
            "none",
            1.0,
            opacity,
            fill_opacity,
            100,
            filter_ref=filter_ref,
        )

    if stroke != "none" and stroke_width > 0:
        emit_stencil_commands(
            child_ctx,
            elem,
            commands,
            "none",
            None,
            stroke,
            stroke_width,
            opacity,
            100,
            stroke_opacity,
            dash,
            fill_rule,
            linecap,
            linejoin,
            filter_ref=filter_ref,
        )

    if not child_cells:
        return

    direct_children = [cell for cell in child_cells if cell.parent == group_id]
    gx, gy, gw, gh = group_bbox(direct_children)
    ctx.add(make_bounds_vertex(ctx, "group;", gx, gy, gw, gh, cell_id=group_id))
    shift_cells(direct_children, gx, gy)
    for cell in child_cells:
        ctx.add(cell)
