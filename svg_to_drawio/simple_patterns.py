"""Helpers for expanding very simple SVG patterns into editable draw.io geometry."""

from __future__ import annotations

import re
from dataclasses import replace
from xml.etree.ElementTree import Element

from .cell_factory import make_bounds_vertex
from .drawio_model import Cell, group_bbox, shift_cells
from .elements.shapes import emit_circle, emit_line, emit_rect
from .emitter_context import EmitterContext
from .rendering_options import normalize_filter_ref
from .transforms import Matrix
from .utils import parse_length, parse_style_attr, strip_ns

_PATTERN_MAX_CHILDREN = 240
_EPSILON = 1e-6
_SUPPORTED_PATTERN_TAGS: frozenset[str] = frozenset({"rect", "line", "circle"})
_IGNORED_PATTERN_TAGS: frozenset[str] = frozenset({"title", "desc", "metadata"})


def emit_simple_pattern_fill(
    ctx: EmitterContext,
    elem: Element,
    matrix: Matrix,
    css: dict[str, str],
) -> bool:
    """Expand a supported dot/stripe/grid pattern into editable native geometry."""
    if strip_ns(elem.tag) != "rect":
        return False
    if normalize_filter_ref(css.get("filter") or elem.get("filter")) is not None:
        return False
    if (css.get("clip-path") or elem.get("clip-path") or "").strip().lower() not in {"", "none"}:
        return False
    if (css.get("mask") or elem.get("mask") or "").strip().lower() not in {"", "none"}:
        return False

    fill_value = css.get("fill") or elem.get("fill") or ""
    pattern_elem = _pattern_element(ctx, fill_value)
    if pattern_elem is None:
        return False
    if (pattern_elem.get("patternUnits") or "objectBoundingBox").strip() != "userSpaceOnUse":
        return False
    if (pattern_elem.get("patternContentUnits") or "userSpaceOnUse").strip() != "userSpaceOnUse":
        return False

    width = parse_length(pattern_elem.get("width"))
    height = parse_length(pattern_elem.get("height"))
    if width <= 0 or height <= 0:
        return False

    direct_pattern_tags = [strip_ns(child.tag) for child in pattern_elem]
    if any(tag not in _SUPPORTED_PATTERN_TAGS and tag not in _IGNORED_PATTERN_TAGS for tag in direct_pattern_tags):
        return False

    pattern_children = [child for child in pattern_elem if strip_ns(child.tag) in _SUPPORTED_PATTERN_TAGS]
    if not pattern_children:
        return False

    background = _background_rect(pattern_children, width, height)
    motif_children = [child for child in pattern_children if child is not background]
    if not motif_children:
        return False

    if not (_is_simple_line_pattern(motif_children) or _is_simple_dot_pattern(motif_children)):
        return False

    target_x = parse_length(elem.get("x"))
    target_y = parse_length(elem.get("y"))
    target_width = parse_length(elem.get("width"))
    target_height = parse_length(elem.get("height"))
    if target_width <= 0 or target_height <= 0:
        return False

    child_cells: list[Cell] = []
    group_id = ctx.next_id()
    child_ctx = replace(ctx.with_parent(group_id), add_cell=child_cells.append)

    base_css = dict(css)
    if background is not None:
        background_css = dict(base_css)
        background_css["fill"] = _child_attr(background, "fill", default=background_css.get("fill", "none"))
        background_css["stroke"] = base_css.get("stroke") or elem.get("stroke") or "none"
        background_css["stroke-width"] = base_css.get("stroke-width") or elem.get("stroke-width") or "1"
        emit_rect(child_ctx, elem, matrix, background_css)

    emitted_pattern_cells = _emit_pattern_tiles(
        child_ctx,
        elem,
        matrix,
        motif_children,
        base_css,
        target_x,
        target_y,
        target_width,
        target_height,
        tile_width=width,
        tile_height=height,
    )
    if emitted_pattern_cells <= 0:
        return False

    _emit_pattern_boundary_lines(
        child_ctx,
        elem,
        matrix,
        motif_children,
        base_css,
        target_x,
        target_y,
        target_width,
        target_height,
        tile_width=width,
        tile_height=height,
    )

    direct_children = [cell for cell in child_cells if cell.parent == group_id]
    if not direct_children:
        return False

    gx, gy, gw, gh = group_bbox(direct_children)

    ctx.add(make_bounds_vertex(ctx, "group;", gx, gy, gw, gh, cell_id=group_id))
    shift_cells(direct_children, gx, gy)
    for cell in child_cells:
        ctx.add(cell)

    ctx.report.add_issue(
        "pattern-simplified-native",
        "warning",
        "A simple repeating SVG pattern was expanded into editable draw.io geometry.",
        element_tag=strip_ns(elem.tag),
        element_id=elem.get("id"),
    )
    return True


def _emit_pattern_tiles(
    ctx: EmitterContext,
    elem: Element,
    matrix: Matrix,
    motif_children: list[Element],
    base_css: dict[str, str],
    target_x: float,
    target_y: float,
    target_width: float,
    target_height: float,
    *,
    tile_width: float,
    tile_height: float,
) -> int:
    """Emit the repeated motif children across a rectangular target area."""
    emitted = 0
    x_repeat_count = int((target_width + _EPSILON) // tile_width) + 2
    y_repeat_count = int((target_height + _EPSILON) // tile_height) + 2
    if len(motif_children) * x_repeat_count * y_repeat_count > _PATTERN_MAX_CHILDREN:
        return 0

    tile_origin_x = target_x
    tile_origin_y = target_y
    for y_index in range(y_repeat_count):
        offset_y = tile_origin_y + y_index * tile_height
        for x_index in range(x_repeat_count):
            offset_x = tile_origin_x + x_index * tile_width
            for child in motif_children:
                tag = strip_ns(child.tag)
                if tag == "line":
                    line = _translated_line(child, offset_x, offset_y)
                    if _line_outside_rect(line, target_x, target_y, target_width, target_height):
                        continue
                    emit_line(ctx, line, matrix, _pattern_child_css(base_css, child))
                    emitted += 1
                elif tag == "circle":
                    circle = _translated_circle(child, offset_x, offset_y)
                    if _circle_outside_rect(circle, target_x, target_y, target_width, target_height):
                        continue
                    emit_circle(ctx, circle, matrix, _pattern_child_css(base_css, child))
                    emitted += 1
    return emitted


def _emit_pattern_boundary_lines(
    ctx: EmitterContext,
    elem: Element,
    matrix: Matrix,
    motif_children: list[Element],
    base_css: dict[str, str],
    target_x: float,
    target_y: float,
    target_width: float,
    target_height: float,
    *,
    tile_width: float,
    tile_height: float,
) -> None:
    """Close simple grid-like patterns cleanly at the target rectangle edges."""
    if not _is_simple_line_pattern(motif_children):
        return

    has_horizontal = any(
        abs(parse_length(child.get("y1")) - parse_length(child.get("y2"))) <= _EPSILON for child in motif_children
    )
    has_vertical = any(
        abs(parse_length(child.get("x1")) - parse_length(child.get("x2"))) <= _EPSILON for child in motif_children
    )
    width_remainder = target_width % tile_width
    height_remainder = target_height % tile_height

    if has_vertical and width_remainder > _EPSILON:
        vertical = next(
            child
            for child in motif_children
            if abs(parse_length(child.get("x1")) - parse_length(child.get("x2"))) <= _EPSILON
        )
        emit_line(
            ctx,
            Element(
                "line",
                {
                    **vertical.attrib,
                    "x1": f"{target_x + target_width:.6f}",
                    "x2": f"{target_x + target_width:.6f}",
                    "y1": f"{target_y:.6f}",
                    "y2": f"{target_y + target_height:.6f}",
                },
            ),
            matrix,
            _pattern_child_css(base_css, vertical),
        )

    if has_horizontal and height_remainder > _EPSILON:
        horizontal = next(
            child
            for child in motif_children
            if abs(parse_length(child.get("y1")) - parse_length(child.get("y2"))) <= _EPSILON
        )
        emit_line(
            ctx,
            Element(
                "line",
                {
                    **horizontal.attrib,
                    "x1": f"{target_x:.6f}",
                    "x2": f"{target_x + target_width:.6f}",
                    "y1": f"{target_y + target_height:.6f}",
                    "y2": f"{target_y + target_height:.6f}",
                },
            ),
            matrix,
            _pattern_child_css(base_css, horizontal),
        )


def _pattern_element(ctx: EmitterContext, fill_value: str) -> Element | None:
    """Return the referenced pattern element for one `fill="url(#...)"` value."""
    match = re.match(r"url\(#([^)]+)\)", fill_value)
    if not match:
        return None
    pattern_elem = ctx.defs.get_element(match.group(1))
    if pattern_elem is None or strip_ns(pattern_elem.tag) != "pattern":
        return None
    return pattern_elem


def _background_rect(children: list[Element], width: float, height: float) -> Element | None:
    """Return the tile-sized background rectangle when one is present."""
    for child in children:
        if strip_ns(child.tag) != "rect":
            continue
        x = parse_length(child.get("x"))
        y = parse_length(child.get("y"))
        child_width = parse_length(child.get("width"))
        child_height = parse_length(child.get("height"))
        if (
            abs(x) <= _EPSILON
            and abs(y) <= _EPSILON
            and child_width >= width - _EPSILON
            and child_height >= height - _EPSILON
        ):
            return child
    return None


def _is_simple_line_pattern(children: list[Element]) -> bool:
    """Return whether the motif is composed of horizontal and/or vertical lines."""
    if not children or any(strip_ns(child.tag) != "line" for child in children):
        return False
    return all(
        abs(parse_length(child.get("x1")) - parse_length(child.get("x2"))) <= _EPSILON
        or abs(parse_length(child.get("y1")) - parse_length(child.get("y2"))) <= _EPSILON
        for child in children
    )


def _is_simple_dot_pattern(children: list[Element]) -> bool:
    """Return whether the motif is composed only of circles."""
    return bool(children) and all(strip_ns(child.tag) == "circle" for child in children)


def _pattern_child_css(base_css: dict[str, str], child: Element) -> dict[str, str]:
    """Build the effective CSS for one repeated pattern child."""
    css = dict(base_css)
    css.update(parse_style_attr(child.get("style", "")))
    for name in (
        "fill",
        "stroke",
        "stroke-width",
        "fill-opacity",
        "stroke-opacity",
        "opacity",
        "stroke-linecap",
        "stroke-linejoin",
        "stroke-dasharray",
    ):
        value = child.get(name)
        if value is not None:
            css[name] = value
    css.pop("filter", None)
    return css


def _translated_line(child: Element, offset_x: float, offset_y: float) -> Element:
    """Return one line child translated by a tile offset."""
    return Element(
        "line",
        {
            **child.attrib,
            "x1": f"{offset_x + parse_length(child.get('x1')):.6f}",
            "y1": f"{offset_y + parse_length(child.get('y1')):.6f}",
            "x2": f"{offset_x + parse_length(child.get('x2')):.6f}",
            "y2": f"{offset_y + parse_length(child.get('y2')):.6f}",
        },
    )


def _translated_circle(child: Element, offset_x: float, offset_y: float) -> Element:
    """Return one circle child translated by a tile offset."""
    return Element(
        "circle",
        {
            **child.attrib,
            "cx": f"{offset_x + parse_length(child.get('cx')):.6f}",
            "cy": f"{offset_y + parse_length(child.get('cy')):.6f}",
        },
    )


def _line_outside_rect(
    line: Element,
    x: float,
    y: float,
    width: float,
    height: float,
) -> bool:
    """Return whether the translated line sits completely outside the target rectangle."""
    x1 = parse_length(line.get("x1"))
    y1 = parse_length(line.get("y1"))
    x2 = parse_length(line.get("x2"))
    y2 = parse_length(line.get("y2"))
    if x1 < x - _EPSILON or x2 < x - _EPSILON or x1 > x + width + _EPSILON or x2 > x + width + _EPSILON:
        return True
    if y1 < y - _EPSILON or y2 < y - _EPSILON or y1 > y + height + _EPSILON or y2 > y + height + _EPSILON:
        return True
    return False


def _circle_outside_rect(
    circle: Element,
    x: float,
    y: float,
    width: float,
    height: float,
) -> bool:
    """Return whether the translated circle sits completely outside the target rectangle."""
    cx = parse_length(circle.get("cx"))
    cy = parse_length(circle.get("cy"))
    radius = parse_length(circle.get("r"))
    return (
        cx + radius < x - _EPSILON
        or cy + radius < y - _EPSILON
        or cx - radius > x + width + _EPSILON
        or cy - radius > y + height + _EPSILON
    )


def _child_attr(child: Element, name: str, *, default: str) -> str:
    """Return one child attribute, falling back to a parsed inline style value."""
    styles = parse_style_attr(child.get("style", ""))
    return child.get(name) or styles.get(name) or default
