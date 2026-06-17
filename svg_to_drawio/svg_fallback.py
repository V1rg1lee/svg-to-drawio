"""Helpers for embedding unsupported SVG fragments as self-contained SVG images."""

from __future__ import annotations

from copy import deepcopy
from urllib.parse import quote_from_bytes
from xml.etree.ElementTree import Element, tostring

from .diagnostics import ConversionReport
from .utils import parse_style_attr, strip_ns

_SVG_NS = "http://www.w3.org/2000/svg"
_XLINK_NS = "http://www.w3.org/1999/xlink"


def data_uri_from_svg(svg_text: str) -> str:
    """Encode UTF-8 SVG markup as a percent-escaped data URI."""
    return f"data:image/svg+xml,{quote_from_bytes(svg_text.encode('utf-8'), safe='')}"


def matrix_to_svg(matrix: list[float]) -> str:
    """Serialize a six-value affine matrix into SVG's transform syntax."""
    return "matrix({})".format(" ".join(f"{value:.6f}" for value in matrix))


def _style_text(computed_css: dict[str, str] | None) -> str | None:
    """Serialize resolved CSS declarations into a stable inline style string."""
    if not computed_css:
        return None
    items = [f"{name}:{value}" for name, value in sorted(computed_css.items()) if value]
    return ";".join(items) if items else None


def _copy_defs_and_styles(wrapper: Element, svg_root: Element) -> None:
    """Copy global defs and style blocks so the fallback fragment stays self-contained."""
    copied_defs = False
    for child in svg_root:
        tag = strip_ns(child.tag)
        if tag == "defs":
            wrapper.append(deepcopy(child))
            copied_defs = True
        elif tag == "style":
            wrapper.append(deepcopy(child))

    if copied_defs:
        return

    style_nodes = [deepcopy(node) for node in svg_root.iter() if strip_ns(node.tag) == "style"]
    for node in style_nodes:
        wrapper.append(node)


def build_fallback_svg_data_uri(
    svg_root: Element,
    elem: Element,
    *,
    parent_matrix: list[float],
    bbox: tuple[float, float, float, float],
    computed_css: dict[str, str] | None,
    padding: float = 0.0,
    report: ConversionReport | None = None,
) -> str:
    """Build a self-contained SVG data URI for one unsupported fragment.

    *padding* expands the viewBox on all four sides so that strokes at the element
    boundary and blur filter halos are not clipped by the image cell edge.
    """
    x, y, width, height = bbox
    x -= padding
    y -= padding
    width += 2.0 * padding
    height += 2.0 * padding
    width = max(width, 1.0)
    height = max(height, 1.0)

    wrapper = Element(
        "svg",
        {
            "xmlns": _SVG_NS,
            "xmlns:xlink": _XLINK_NS,
            "viewBox": f"{x:.6f} {y:.6f} {width:.6f} {height:.6f}",
            "width": f"{width:.6f}",
            "height": f"{height:.6f}",
        },
    )
    _copy_defs_and_styles(wrapper, svg_root)

    outer_group = Element("g", {"transform": matrix_to_svg(parent_matrix)})
    fragment = deepcopy(elem)

    merged_style = parse_style_attr(fragment.get("style", ""))
    merged_style.update(dict(computed_css or {}))
    style_text = _style_text(merged_style)
    if style_text:
        fragment.set("style", style_text)
    outer_group.append(fragment)
    wrapper.append(outer_group)

    svg_text = tostring(wrapper, encoding="unicode")
    if report is not None:
        report.add_asset(
            href=f"inline:{strip_ns(elem.tag)}",
            status="embedded-svg-fallback",
            mime_type="image/svg+xml",
            message=f"Embedded fallback generated for <{strip_ns(elem.tag)}>.",
        )
    return data_uri_from_svg(svg_text)
