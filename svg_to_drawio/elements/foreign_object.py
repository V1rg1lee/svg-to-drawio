"""Emit textual SVG foreignObject content as editable draw.io labels."""

from __future__ import annotations

import html
import re
from xml.etree.ElementTree import Element

from ..cell_factory import make_box_vertex
from ..compatibility import note_text_backend
from ..css import AncestorInfo, ancestor_info, apply_css
from ..element_geometry import image_bounds
from ..emitter_context import EmitterContext
from ..issue_codes import FOREIGN_OBJECT_TEXT_APPROXIMATED
from ..style_builder import StyleBuilder
from ..styles import VisualStyle, font_style_flag, get_visual, opacity_pct
from ..text_metrics import measure_text_detailed
from ..transforms import Matrix
from ..utils import parse_length, strip_ns
from .style_support import add_filter_styles, add_metadata_styles

_BLOCK_TAGS: frozenset[str] = frozenset(
    {
        "address",
        "article",
        "aside",
        "blockquote",
        "div",
        "footer",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "li",
        "main",
        "nav",
        "p",
        "pre",
        "section",
    }
)


def _font_kwargs(visual: VisualStyle) -> dict[str, str]:
    """Return normalized measurement options for one resolved text style."""
    return {
        "font_weight": str(visual.get("font_weight", "normal") or "normal"),
        "font_style": str(visual.get("font_style_v", "normal") or "normal"),
    }


def _extract_lines(elem: Element) -> list[str]:
    """Extract readable lines from an XHTML subtree without retaining unsafe markup."""
    lines: list[str] = []
    current: list[str] = []

    def flush_line() -> None:
        text = re.sub(r"\s+", " ", "".join(current)).strip()
        if text:
            lines.append(text)
        current.clear()

    def visit(node: Element, *, root: bool = False) -> None:
        tag = strip_ns(node.tag).lower()
        is_block = tag in _BLOCK_TAGS
        if is_block and not root and current:
            flush_line()
        if tag == "br":
            flush_line()
            return
        if node.text:
            current.append(node.text)
        for child in node:
            visit(child)
            if child.tail:
                current.append(child.tail)
        if is_block and not root:
            flush_line()

    visit(elem, root=True)
    flush_line()
    return lines


def _resolve_visual(
    ctx: EmitterContext,
    elem: Element,
    inherited_css: dict[str, str] | None,
) -> tuple[VisualStyle, dict[str, str]]:
    """Resolve the style of the first text-bearing XHTML descendant."""
    selected_elem = elem
    selected_css = dict(inherited_css or {})

    def visit(
        node: Element,
        parent_css: dict[str, str],
        ancestors: list[AncestorInfo],
    ) -> bool:
        nonlocal selected_elem, selected_css
        tag = strip_ns(node.tag)
        computed = apply_css(
            node,
            ctx.css_rules,
            tag,
            parent_css,
            ancestors=ancestors,
            custom_props=ctx.custom_props,
            rule_index=ctx.rule_index,
        )
        if computed.get("color") and not computed.get("fill"):
            computed["fill"] = computed["color"]
        if node.text and node.text.strip():
            selected_elem = node
            selected_css = computed
            return True

        child_ancestors = ancestors + [ancestor_info(node)]
        return any(visit(child, computed, child_ancestors) for child in node)

    visit(elem, selected_css, [])
    return get_visual(selected_elem, selected_css), selected_css


def emit_foreign_object(
    ctx: EmitterContext,
    elem: Element,
    matrix: Matrix,
    css: dict[str, str] | None = None,
) -> None:
    """Emit textual XHTML inside an SVG foreignObject as editable draw.io text."""
    lines = _extract_lines(elem)
    if not lines:
        return

    ctx.report.add_issue(
        FOREIGN_OBJECT_TEXT_APPROXIMATED,
        "warning",
        "HTML text inside foreignObject was flattened to editable draw.io text; complex HTML layout may be simplified.",
        element_tag=strip_ns(elem.tag),
        element_id=elem.get("id"),
    )
    visual, html_css = _resolve_visual(ctx, elem, css)
    content = "<br>".join(html.escape(line) for line in lines)
    font_size = max(visual["font_size"], 6)
    font_family = visual.get("font_family") or "Helvetica"
    measured_width, measured_height, backend = measure_text_detailed(
        max(lines, key=len),
        font_size,
        font_family,
        policy=ctx.rendering_options.text_metrics_policy,
        **_font_kwargs(visual),
    )
    ctx.report.record_feature_observation(note_text_backend(backend))

    x = parse_length(elem.get("x"), 0.0)
    y = parse_length(elem.get("y"), 0.0)
    width = parse_length(elem.get("width"), measured_width) or measured_width
    height = parse_length(elem.get("height"), measured_height * len(lines)) or measured_height * len(lines)
    box = image_bounds(matrix, x, y, width, height)

    text_align = (html_css.get("text-align") or "").strip().lower()
    align = {"center": "center", "right": "right", "end": "right"}.get(text_align, "left")
    font_color = visual["text_fill"] or html_css.get("color") or "#000000"
    style = StyleBuilder()
    style.add_flag("text").add("html", 1).add("strokeColor", "none").add("fillColor", "none")
    style.add("align", align).add("verticalAlign", "middle").add("whiteSpace", "wrap").add("rounded", 0)
    style.add("fontSize", font_size).add("fontColor", font_color).add("fontFamily", font_family)
    style.add("opacity", opacity_pct(visual["opacity"] * visual["text_opacity"]))
    style.add("fontStyle", font_style_flag(visual))
    rotation = box.rotation_if_visible()
    rotation_style = f"{rotation:.2f}" if rotation is not None else None
    style.add("rotation", rotation_style, when=rotation_style is not None)
    add_metadata_styles(style, elem, ctx)
    add_filter_styles(style, ctx, elem, visual["filter"], fallback_color=font_color)
    ctx.add(make_box_vertex(ctx, style.build(), box, value=content))
