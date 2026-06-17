"""Helpers for embedding unsupported SVG fragments as self-contained SVG images."""

from __future__ import annotations

import re
from copy import deepcopy
from urllib.parse import quote_from_bytes
from xml.etree.ElementTree import Element, tostring

from .diagnostics import ConversionReport
from .utils import parse_style_attr, strip_ns

# Matches url(#id) or bare #id in attribute values and style text.
_LOCAL_REF_RE = re.compile(r"url\(#([^)]+)\)|(?:^|[\s:,])#([A-Za-z][\w.-]*)")

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


def _collect_refs_from_text(text: str, seen: set[str]) -> None:
    """Accumulate local ID references found in any text (attribute value or style)."""
    for m in _LOCAL_REF_RE.finditer(text):
        ref = m.group(1) or m.group(2)
        if ref:
            seen.add(ref)


def _collect_refs(node: Element, seen: set[str]) -> None:
    """Recursively collect all local ID references from a sub-tree's attributes."""
    for val in node.attrib.values():
        _collect_refs_from_text(val, seen)
    for child in node:
        _collect_refs(child, seen)


def _slice_defs(svg_root: Element, elem: Element) -> Element | None:
    """Build a minimal <defs> containing only the definitions referenced by elem's sub-tree.

    Performs a transitive closure so that defs which themselves reference other defs are
    included too (e.g. a clipPath that uses a gradient).
    CSS <style> blocks are not included here — they are copied separately because class-based
    rules can apply to any descendant of the fragment.
    """
    id_to_def: dict[str, Element] = {}
    for child in svg_root:
        if strip_ns(child.tag) == "defs":
            for def_child in child:
                def_id = def_child.get("id")
                if def_id:
                    id_to_def[def_id] = def_child

    if not id_to_def:
        return None

    needed: set[str] = set()
    _collect_refs(elem, needed)

    # Also scan root-level <style> blocks: CSS rules may reference defs via url(#id).
    for child in svg_root:
        if strip_ns(child.tag) == "style":
            _collect_refs_from_text(child.text or "", needed)

    # Transitive expansion: referenced defs may reference other defs.
    frontier = set(needed)
    while frontier:
        next_frontier: set[str] = set()
        for ref_id in frontier:
            def_elem = id_to_def.get(ref_id)
            if def_elem is not None:
                inner: set[str] = set()
                _collect_refs(def_elem, inner)
                new = inner - needed
                needed |= new
                next_frontier |= new
        frontier = next_frontier

    relevant = [deepcopy(id_to_def[ref_id]) for ref_id in needed if ref_id in id_to_def]
    if not relevant:
        return None

    defs_elem = Element("defs")
    for child in relevant:
        defs_elem.append(child)
    return defs_elem


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
    sliced = _slice_defs(svg_root, elem)
    if sliced is not None:
        wrapper.append(sliced)
    for child in svg_root:
        if strip_ns(child.tag) == "style":
            wrapper.append(deepcopy(child))

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
