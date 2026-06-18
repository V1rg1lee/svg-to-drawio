"""Helpers for simple clip-path and mask rewrites that can stay editable."""

from __future__ import annotations

import re
from xml.etree.ElementTree import Element

from .defs import DefsIndex
from .utils import parse_length, strip_ns

SimpleBounds = tuple[float, float, float, float]

_SIMPLE_CLIP_TAGS: frozenset[str] = frozenset({"rect", "circle", "ellipse", "polygon"})


def local_shape_bounds(elem: Element) -> SimpleBounds | None:
    """Return local untransformed bounds for a simple SVG geometry element."""
    tag = strip_ns(elem.tag)
    if tag == "rect":
        x = parse_length(elem.get("x"))
        y = parse_length(elem.get("y"))
        width = parse_length(elem.get("width"))
        height = parse_length(elem.get("height"))
        return x, y, width, height
    if tag == "circle":
        cx = parse_length(elem.get("cx"))
        cy = parse_length(elem.get("cy"))
        radius = parse_length(elem.get("r"))
        return cx - radius, cy - radius, radius * 2.0, radius * 2.0
    if tag == "ellipse":
        cx = parse_length(elem.get("cx"))
        cy = parse_length(elem.get("cy"))
        rx = parse_length(elem.get("rx"))
        ry = parse_length(elem.get("ry"))
        return cx - rx, cy - ry, rx * 2.0, ry * 2.0
    if tag == "polygon":
        coords = [float(item) for item in re.findall(r"[-\d.eE+]+", elem.get("points", ""))]
        if len(coords) < 6:
            return None
        xs = coords[0::2]
        ys = coords[1::2]
        x = min(xs)
        y = min(ys)
        return x, y, max(xs) - x, max(ys) - y
    return None


def bounds_contains(outer: SimpleBounds, inner: SimpleBounds) -> bool:
    """Return whether one bounds tuple fully contains another."""
    ox, oy, ow, oh = outer
    ix, iy, iw, ih = inner
    epsilon = 1e-6
    return ix >= ox - epsilon and iy >= oy - epsilon and ix + iw <= ox + ow + epsilon and iy + ih <= oy + oh + epsilon


def simple_clip_candidate(defs: DefsIndex, clip_ref: str, target_bounds: SimpleBounds) -> Element | None:
    """Return one editable replacement geometry for a simple clip-path reference."""
    candidate, units = _simple_candidate(defs, clip_ref, expected_tag="clipPath", units_attr="clipPathUnits")
    if candidate is None or units is None:
        return None
    return _shape_in_target_units(candidate, units, target_bounds)


def simple_mask_candidate(defs: DefsIndex, mask_ref: str, target_bounds: SimpleBounds) -> Element | None:
    """Return one editable replacement geometry for a simple mask reference."""
    candidate, units = _simple_candidate(defs, mask_ref, expected_tag="mask", units_attr="maskContentUnits")
    if candidate is None or units is None:
        return None

    fill = (candidate.get("fill") or "").strip().lower()
    if fill and fill not in {"#fff", "#ffffff", "white"}:
        return None
    return _shape_in_target_units(candidate, units, target_bounds)


def _simple_candidate(
    defs: DefsIndex,
    ref: str,
    *,
    expected_tag: str,
    units_attr: str,
) -> tuple[Element | None, str | None]:
    match = re.match(r"url\(#([^)]+)\)", ref)
    if not match:
        return None, None
    container = defs.get_element(match.group(1))
    if container is None or strip_ns(container.tag) != expected_tag:
        return None, None
    units = (container.get(units_attr) or "userSpaceOnUse").strip()
    if units not in {"userSpaceOnUse", "objectBoundingBox"}:
        return None, None

    drawable_children = [child for child in container if strip_ns(child.tag) in _SIMPLE_CLIP_TAGS]
    if len(drawable_children) != 1:
        return None, None
    return drawable_children[0], units


def _shape_in_target_units(candidate: Element, units: str, target_bounds: SimpleBounds) -> Element | None:
    if units == "userSpaceOnUse":
        return candidate

    x, y, width, height = target_bounds
    tag = strip_ns(candidate.tag)
    if tag == "rect":
        attrib = dict(candidate.attrib)
        attrib["x"] = f"{x + parse_length(candidate.get('x')) * width:.6f}"
        attrib["y"] = f"{y + parse_length(candidate.get('y')) * height:.6f}"
        attrib["width"] = f"{parse_length(candidate.get('width')) * width:.6f}"
        attrib["height"] = f"{parse_length(candidate.get('height')) * height:.6f}"
        if candidate.get("rx") is not None:
            attrib["rx"] = f"{parse_length(candidate.get('rx')) * width:.6f}"
        if candidate.get("ry") is not None:
            attrib["ry"] = f"{parse_length(candidate.get('ry')) * height:.6f}"
        return Element(candidate.tag, attrib)

    if tag == "circle":
        cx = x + parse_length(candidate.get("cx")) * width
        cy = y + parse_length(candidate.get("cy")) * height
        radius = parse_length(candidate.get("r"))
        if abs(width - height) <= 1e-6:
            return Element(
                candidate.tag,
                {
                    **candidate.attrib,
                    "cx": f"{cx:.6f}",
                    "cy": f"{cy:.6f}",
                    "r": f"{radius * width:.6f}",
                },
            )
        return Element(
            "ellipse",
            {
                "cx": f"{cx:.6f}",
                "cy": f"{cy:.6f}",
                "rx": f"{radius * width:.6f}",
                "ry": f"{radius * height:.6f}",
            },
        )

    if tag == "ellipse":
        return Element(
            candidate.tag,
            {
                **candidate.attrib,
                "cx": f"{x + parse_length(candidate.get('cx')) * width:.6f}",
                "cy": f"{y + parse_length(candidate.get('cy')) * height:.6f}",
                "rx": f"{parse_length(candidate.get('rx')) * width:.6f}",
                "ry": f"{parse_length(candidate.get('ry')) * height:.6f}",
            },
        )

    if tag == "polygon":
        coords = [float(item) for item in re.findall(r"[-\d.eE+]+", candidate.get("points", ""))]
        if len(coords) < 6 or len(coords) % 2 != 0:
            return None
        scaled_points: list[str] = []
        for px, py in zip(coords[0::2], coords[1::2], strict=True):
            scaled_points.append(f"{x + px * width:.6f},{y + py * height:.6f}")
        return Element(candidate.tag, {**candidate.attrib, "points": " ".join(scaled_points)})

    return None
