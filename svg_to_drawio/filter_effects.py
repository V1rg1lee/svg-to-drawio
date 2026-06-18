"""Helpers for recognizing SVG filters that can map to native draw.io styles."""

from __future__ import annotations

from typing import Literal, TypedDict
from xml.etree.ElementTree import Element

from .styles import normalize_color
from .utils import parse_float, strip_ns


class ShadowFilter(TypedDict):
    """Normalized drop-shadow values that can be converted into draw.io styles."""

    type: str
    dx: float
    dy: float
    color: str | None
    opacity: int
    approximation: Literal["native", "approximate"]
    detail: str


_SUPPORTED_CLASSIC_SHADOW_PRIMITIVES: frozenset[str] = frozenset(
    {
        "feGaussianBlur",
        "feOffset",
        "feFlood",
        "feComposite",
        "feMerge",
        "feMergeNode",
        "feColorMatrix",
        "feComponentTransfer",
        "feFuncA",
    }
)


def parse_shadow_filter(filter_elem: Element) -> ShadowFilter | None:
    """Return a native shadow approximation for one supported SVG filter."""
    for child in filter_elem.iter():
        if strip_ns(child.tag) == "feDropShadow":
            return _from_drop_shadow(child)
    classic_shadow = _from_classic_shadow_chain(filter_elem)
    if classic_shadow is not None:
        return classic_shadow
    glow = _from_glow_chain(filter_elem)
    if glow is not None:
        return glow
    offset_only = _from_offset_chain(filter_elem)
    if offset_only is not None:
        return offset_only
    return None


def _from_drop_shadow(child: Element) -> ShadowFilter:
    """Convert one native SVG ``feDropShadow`` primitive into draw.io shadow fields."""
    return {
        "type": "shadow",
        "dx": parse_float(child.get("dx", "2")),
        "dy": parse_float(child.get("dy", "2")),
        "color": normalize_color(child.get("flood-color", "#000000")) or "#000000",
        "opacity": int(parse_float(child.get("flood-opacity", "0.5")) * 100),
        "approximation": "native",
        "detail": "SVG drop shadows were mapped directly to native draw.io shadow styling.",
    }


def _from_classic_shadow_chain(filter_elem: Element) -> ShadowFilter | None:
    """Recognize the common blur+offset+flood shadow pipeline exported by design tools."""
    primitives = [child for child in filter_elem if strip_ns(child.tag)]
    primitive_tags = {strip_ns(child.tag) for child in primitives}
    if not primitive_tags or not primitive_tags.issubset(_SUPPORTED_CLASSIC_SHADOW_PRIMITIVES):
        return None

    offset = next((child for child in primitives if strip_ns(child.tag) == "feOffset"), None)
    flood = next((child for child in primitives if strip_ns(child.tag) == "feFlood"), None)
    has_composite = any(strip_ns(child.tag) == "feComposite" for child in primitives)
    has_merge = any(strip_ns(child.tag) == "feMerge" for child in primitives)
    if offset is None or flood is None or not (has_composite or has_merge):
        return None

    return {
        "type": "shadow",
        "dx": parse_float(offset.get("dx", "2")),
        "dy": parse_float(offset.get("dy", "2")),
        "color": normalize_color(flood.get("flood-color", "#000000")) or "#000000",
        "opacity": int(parse_float(flood.get("flood-opacity", "0.5")) * 100),
        "approximation": "native",
        "detail": "A classic blur-plus-offset shadow chain was mapped to native draw.io shadow styling.",
    }


def _from_glow_chain(filter_elem: Element) -> ShadowFilter | None:
    """Recognize lightweight blur/glow filters and approximate them with a centered shadow."""
    primitives = [child for child in filter_elem if strip_ns(child.tag)]
    primitive_tags = {strip_ns(child.tag) for child in primitives}
    supported = {"feGaussianBlur", "feFlood", "feComposite", "feMerge", "feMergeNode", "feColorMatrix"}
    if not primitive_tags or not primitive_tags.issubset(supported):
        return None
    if primitive_tags == {"feGaussianBlur"}:
        return None

    blur = next((child for child in primitives if strip_ns(child.tag) == "feGaussianBlur"), None)
    if blur is None:
        return None
    std_deviation = parse_float(blur.get("stdDeviation", "0"))
    if std_deviation <= 0 or std_deviation > 3.5:
        return None
    if any(strip_ns(child.tag) == "feOffset" for child in primitives):
        return None

    flood = next((child for child in primitives if strip_ns(child.tag) == "feFlood"), None)
    color = normalize_color(flood.get("flood-color")) if flood is not None else None
    opacity = int(parse_float(flood.get("flood-opacity", "0.35")) * 100) if flood is not None else 35
    return {
        "type": "shadow",
        "dx": 0.0,
        "dy": 0.0,
        "color": color,
        "opacity": opacity,
        "approximation": "approximate",
        "detail": (
            "A light blur or glow filter was approximated with a centered native shadow to keep the shape editable."
        ),
    }


def _from_offset_chain(filter_elem: Element) -> ShadowFilter | None:
    """Recognize simple offset filters and approximate them with a native shadow."""
    primitives = [child for child in filter_elem if strip_ns(child.tag)]
    primitive_tags = {strip_ns(child.tag) for child in primitives}
    supported = {"feOffset", "feFlood", "feComposite", "feMerge", "feMergeNode", "feColorMatrix"}
    if not primitive_tags or not primitive_tags.issubset(supported):
        return None

    offset = next((child for child in primitives if strip_ns(child.tag) == "feOffset"), None)
    if offset is None:
        return None
    if any(strip_ns(child.tag) == "feGaussianBlur" for child in primitives):
        return None

    flood = next((child for child in primitives if strip_ns(child.tag) == "feFlood"), None)
    color = normalize_color(flood.get("flood-color")) if flood is not None else None
    opacity = int(parse_float(flood.get("flood-opacity", "0.35")) * 100) if flood is not None else 35
    return {
        "type": "shadow",
        "dx": parse_float(offset.get("dx", "2")),
        "dy": parse_float(offset.get("dy", "2")),
        "color": color,
        "opacity": opacity,
        "approximation": "approximate",
        "detail": "A simple offset filter was approximated with a native shadow so the element could stay editable.",
    }
