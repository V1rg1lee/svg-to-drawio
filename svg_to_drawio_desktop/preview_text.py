"""Advanced text rewrites that make the desktop SVG preview closer to engine output."""

from __future__ import annotations

from dataclasses import dataclass
from xml.etree.ElementTree import Element

from svg_to_drawio.defs import DefsIndex
from svg_to_drawio.styles import VisualStyle, get_visual
from svg_to_drawio.text_metrics import measure_text
from svg_to_drawio.text_path import (
    normal_vector,
    parse_start_offset,
    point_and_angle_at_distance,
    polyline_length,
    sample_path_polyline,
)
from svg_to_drawio.transforms import IDENTITY
from svg_to_drawio.utils import parse_length, strip_ns

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
PREVIEW_TEXT_METRICS_POLICY = "system"
_TEXT_CONTAINER_ATTRS = ("transform", "filter", "clip-path", "mask")


@dataclass(frozen=True)
class PreviewTextRun:
    """One preview textPath run plus its local position offsets."""

    content: str
    visual: VisualStyle
    dx: float = 0.0
    dy: float = 0.0


def _format_number(value: float) -> str:
    """Serialize a float compactly for SVG output."""
    return f"{value:.6g}"


def _font_kwargs(visual: VisualStyle) -> dict[str, str]:
    """Return normalized text metric kwargs for one visual style."""
    return {
        "font_weight": str(visual.get("font_weight", "normal") or "normal"),
        "font_style": str(visual.get("font_style_v", "normal") or "normal"),
    }


def _letter_spacing_px(visual: VisualStyle) -> float:
    """Return the additional spacing requested between adjacent glyphs."""
    letter_spacing = str(visual.get("letter_spacing") or "normal").strip().lower()
    if letter_spacing in {"", "normal"}:
        return 0.0
    return parse_length(letter_spacing, 0.0)


def _glyph_run_layout(
    content: str,
    visual: VisualStyle,
) -> tuple[list[str], list[float], float, float]:
    """Return per-glyph widths, effective gap spacing, and total advance."""
    font_size = max(visual["font_size"], 6.0)
    font_family = visual.get("font_family") or "Helvetica"
    glyphs = list(content)
    if not glyphs:
        return [], [], 0.0, 0.0

    glyph_widths = [
        measure_text(
            glyph if glyph.strip() else " ",
            font_size,
            font_family,
            policy=PREVIEW_TEXT_METRICS_POLICY,
            **_font_kwargs(visual),
        )[0]
        for glyph in glyphs
    ]
    gap_count = max(len(glyphs) - 1, 0)
    gap_spacing = _letter_spacing_px(visual)
    target_length = visual.get("text_length")
    length_adjust = str(visual.get("length_adjust") or "spacing").strip().lower()

    if target_length is not None and gap_count > 0:
        if length_adjust == "spacingandglyphs":
            current_length = sum(glyph_widths) + gap_spacing * gap_count
            if current_length > 1e-6:
                scale = target_length / current_length
                glyph_widths = [max(width * scale, font_size * 0.1) for width in glyph_widths]
                gap_spacing *= scale
        else:
            gap_spacing += (target_length - sum(glyph_widths) - gap_spacing * gap_count) / gap_count
    elif target_length is not None and gap_count == 0:
        glyph_widths = [max(target_length, glyph_widths[0])]

    total_width = sum(glyph_widths) + gap_spacing * gap_count
    return glyphs, glyph_widths, gap_spacing, total_width


def _baseline_shift_distance(visual: VisualStyle) -> float:
    """Return the signed preview offset along the positive-y path normal."""
    font_size = max(visual["font_size"], 6.0)
    baseline_shift = str(visual.get("baseline_shift") or "0").strip().lower()
    if baseline_shift == "super":
        return -font_size * 0.35
    if baseline_shift == "sub":
        return font_size * 0.35
    if baseline_shift in {"", "0", "baseline"}:
        return 0.0
    return -parse_length(baseline_shift, 0.0)


def _text_anchor(visual: VisualStyle) -> str:
    """Return the SVG text-anchor value used by the preview glyph nodes."""
    anchor = str(visual.get("text_anchor") or "start").strip().lower()
    return anchor if anchor in {"start", "middle", "end"} else "start"


def _combined_text_opacity(visual: VisualStyle) -> float:
    """Return the effective text opacity after global and fill alpha are combined."""
    return float(visual["opacity"]) * float(visual["text_opacity"])


def _style_text_element(node: Element, visual: VisualStyle, *, anchor: str) -> None:
    """Apply one resolved text style to a preview glyph node."""
    node.set("text-anchor", anchor)
    node.set("fill", visual["text_fill"] or "#000000")
    node.set("font-size", _format_number(max(visual["font_size"], 6.0)))
    node.set("font-family", visual.get("font_family") or "Helvetica")
    node.set("font-weight", str(visual.get("font_weight") or "normal"))
    node.set("font-style", str(visual.get("font_style_v") or "normal"))
    text_decoration = str(visual.get("text_decoration") or "none")
    if text_decoration and text_decoration != "none":
        node.set("text-decoration", text_decoration)
    opacity = _combined_text_opacity(visual)
    if abs(opacity - 1.0) > 1e-6:
        node.set("opacity", _format_number(opacity))


def _make_group(elem: Element) -> Element:
    """Create one replacement preview group for a rewritten text element."""
    group = Element(f"{{{SVG_NS}}}g")
    for attr_name in _TEXT_CONTAINER_ATTRS:
        value = elem.get(attr_name)
        if value:
            group.set(attr_name, value)
    return group


def _collect_text_content(elem: Element) -> str:
    """Collect one text element's visible content while trimming formatting whitespace."""
    return "".join(elem.itertext()).strip()


def _first_text_path_child(elem: Element) -> Element | None:
    """Return the first nested textPath child if present."""
    return next((child for child in elem if strip_ns(child.tag) == "textPath"), None)


def _extend_text_path_runs(
    runs: list[PreviewTextRun],
    node: Element,
    node_visual: VisualStyle,
    *,
    leading_dx: float = 0.0,
    leading_dy: float = 0.0,
) -> None:
    """Flatten one textPath subtree into styled runs with local dx/dy offsets."""
    content = node.text or ""
    if content or abs(leading_dx) > 1e-6 or abs(leading_dy) > 1e-6:
        runs.append(PreviewTextRun(content, node_visual, dx=leading_dx, dy=leading_dy))

    for child in node:
        if strip_ns(child.tag) != "tspan":
            continue
        child_visual = get_visual(child, None)
        _extend_text_path_runs(
            runs,
            child,
            child_visual,
            leading_dx=parse_length(child.get("dx"), 0.0),
            leading_dy=parse_length(child.get("dy"), 0.0),
        )
        if child.tail:
            runs.append(PreviewTextRun(child.tail, node_visual))


def _collect_text_path_runs(text_path: Element, visual: VisualStyle) -> list[PreviewTextRun]:
    """Collect all styled runs from one inlined textPath subtree."""
    runs: list[PreviewTextRun] = []
    _extend_text_path_runs(runs, text_path, visual)
    return runs


def _rewrite_positioned_glyph_text(elem: Element) -> Element | None:
    """Rewrite one textLength or letter-spacing text node into positioned glyphs."""
    if any(strip_ns(child.tag) == "tspan" for child in elem):
        return None

    visual = get_visual(elem, None)
    if abs(_letter_spacing_px(visual)) <= 1e-6 and visual.get("text_length") is None:
        return None

    content = _collect_text_content(elem)
    if not content:
        return None

    glyphs, glyph_widths, gap_spacing, total_width = _glyph_run_layout(content, visual)
    if not glyphs:
        return None

    x0 = parse_length(elem.get("x"))
    y0 = parse_length(elem.get("y"))
    anchor = _text_anchor(visual)
    start_x = x0 - (total_width / 2.0 if anchor == "middle" else total_width if anchor == "end" else 0.0)

    group = _make_group(elem)
    cursor_x = start_x
    emitted = False

    for index, (glyph, glyph_width) in enumerate(zip(glyphs, glyph_widths, strict=True)):
        if glyph.strip():
            glyph_elem = Element(f"{{{SVG_NS}}}text")
            glyph_elem.text = glyph
            glyph_elem.set("x", _format_number(cursor_x + glyph_width / 2.0))
            glyph_elem.set("y", _format_number(y0))
            _style_text_element(glyph_elem, visual, anchor="middle")
            group.append(glyph_elem)
            emitted = True
        cursor_x += glyph_width
        if index < len(glyphs) - 1:
            cursor_x += gap_spacing

    return group if emitted else None


def _rewrite_text_path(elem: Element, defs: DefsIndex) -> Element | None:
    """Rewrite one textPath element into rotated positioned glyphs."""
    text_path = _first_text_path_child(elem)
    if text_path is None:
        return None

    href = text_path.get("href") or text_path.get(f"{{{XLINK_NS}}}href") or ""
    if not href.startswith("#"):
        return None

    path_elem = defs.get_element(href[1:])
    if path_elem is None or strip_ns(path_elem.tag) != "path":
        return None

    path_data = path_elem.get("d")
    if not path_data:
        return None

    path_matrix = defs.get_element_transform(href[1:]) or IDENTITY[:]
    polyline = sample_path_polyline(
        path_data,
        point_transform=lambda px, py: (
            path_matrix[0] * px + path_matrix[2] * py + path_matrix[4],
            path_matrix[1] * px + path_matrix[3] * py + path_matrix[5],
        ),
        curve_steps=80,
    )
    total_path_length = polyline_length(polyline)
    if len(polyline) < 2 or total_path_length <= 1e-6:
        return None

    visual = get_visual(elem, None)
    runs = _collect_text_path_runs(text_path, visual)
    run_layouts: list[tuple[PreviewTextRun, list[str], list[float], float, float]] = []
    total_advance = 0.0
    emitted_content = False

    for run in runs:
        glyphs, glyph_widths, gap_spacing, total_width = _glyph_run_layout(run.content, run.visual)
        emitted_content = emitted_content or any(glyph.strip() for glyph in glyphs)
        run_layouts.append((run, glyphs, glyph_widths, gap_spacing, total_width))
        total_advance += run.dx + total_width

    if not emitted_content:
        return None

    advance_scale = 1.0
    if total_advance > total_path_length and total_advance > 1e-6:
        advance_scale = total_path_length / total_advance
        total_advance = total_path_length

    start_distance = parse_start_offset(text_path.get("startOffset"), total_path_length)
    anchor = _text_anchor(visual)
    if anchor == "middle":
        start_distance -= total_advance / 2.0
    elif anchor == "end":
        start_distance -= total_advance

    group = _make_group(elem)
    cursor_distance = 0.0
    emitted = False

    for run, glyphs, glyph_widths, gap_spacing, _total_width in run_layouts:
        cursor_distance += run.dx * advance_scale
        normal_offset = run.dy + _baseline_shift_distance(run.visual)

        for index, (glyph, glyph_width) in enumerate(zip(glyphs, glyph_widths, strict=True)):
            path_glyph_width = glyph_width * advance_scale
            center_distance = start_distance + cursor_distance + path_glyph_width / 2.0
            path_position = point_and_angle_at_distance(polyline, center_distance)
            if glyph.strip() and path_position is not None:
                normal_x, normal_y = normal_vector(path_position.angle_degrees)
                baseline_x = path_position.x + normal_x * normal_offset
                baseline_y = path_position.y + normal_y * normal_offset
                glyph_elem = Element(f"{{{SVG_NS}}}text")
                glyph_elem.text = glyph
                glyph_elem.set("x", _format_number(baseline_x))
                glyph_elem.set("y", _format_number(baseline_y))
                glyph_elem.set(
                    "transform",
                    (
                        f"rotate({_format_number(path_position.angle_degrees)} "
                        f"{_format_number(baseline_x)} {_format_number(baseline_y)})"
                    ),
                )
                _style_text_element(glyph_elem, run.visual, anchor="middle")
                group.append(glyph_elem)
                emitted = True
            cursor_distance += path_glyph_width
            if index < len(glyphs) - 1:
                cursor_distance += gap_spacing * advance_scale

    return group if emitted else None


def _rewrite_text_element(elem: Element, defs: DefsIndex) -> Element | None:
    """Return a preview-safe replacement for one advanced text element if needed."""
    replacement = _rewrite_text_path(elem, defs)
    if replacement is not None:
        return replacement
    return _rewrite_positioned_glyph_text(elem)


def rewrite_advanced_preview_text(root: Element) -> bool:
    """Rewrite advanced SVG text features into simpler preview-friendly glyph nodes."""
    defs = DefsIndex()
    defs.index(root)
    changed = False

    def walk(parent: Element) -> None:
        nonlocal changed
        for child in list(parent):
            walk(child)

        children = list(parent)
        for index, child in enumerate(children):
            if strip_ns(child.tag) != "text":
                continue
            replacement = _rewrite_text_element(child, defs)
            if replacement is None:
                continue
            parent.remove(child)
            parent.insert(index, replacement)
            changed = True

    walk(root)
    return changed
