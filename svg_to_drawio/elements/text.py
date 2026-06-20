"""Emitters for SVG text elements."""

from __future__ import annotations

from dataclasses import dataclass, replace
from xml.etree.ElementTree import Element

from ..cell_factory import make_bounds_vertex
from ..compatibility import note_text_backend
from ..drawio_model import Cell, group_bbox, shift_cells
from ..emitter_context import EmitterContext
from ..issue_codes import (
    DOMINANT_BASELINE_APPROXIMATED,
    LETTER_SPACING_APPROXIMATED,
    TEXT_LENGTH_APPROXIMATED,
    TEXT_PATH_APPROXIMATED,
)
from ..style_builder import StyleBuilder
from ..styles import VisualStyle, font_style_flag, get_visual, opacity_pct
from ..text_metrics import measure_text, measure_text_detailed
from ..text_path import (
    normal_vector,
    parse_start_offset,
    point_and_angle_at_distance,
    polyline_length,
    sample_path_polyline,
)
from ..transforms import Matrix, apply_pt
from ..utils import parse_float, parse_length, parse_style_attr, strip_ns
from .style_support import add_filter_styles, add_metadata_styles

# Tspan attributes that require separate cell rendering.
_TSPAN_STYLE_ATTRS: tuple[str, ...] = (
    "x",
    "y",
    "dy",
    "dx",
    "fill",
    "font-size",
    "font-weight",
    "font-style",
    "font-family",
    "text-decoration",
    "text-anchor",
    "style",
)


@dataclass(frozen=True)
class TextPathRun:
    """One styled textPath run plus any leading local positioning adjustments."""

    content: str
    visual: VisualStyle
    dx: float = 0.0
    dy: float = 0.0


def _has_text_path(elem: Element) -> bool:
    """Return whether the text element contains a `<textPath>` child."""
    return any(strip_ns(child.tag) == "textPath" for child in elem)


def _first_text_path_child(elem: Element) -> Element | None:
    """Return the first `<textPath>` child of a text element, if present."""
    return next((child for child in elem if strip_ns(child.tag) == "textPath"), None)


def _font_kwargs(visual: VisualStyle) -> dict[str, str]:
    """Return the normalized measurement kwargs for one text style."""
    return {
        "font_weight": str(visual.get("font_weight", "normal") or "normal"),
        "font_style": str(visual.get("font_style_v", "normal") or "normal"),
    }


def _visual_to_css(visual: VisualStyle) -> dict[str, str]:
    """Rebuild the inheritable CSS subset represented by a resolved visual style."""
    css: dict[str, str] = {
        "fill": visual["text_fill"] or "#000000",
        "font-size": str(visual["font_size"]),
        "font-family": visual.get("font_family") or "Helvetica",
        "font-weight": str(visual.get("font_weight") or "normal"),
        "font-style": str(visual.get("font_style_v") or "normal"),
        "text-anchor": str(visual.get("text_anchor") or "start"),
        "text-decoration": str(visual.get("text_decoration") or "none"),
        "baseline-shift": str(visual.get("baseline_shift") or "0"),
        "dominant-baseline": str(visual.get("dominant_baseline") or "alphabetic"),
        "letter-spacing": str(visual.get("letter_spacing") or "normal"),
    }
    if visual.get("text_length") is not None:
        css["textLength"] = str(visual["text_length"])
    if visual.get("length_adjust"):
        css["lengthAdjust"] = str(visual["length_adjust"])
    return css


def _baseline_offset(font_size: float, est_height: float, visual: VisualStyle) -> float:
    """Return the top-left offset needed to align the SVG text baseline."""
    baseline_shift = str(visual.get("baseline_shift") or "0").strip().lower()
    if baseline_shift == "super":
        baseline_shift_px = font_size * 0.35
    elif baseline_shift == "sub":
        baseline_shift_px = -font_size * 0.35
    elif baseline_shift in ("0", "", "baseline"):
        baseline_shift_px = 0.0
    else:
        baseline_shift_px = parse_length(baseline_shift, 0.0)

    dominant_baseline = str(visual.get("dominant_baseline") or "alphabetic").strip().lower()
    if dominant_baseline in {"middle", "central"}:
        dominant_offset = est_height * 0.50
    elif dominant_baseline in {"text-before-edge", "before-edge", "hanging"}:
        dominant_offset = est_height * 0.18
    elif dominant_baseline in {"text-after-edge", "after-edge", "ideographic"}:
        dominant_offset = est_height * 0.95
    else:
        dominant_offset = max(font_size * 0.85, est_height * 0.60)
    return dominant_offset + baseline_shift_px


def _path_center_offset(font_size: float, visual: VisualStyle) -> float:
    """Return the path-normal offset from the SVG baseline to the glyph cell center.

    For regular text cells we can use the measured draw.io box height directly. For
    individually positioned `textPath` glyphs, using the full measured box height makes
    the baseline sit too close to the vertical center of the cell, so the source path
    visually crosses the letters. A synthetic one-em reference height keeps the editable
    glyph boxes noticeably above the path while still respecting dominant-baseline and
    baseline-shift adjustments.
    """
    reference_height = max(font_size, 1.0)
    return _baseline_offset(font_size, reference_height, visual) - reference_height / 2.0


def _letter_spacing_px(visual: VisualStyle) -> float:
    """Return the requested extra spacing between adjacent glyphs."""
    letter_spacing = str(visual.get("letter_spacing") or "normal").strip().lower()
    if letter_spacing in {"", "normal"}:
        return 0.0
    return parse_length(letter_spacing, 0.0)


def _glyph_run_layout(
    content: str,
    visual: VisualStyle,
    metrics_policy: str,
) -> tuple[list[str], list[float], float, float, str]:
    """Return glyph widths, gap spacing, total advance, and the measurement backend."""
    font_size = max(visual["font_size"], 6)
    font_family = visual.get("font_family") or "Helvetica"
    font_kwargs = _font_kwargs(visual)
    glyphs = list(content)

    _, _, backend = measure_text_detailed(
        content,
        font_size,
        font_family,
        policy=metrics_policy,
        **font_kwargs,
    )
    if not glyphs:
        return [], [], 0.0, 0.0, backend

    glyph_widths = [
        measure_text(glyph if glyph.strip() else " ", font_size, font_family, policy=metrics_policy, **font_kwargs)[0]
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
    return glyphs, glyph_widths, gap_spacing, total_width, backend


def _extend_text_path_runs(
    runs: list[TextPathRun],
    node: Element,
    node_visual: VisualStyle,
    node_css: dict[str, str] | None,
    ctx: EmitterContext,
    *,
    leading_dx: float = 0.0,
    leading_dy: float = 0.0,
) -> None:
    """Flatten one `<textPath>` or nested `<tspan>` tree into styled runs."""
    content = node.text or ""
    if content or abs(leading_dx) > 1e-6 or abs(leading_dy) > 1e-6:
        runs.append(TextPathRun(content, node_visual, dx=leading_dx, dy=leading_dy))

    current_css = node_css or _visual_to_css(node_visual)
    for child in node:
        if strip_ns(child.tag) != "tspan":
            continue
        child_visual = _tspan_visual(child, current_css, ctx)
        _extend_text_path_runs(
            runs,
            child,
            child_visual,
            _visual_to_css(child_visual),
            ctx,
            leading_dx=parse_length(child.get("dx"), 0.0),
            leading_dy=parse_length(child.get("dy"), 0.0),
        )
        if child.tail:
            runs.append(TextPathRun(child.tail, node_visual))


def _collect_text_path_runs(
    text_path: Element,
    visual: VisualStyle,
    css: dict[str, str] | None,
    ctx: EmitterContext,
) -> list[TextPathRun]:
    """Collect styled runs from a `<textPath>` subtree while preserving spacing."""
    runs: list[TextPathRun] = []
    _extend_text_path_runs(runs, text_path, visual, css, ctx)
    return runs


def _should_emit_positioned_glyphs(content: str, visual: VisualStyle) -> bool:
    """Return whether this run needs manual glyph positioning for better fidelity."""
    return "\n" not in content and (abs(_letter_spacing_px(visual)) > 1e-6 or visual.get("text_length") is not None)


def _run_advance(content: str, visual: VisualStyle, metrics_policy: str) -> float:
    """Return the horizontal SVG-space advance of one text run."""
    font_size = max(visual["font_size"], 6)
    font_family = visual.get("font_family") or "Helvetica"
    font_kwargs = _font_kwargs(visual)

    if not _should_emit_positioned_glyphs(content, visual):
        advance, _ = measure_text(content, font_size, font_family, policy=metrics_policy, **font_kwargs)
        return advance

    _, _, _, total_width, _ = _glyph_run_layout(content, visual, metrics_policy)
    return total_width


def _emit_text_cell(
    ctx: EmitterContext,
    elem: Element,
    matrix: Matrix,
    visual: VisualStyle,
    x0: float,
    y0: float,
    content: str,
    *,
    record_backend: bool = True,
    minimum_width: float = 20.0,
    width_override: float | None = None,
    align_override: str | None = None,
    rotation_degrees: float | None = None,
    placement: str = "baseline",
) -> None:
    """Emit one draw.io text cell."""
    font_color = visual["text_fill"] or "#000000"
    font_size = max(visual["font_size"], 6)
    font_family = visual.get("font_family") or "Helvetica"
    metrics_policy = ctx.rendering_options.text_metrics_policy
    opacity = opacity_pct(visual["opacity"] * visual["text_opacity"])
    align = align_override or {"start": "left", "middle": "center", "end": "right"}.get(visual["text_anchor"], "left")
    font_style = font_style_flag(visual)

    x, y = apply_pt(matrix, x0, y0)
    est_width, est_height, backend = measure_text_detailed(
        content,
        font_size,
        font_family,
        policy=metrics_policy,
        **_font_kwargs(visual),
    )
    if record_backend:
        ctx.report.record_feature_observation(note_text_backend(backend))
    est_width = max(width_override if width_override is not None else est_width, minimum_width)
    tx = x - (est_width / 2 if align == "center" else est_width if align == "right" else 0)
    if placement == "center":
        ty = y - est_height / 2.0
    else:
        ty = y - _baseline_offset(font_size, est_height, visual)

    rotation_style = f"{rotation_degrees:.2f}" if rotation_degrees is not None else None

    style = StyleBuilder()
    style.add_flag("text").add("html", 1).add("strokeColor", "none").add("fillColor", "none")
    style.add("align", align).add("verticalAlign", "middle").add("whiteSpace", "wrap").add("rounded", 0)
    style.add("fontSize", font_size).add("fontColor", font_color).add("fontFamily", font_family)
    style.add("opacity", opacity).add("fontStyle", font_style)
    style.add("rotation", rotation_style, when=rotation_style is not None)
    add_metadata_styles(style, elem, ctx)
    add_filter_styles(style, ctx, elem, visual["filter"], fallback_color=font_color)
    ctx.add(make_bounds_vertex(ctx, style.build(), tx, ty, est_width, est_height, value=content))


def _emit_positioned_glyphs(
    ctx: EmitterContext,
    elem: Element,
    matrix: Matrix,
    visual: VisualStyle,
    x0: float,
    y0: float,
    content: str,
) -> float:
    """Approximate letter-spacing or textLength with individually positioned editable glyphs."""
    metrics_policy = ctx.rendering_options.text_metrics_policy
    font_size = max(visual["font_size"], 6)
    glyphs, glyph_widths, gap_spacing, total_width, backend = _glyph_run_layout(content, visual, metrics_policy)
    ctx.report.record_feature_observation(note_text_backend(backend))
    if not glyphs:
        return 0.0

    align = {"start": "left", "middle": "center", "end": "right"}.get(visual["text_anchor"], "left")
    start_x = x0 - (total_width / 2 if align == "center" else total_width if align == "right" else 0.0)

    child_cells: list[Cell] = []
    group_id = ctx.next_id()
    child_ctx = replace(ctx.with_parent(group_id), add_cell=child_cells.append)
    cursor_x = start_x
    emitted_count = 0

    for index, (glyph, glyph_width) in enumerate(zip(glyphs, glyph_widths, strict=True)):
        if glyph.strip():
            _emit_text_cell(
                child_ctx,
                elem,
                matrix,
                visual,
                cursor_x,
                y0,
                glyph,
                record_backend=False,
                minimum_width=max(font_size * 0.25, 1.0),
                width_override=glyph_width,
            )
            emitted_count += 1
        cursor_x += glyph_width
        if index < len(glyphs) - 1:
            cursor_x += gap_spacing

    direct_children = [cell for cell in child_cells if cell.parent == group_id]
    if emitted_count <= 1 or not direct_children:
        for cell in child_cells:
            ctx.add(cell)
        return total_width

    gx, gy, gw, gh = group_bbox(direct_children)
    ctx.add(make_bounds_vertex(ctx, "group;", gx, gy, gw, gh, cell_id=group_id))
    shift_cells(direct_children, gx, gy)
    for cell in child_cells:
        ctx.add(cell)
    return total_width


def _emit_text_along_path(
    ctx: EmitterContext,
    elem: Element,
    matrix: Matrix,
    visual: VisualStyle,
    text_path: Element,
    runs: list[TextPathRun],
) -> bool:
    """Approximate one simple SVG textPath with rotated editable glyphs."""
    href = text_path.get("href") or text_path.get("{http://www.w3.org/1999/xlink}href") or ""
    if not href.startswith("#"):
        return False

    path_id = href[1:]
    path_elem = ctx.defs.get_element(path_id)
    if path_elem is None or strip_ns(path_elem.tag) != "path":
        return False

    path_data = path_elem.get("d")
    if not path_data:
        return False

    path_matrix = ctx.defs.get_element_transform(path_id) or [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
    polyline = sample_path_polyline(
        path_data,
        point_transform=lambda px, py: apply_pt(path_matrix, px, py),
        curve_steps=80,
    )
    total_path_length = polyline_length(polyline)
    if len(polyline) < 2 or total_path_length <= 1e-6:
        return False

    metrics_policy = ctx.rendering_options.text_metrics_policy
    run_layouts: list[tuple[TextPathRun, list[str], list[float], float, float]] = []
    total_advance = 0.0
    emitted_content = False

    for run in runs:
        glyphs, glyph_widths, gap_spacing, total_width, backend = _glyph_run_layout(
            run.content,
            run.visual,
            metrics_policy,
        )
        ctx.report.record_feature_observation(note_text_backend(backend))
        emitted_content = emitted_content or any(glyph.strip() for glyph in glyphs)
        run_layouts.append((run, glyphs, glyph_widths, gap_spacing, total_width))
        total_advance += run.dx + total_width

    if not emitted_content:
        return False

    advance_scale = 1.0
    if total_advance > total_path_length and total_advance > 1e-6:
        advance_scale = total_path_length / total_advance
        total_advance = total_path_length

    start_distance = parse_start_offset(text_path.get("startOffset"), total_path_length)
    anchor = {"start": "left", "middle": "center", "end": "right"}.get(visual["text_anchor"], "left")
    if anchor == "center":
        start_distance -= total_advance / 2.0
    elif anchor == "right":
        start_distance -= total_advance

    child_cells: list[Cell] = []
    group_id = ctx.next_id()
    child_ctx = replace(ctx.with_parent(group_id), add_cell=child_cells.append)
    cursor_distance = 0.0
    emitted_count = 0

    for run, glyphs, glyph_widths, gap_spacing, total_width in run_layouts:
        font_size = max(run.visual["font_size"], 6)
        cursor_distance += run.dx * advance_scale
        path_glyph_widths = [width * advance_scale for width in glyph_widths]
        path_gap_spacing = gap_spacing * advance_scale

        for index, (glyph, glyph_width, path_glyph_width) in enumerate(
            zip(glyphs, glyph_widths, path_glyph_widths, strict=True)
        ):
            center_distance = start_distance + cursor_distance + path_glyph_width / 2.0
            path_position = point_and_angle_at_distance(polyline, center_distance)
            if glyph.strip() and path_position is not None:
                baseline_to_center = _path_center_offset(font_size, run.visual)
                normal_x, normal_y = normal_vector(path_position.angle_degrees)
                center_x = path_position.x - normal_x * baseline_to_center + normal_x * run.dy
                center_y = path_position.y - normal_y * baseline_to_center + normal_y * run.dy
                _emit_text_cell(
                    child_ctx,
                    elem,
                    matrix,
                    run.visual,
                    center_x,
                    center_y,
                    glyph,
                    record_backend=False,
                    minimum_width=max(font_size * 0.25, 1.0),
                    width_override=glyph_width,
                    align_override="center",
                    rotation_degrees=path_position.angle_degrees,
                    placement="center",
                )
                emitted_count += 1
            cursor_distance += path_glyph_width
            if index < len(glyphs) - 1:
                cursor_distance += path_gap_spacing

    direct_children = [cell for cell in child_cells if cell.parent == group_id]
    if emitted_count <= 1 or not direct_children:
        for cell in child_cells:
            ctx.add(cell)
        return emitted_count > 0

    gx, gy, gw, gh = group_bbox(direct_children)
    ctx.add(make_bounds_vertex(ctx, "group;", gx, gy, gw, gh, cell_id=group_id))
    shift_cells(direct_children, gx, gy)
    for cell in child_cells:
        ctx.add(cell)
    return True


def _emit_text_run(
    ctx: EmitterContext,
    elem: Element,
    matrix: Matrix,
    visual: VisualStyle,
    x0: float,
    y0: float,
    content: str,
) -> float:
    """Emit one logical text run and return its horizontal advance."""
    if not content:
        return 0.0
    if _should_emit_positioned_glyphs(content, visual):
        return _emit_positioned_glyphs(ctx, elem, matrix, visual, x0, y0, content)

    _emit_text_cell(ctx, elem, matrix, visual, x0, y0, content)
    return _run_advance(content, visual, ctx.rendering_options.text_metrics_policy)


def _collect_text(elem: Element) -> str:
    """Collect all text content from a `<text>` element, ignoring per-tspan styling."""
    return "".join(elem.itertext()).strip()


def _has_styled_tspans(elem: Element) -> bool:
    """Return whether any tspan needs its own draw.io text cell."""
    for child in elem:
        if strip_ns(child.tag) == "tspan" and any(child.get(attr) for attr in _TSPAN_STYLE_ATTRS):
            return True
    return False


def _tspan_visual(
    tspan: Element,
    parent_css: dict[str, str] | None,
    ctx: EmitterContext | None = None,
) -> VisualStyle:
    """Resolve tspan visual properties, using the full CSS cascade when available."""
    if ctx is not None:
        from ..css import apply_css

        computed = apply_css(
            tspan, ctx.css_rules, "tspan", parent_css, custom_props=ctx.custom_props, rule_index=ctx.rule_index
        )
    else:
        computed = dict(parent_css or {})
        computed.update(parse_style_attr(tspan.get("style", "")))
        for attr in (
            "fill",
            "font-size",
            "font-weight",
            "font-style",
            "font-family",
            "text-decoration",
            "text-anchor",
        ):
            value = tspan.get(attr)
            if value:
                computed[attr] = value
    return get_visual(tspan, computed)


def emit_text(ctx: EmitterContext, elem: Element, matrix: Matrix, css: dict[str, str] | None = None) -> None:
    """Emit an SVG `<text>` element."""
    visual = get_visual(elem, css)
    metrics_policy = ctx.rendering_options.text_metrics_policy
    x0 = parse_length(elem.get("x"))
    y0 = parse_length(elem.get("y"))

    if abs(_letter_spacing_px(visual)) > 1e-6:
        ctx.report.add_issue(
            LETTER_SPACING_APPROXIMATED,
            "warning",
            "Letter spacing was approximated with positioned editable glyphs.",
            element_tag=strip_ns(elem.tag),
            element_id=elem.get("id"),
        )

    if visual.get("text_length") is not None:
        ctx.report.add_issue(
            TEXT_LENGTH_APPROXIMATED,
            "warning",
            "SVG textLength constraints were approximated with positioned editable glyphs.",
            element_tag=strip_ns(elem.tag),
            element_id=elem.get("id"),
        )

    dominant_baseline = str(visual.get("dominant_baseline") or "alphabetic").strip().lower()
    if dominant_baseline not in {"", "auto", "alphabetic", "baseline"}:
        ctx.report.add_issue(
            DOMINANT_BASELINE_APPROXIMATED,
            "warning",
            "Dominant-baseline alignment was approximated for editable draw.io text.",
            element_tag=strip_ns(elem.tag),
            element_id=elem.get("id"),
        )

    text_path = _first_text_path_child(elem)
    if text_path is not None:
        runs = _collect_text_path_runs(text_path, visual, css, ctx)
        if not any(run.content.strip() for run in runs):
            return
        ctx.report.add_issue(
            TEXT_PATH_APPROXIMATED,
            "warning",
            "Text on a path was approximated with rotated editable glyphs placed along the source path.",
            element_tag=strip_ns(elem.tag),
            element_id=elem.get("id"),
        )
        if not _emit_text_along_path(ctx, elem, matrix, visual, text_path, runs):
            content = _collect_text(elem)
            _emit_text_run(ctx, elem, matrix, visual, x0, y0, content)
        return

    if _has_styled_tspans(elem):
        cur_x, cur_y = x0, y0

        if elem.text and elem.text.strip():
            cur_x += _emit_text_run(ctx, elem, matrix, visual, cur_x, cur_y, elem.text.strip())

        for tspan in elem:
            if strip_ns(tspan.tag) != "tspan":
                continue

            if tspan.get("x"):
                cur_x = parse_length(tspan.get("x"))
            if tspan.get("y"):
                cur_y = parse_length(tspan.get("y"))
            if tspan.get("dy"):
                cur_y += parse_float(tspan.get("dy"))
            if tspan.get("dx"):
                cur_x += parse_float(tspan.get("dx"))

            raw = tspan.text or ""
            content = raw.strip()
            if not content:
                cur_x += _run_advance(raw or " ", visual, metrics_policy)
                continue

            tspan_visual = _tspan_visual(tspan, css, ctx)
            font_size = max(tspan_visual["font_size"], 6)

            prefix_spaces = len(raw) - len(raw.lstrip())
            if prefix_spaces:
                prefix_advance, _ = measure_text(
                    " " * prefix_spaces,
                    font_size,
                    tspan_visual.get("font_family") or "Helvetica",
                    policy=metrics_policy,
                    **_font_kwargs(tspan_visual),
                )
                cur_x += prefix_advance

            cur_x += _emit_text_run(ctx, elem, matrix, tspan_visual, cur_x, cur_y, content)

            tail = tspan.tail or ""
            tail_content = tail.strip()
            if tail_content:
                prefix_spaces = len(tail) - len(tail.lstrip())
                if prefix_spaces:
                    prefix_advance, _ = measure_text(
                        " " * prefix_spaces,
                        max(visual["font_size"], 6),
                        visual.get("font_family") or "Helvetica",
                        policy=metrics_policy,
                        **_font_kwargs(visual),
                    )
                    cur_x += prefix_advance
                cur_x += _emit_text_run(ctx, elem, matrix, visual, cur_x, cur_y, tail_content)
        return

    content = _collect_text(elem)
    if not content:
        return
    _emit_text_run(ctx, elem, matrix, visual, x0, y0, content)
