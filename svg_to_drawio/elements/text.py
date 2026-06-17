"""Emitters for SVG text elements."""

from __future__ import annotations

from xml.etree.ElementTree import Element

from ..cell_factory import make_bounds_vertex
from ..compatibility import note_text_backend
from ..emitter_context import EmitterContext
from ..style_builder import StyleBuilder
from ..styles import VisualStyle, font_style_flag, get_visual, opacity_pct
from ..text_metrics import measure_text, measure_text_detailed
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


def _has_text_path(elem: Element) -> bool:
    """Return whether the text element contains a `<textPath>` child."""
    return any(strip_ns(child.tag) == "textPath" for child in elem)


def _emit_text_cell(
    ctx: EmitterContext,
    elem: Element,
    matrix: Matrix,
    visual: VisualStyle,
    x0: float,
    y0: float,
    content: str,
) -> None:
    """Emit one draw.io text cell."""
    font_color = visual["text_fill"] or "#000000"
    font_size = max(visual["font_size"], 6)
    font_family = visual.get("font_family") or "Helvetica"
    metrics_policy = ctx.rendering_options.text_metrics_policy
    opacity = opacity_pct(visual["opacity"] * visual["text_opacity"])
    align = {"start": "left", "middle": "center", "end": "right"}.get(visual["text_anchor"], "left")
    font_style = font_style_flag(visual)

    x, y = apply_pt(matrix, x0, y0)
    est_width, est_height, backend = measure_text_detailed(
        content,
        font_size,
        font_family,
        font_weight=str(visual.get("font_weight", "normal") or "normal"),
        font_style=str(visual.get("font_style_v", "normal") or "normal"),
        policy=metrics_policy,
    )
    ctx.report.record_feature_observation(note_text_backend(backend))
    est_width = max(est_width, 20.0)
    tx = x - (est_width / 2 if align == "center" else est_width if align == "right" else 0)

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
        baseline_offset = est_height * 0.50
    elif dominant_baseline in {"text-before-edge", "before-edge", "hanging"}:
        baseline_offset = est_height * 0.18
    elif dominant_baseline in {"text-after-edge", "after-edge", "ideographic"}:
        baseline_offset = est_height * 0.95
    else:
        baseline_offset = max(font_size * 0.85, est_height * 0.60)
    ty = y - baseline_offset - baseline_shift_px

    style = StyleBuilder()
    style.add_flag("text").add("html", 1).add("strokeColor", "none").add("fillColor", "none")
    style.add("align", align).add("verticalAlign", "middle").add("whiteSpace", "wrap").add("rounded", 0)
    style.add("fontSize", font_size).add("fontColor", font_color).add("fontFamily", font_family)
    style.add("opacity", opacity).add("fontStyle", font_style)
    add_metadata_styles(style, elem, ctx)
    add_filter_styles(style, ctx, visual["filter"])
    ctx.add(make_bounds_vertex(ctx, style.build(), tx, ty, est_width, est_height, value=content))


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

        computed = apply_css(tspan, ctx.css_rules, "tspan", parent_css, custom_props=ctx.custom_props)
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

    letter_spacing = str(visual.get("letter_spacing") or "normal").strip().lower()
    if letter_spacing not in {"", "0", "0px", "normal"}:
        ctx.report.add_issue(
            "letter-spacing-ignored",
            "warning",
            "Letter spacing is not preserved natively in draw.io text; the plain text content was kept.",
            element_tag=strip_ns(elem.tag),
            element_id=elem.get("id"),
        )

    dominant_baseline = str(visual.get("dominant_baseline") or "alphabetic").strip().lower()
    if dominant_baseline not in {"", "auto", "alphabetic", "baseline"}:
        ctx.report.add_issue(
            "dominant-baseline-approximated",
            "warning",
            "Dominant-baseline alignment was approximated for editable draw.io text.",
            element_tag=strip_ns(elem.tag),
            element_id=elem.get("id"),
        )

    if _has_text_path(elem):
        content = _collect_text(elem)
        if not content:
            return
        ctx.report.add_issue(
            "text-path-approximated",
            "warning",
            "Text on a path was flattened into regular editable text near the source anchor point.",
            element_tag=strip_ns(elem.tag),
            element_id=elem.get("id"),
        )
        _emit_text_cell(ctx, elem, matrix, visual, x0, y0, content)
        return

    if _has_styled_tspans(elem):
        cur_x, cur_y = x0, y0

        if elem.text and elem.text.strip():
            content = elem.text.strip()
            _emit_text_cell(ctx, elem, matrix, visual, cur_x, cur_y, content)
            advance, _ = measure_text(
                content,
                max(visual["font_size"], 6),
                visual.get("font_family") or "Helvetica",
                font_weight=str(visual.get("font_weight", "normal") or "normal"),
                font_style=str(visual.get("font_style_v", "normal") or "normal"),
                policy=metrics_policy,
            )
            cur_x += advance

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
                advance, _ = measure_text(
                    raw or " ",
                    max(visual["font_size"], 6),
                    visual.get("font_family") or "Helvetica",
                    font_weight=str(visual.get("font_weight", "normal") or "normal"),
                    font_style=str(visual.get("font_style_v", "normal") or "normal"),
                    policy=metrics_policy,
                )
                cur_x += advance
                continue

            tspan_visual = _tspan_visual(tspan, css, ctx)
            font_size = max(tspan_visual["font_size"], 6)

            prefix_spaces = len(raw) - len(raw.lstrip())
            if prefix_spaces:
                prefix_advance, _ = measure_text(
                    " " * prefix_spaces,
                    font_size,
                    tspan_visual.get("font_family") or "Helvetica",
                    font_weight=str(tspan_visual.get("font_weight", "normal") or "normal"),
                    font_style=str(tspan_visual.get("font_style_v", "normal") or "normal"),
                    policy=metrics_policy,
                )
                cur_x += prefix_advance

            _emit_text_cell(ctx, elem, matrix, tspan_visual, cur_x, cur_y, content)
            content_advance, _ = measure_text(
                content,
                font_size,
                tspan_visual.get("font_family") or "Helvetica",
                font_weight=str(tspan_visual.get("font_weight", "normal") or "normal"),
                font_style=str(tspan_visual.get("font_style_v", "normal") or "normal"),
                policy=metrics_policy,
            )
            cur_x += content_advance

            tail = tspan.tail or ""
            tail_content = tail.strip()
            if tail_content:
                prefix_spaces = len(tail) - len(tail.lstrip())
                if prefix_spaces:
                    prefix_advance, _ = measure_text(
                        " " * prefix_spaces,
                        max(visual["font_size"], 6),
                        visual.get("font_family") or "Helvetica",
                        font_weight=str(visual.get("font_weight", "normal") or "normal"),
                        font_style=str(visual.get("font_style_v", "normal") or "normal"),
                        policy=metrics_policy,
                    )
                    cur_x += prefix_advance
                _emit_text_cell(ctx, elem, matrix, visual, cur_x, cur_y, tail_content)
                tail_advance, _ = measure_text(
                    tail_content,
                    max(visual["font_size"], 6),
                    visual.get("font_family") or "Helvetica",
                    font_weight=str(visual.get("font_weight", "normal") or "normal"),
                    font_style=str(visual.get("font_style_v", "normal") or "normal"),
                    policy=metrics_policy,
                )
                cur_x += tail_advance
        return

    content = _collect_text(elem)
    if not content:
        return
    _emit_text_cell(ctx, elem, matrix, visual, x0, y0, content)
