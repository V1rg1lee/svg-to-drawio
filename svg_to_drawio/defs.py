"""Definition lookup helpers for gradients, markers, filters, and reusable SVG nodes."""

from __future__ import annotations

import math
import re
from typing import TypedDict
from xml.etree.ElementTree import Element

from .styles import GradientStop, GradientStyle, normalize_color
from .utils import parse_float, parse_style_attr, strip_ns

# Heuristic mapping of common marker identifiers to draw.io arrow names.
_MARKER_ID_MAP: dict[str, str] = {
    "arrow": "block",
    "arrowhead": "block",
    "triangle": "block",
    "circle": "oval",
    "dot": "oval",
    "diamond": "diamond",
    "open": "open",
}
_POINT_RE = re.compile(r"[-\d.eE+]+")


class ShadowFilter(TypedDict):
    """Normalized drop-shadow values that can be converted into draw.io styles."""

    type: str
    dx: float
    dy: float
    color: str
    opacity: int


def _stop_color(stop_elem: Element) -> str:
    """Resolve a gradient stop color while folding stop opacity into the output color.

    draw.io gradients only accept colors, not per-stop alpha values, so partially transparent
    stops are blended against white to produce a stable fallback.
    """
    props = parse_style_attr(stop_elem.get("style", ""))
    raw = props.get("stop-color") or stop_elem.get("stop-color", "#000000")
    color = normalize_color(raw) or "#000000"
    raw_opacity = props.get("stop-opacity") or stop_elem.get("stop-opacity", "1")
    alpha = max(0.0, min(1.0, parse_float(raw_opacity, 1.0)))
    if alpha < 1.0 and color.startswith("#") and len(color) == 7:
        red = int(color[1:3], 16)
        green = int(color[3:5], 16)
        blue = int(color[5:7], 16)
        red = round(red * alpha + 255 * (1 - alpha))
        green = round(green * alpha + 255 * (1 - alpha))
        blue = round(blue * alpha + 255 * (1 - alpha))
        color = f"#{red:02x}{green:02x}{blue:02x}"
    return color


def _get_href(elem: Element) -> str | None:
    """Return the fragment ID from href or xlink:href if it is a local reference."""
    href = elem.get("href") or elem.get("{http://www.w3.org/1999/xlink}href") or ""
    return href[1:] if href.startswith("#") else None


def _parse_stop_offset(value: str | None) -> float:
    """Parse and normalize one SVG gradient stop offset to the inclusive range `[0, 1]`."""
    text = (value or "0").strip()
    if text.endswith("%"):
        return max(0.0, min(1.0, parse_float(text[:-1]) / 100.0))
    return max(0.0, min(1.0, parse_float(text, 0.0)))


def _parse_stops(elem: Element) -> list[GradientStop]:
    """Extract and sort gradient stops from a gradient element."""
    stops: list[GradientStop] = []
    for child in elem:
        if strip_ns(child.tag) == "stop":
            stops.append({"offset": _parse_stop_offset(child.get("offset")), "color": _stop_color(child)})
    stops.sort(key=lambda stop: stop["offset"])
    return stops


def _linear_direction(elem: Element) -> str:
    """Derive a draw.io gradient direction from a linearGradient element's own geometry."""
    x1 = parse_float(elem.get("x1", "0"))
    y1 = parse_float(elem.get("y1", "0"))
    x2 = parse_float(elem.get("x2", "1"))
    y2 = parse_float(elem.get("y2", "0"))
    dx, dy = x2 - x1, y2 - y1
    direction = ("east" if dx >= 0 else "west") if abs(dx) >= abs(dy) else ("south" if dy >= 0 else "north")
    gradient_transform = elem.get("gradientTransform", "")
    if gradient_transform:
        from .transforms import parse_transform

        matrix = parse_transform(gradient_transform)
        angle = math.degrees(math.atan2(matrix[1], matrix[0]))
        if -45 <= angle <= 45:
            direction = "east"
        elif 45 < angle <= 135:
            direction = "south"
        elif angle > 135 or angle < -135:
            direction = "west"
        else:
            direction = "north"
    return direction


def _has_own_geometry(elem: Element) -> bool:
    """Return True if a gradient element specifies its own directional geometry."""
    return any(elem.get(attr) is not None for attr in ("x1", "y1", "x2", "y2", "gradientTransform"))


class DefsIndex:
    """Index all reusable `<defs>` content for quick lookup during conversion."""

    def __init__(self) -> None:
        self._elements: dict[str, Element] = {}
        self._gradients: dict[str, GradientStyle] = {}
        self._markers: dict[str, str] = {}
        self._filters: dict[str, ShadowFilter] = {}

    def index(self, svg_root: Element) -> None:
        """Scan an SVG tree and cache addressable `<defs>` resources by identifier."""
        for elem in svg_root.iter():
            tag = strip_ns(elem.tag)
            element_id = elem.get("id")
            if element_id:
                self._elements[element_id] = elem
            if tag == "linearGradient":
                self._index_linear(elem, element_id)
            elif tag == "radialGradient":
                self._index_radial(elem, element_id)
            elif tag == "marker":
                self._index_marker(elem, element_id)
            elif tag == "filter":
                self._index_filter(elem, element_id)

        # Second pass: resolve gradient href inheritance for gradients without their own stops.
        # SVG spec: attributes not present on the child are inherited from the href parent.
        # The most common pattern (Inkscape/Illustrator) is: child has no stops but overrides
        # the geometry (x1/y1/x2/y2 or gradientTransform) to change the gradient direction.
        for elem in svg_root.iter():
            tag = strip_ns(elem.tag)
            if tag not in ("linearGradient", "radialGradient"):
                continue
            element_id = elem.get("id")
            if not element_id or element_id in self._gradients:
                continue
            target_id = _get_href(elem)
            if not target_id or target_id not in self._gradients:
                continue
            parent = self._gradients[target_id]
            if tag == "linearGradient" and _has_own_geometry(elem):
                # Merge: stops from parent, direction from child's own geometry.
                stops = parent["stops"]
                self._gradients[element_id] = {
                    "color": stops[0]["color"],
                    "color2": stops[-1]["color"],
                    "direction": _linear_direction(elem),
                    "kind": "linear",
                    "stops": stops,
                }
            else:
                # No own geometry (or radial): inherit the parent definition entirely.
                self._gradients[element_id] = parent

    def _index_linear(self, elem: Element, element_id: str | None) -> None:
        """Register a linear gradient in draw.io's reduced gradient model."""
        stops = _parse_stops(elem)
        if not stops or not element_id:
            return
        self._gradients[element_id] = {
            "color": stops[0]["color"],
            "color2": stops[-1]["color"],
            "direction": _linear_direction(elem),
            "kind": "linear",
            "stops": stops,
        }

    def _index_radial(self, elem: Element, element_id: str | None) -> None:
        """Register a radial gradient using draw.io's radial gradient direction."""
        stops = _parse_stops(elem)
        if not stops or not element_id:
            return
        self._gradients[element_id] = {
            "color": stops[0]["color"],
            "color2": stops[-1]["color"],
            "direction": "radial",
            "kind": "radial",
            "stops": stops,
        }

    def _index_marker(self, elem: Element, element_id: str | None) -> None:
        """Map an SVG marker to the closest built-in draw.io arrow shape."""
        if not element_id:
            return

        lower_id = element_id.lower()

        for key, arrow in _MARKER_ID_MAP.items():
            if key in lower_id:
                self._markers[element_id] = arrow
                return

        for child in elem.iter():
            tag = strip_ns(child.tag)
            if tag == "circle":
                self._markers[element_id] = "oval"
                return
            if tag == "polygon":
                coords = _POINT_RE.findall(child.get("points", ""))
                point_count = len(coords) // 2
                if point_count == 4 and "diamond" in lower_id:
                    self._markers[element_id] = "diamond"
                    return
                if point_count == 3 and any(token in lower_id for token in ("arrow", "triangle", "arrowhead")):
                    self._markers[element_id] = "block"
                    return
                self._markers[element_id] = "open"
                return
            if tag == "path":
                if "diamond" in lower_id:
                    self._markers[element_id] = "diamond"
                    return
                if any(token in lower_id for token in ("arrow", "triangle", "arrowhead")):
                    self._markers[element_id] = "block"
                    return
                self._markers[element_id] = "open"
                return
            if tag == "rect" and any(token in lower_id for token in ("square", "box")):
                self._markers[element_id] = "block"
                return

        self._markers[element_id] = "open"

    def _index_filter(self, elem: Element, element_id: str | None) -> None:
        """Cache supported SVG filter primitives as draw.io style fragments."""
        if not element_id:
            return

        for child in elem.iter():
            child_tag = strip_ns(child.tag)
            if child_tag != "feDropShadow":
                continue
            dx = parse_float(child.get("dx", "2"))
            dy = parse_float(child.get("dy", "2"))
            color = normalize_color(child.get("flood-color", "#000000")) or "#000000"
            opacity = int(parse_float(child.get("flood-opacity", "0.5")) * 100)
            self._filters[element_id] = {
                "type": "shadow",
                "dx": dx,
                "dy": dy,
                "color": color,
                "opacity": opacity,
            }
            return

    def get_element(self, ref_id: str) -> Element | None:
        """Return an indexed element by ID for `<use>` or other internal references."""
        return self._elements.get(ref_id)

    def resolve_fill(self, fill_str: str | None) -> tuple[str | None, GradientStyle | None]:
        """Resolve `url(#id)` paint references into a fallback color plus gradient metadata."""
        if not fill_str:
            return fill_str, None

        match = re.match(r"url\(#([^)]+)\)", fill_str)
        if match:
            gradient = self._gradients.get(match.group(1))
            if gradient:
                return gradient["color"], gradient
        return fill_str, None

    def referenced_tag(self, paint_or_ref: str | None) -> str | None:
        """Return the tag name referenced by a local ``url(#id)`` fragment, if known."""
        if not paint_or_ref:
            return None
        match = re.match(r"url\(#([^)]+)\)", paint_or_ref)
        if not match:
            return None
        elem = self._elements.get(match.group(1))
        return strip_ns(elem.tag) if elem is not None else None

    def resolve_marker(self, marker_str: str | None) -> str:
        """Return the nearest draw.io arrow name for an SVG marker reference."""
        if not marker_str:
            return "none"
        match = re.match(r"url\(#([^)]+)\)", marker_str)
        if match:
            return self._markers.get(match.group(1), "open")
        return "none"

    def resolve_custom_marker_shape(self, marker_str: str | None) -> str | None:
        """Return a simple endpoint-shape marker when the marker is not a native draw.io arrow."""
        if not marker_str or self.resolve_marker(marker_str) != "open":
            return None
        match = re.match(r"url\(#([^)]+)\)", marker_str)
        if not match:
            return None
        marker = self._elements.get(match.group(1))
        if marker is None:
            return None
        return _simple_marker_shape(marker)

    def resolve_filter_entries(self, filter_str: str | None) -> list[tuple[str, str | int]]:
        """Convert a supported SVG filter reference into ordered draw.io style entries."""
        if not filter_str:
            return []

        match = re.match(r"url\(#([^)]+)\)", filter_str)
        if not match:
            return []

        shadow = self._filters.get(match.group(1))
        if shadow and shadow["type"] == "shadow":
            return [
                ("shadow", 1),
                ("shadowColor", shadow["color"]),
                ("shadowOpacity", shadow["opacity"]),
                ("shadowOffsetX", f"{shadow['dx']:.0f}"),
                ("shadowOffsetY", f"{shadow['dy']:.0f}"),
            ]
        return []

    def supports_filter(self, filter_str: str | None) -> bool:
        """Return whether a filter reference resolves to a supported draw.io approximation."""
        if not filter_str:
            return True
        return bool(self.resolve_filter_entries(filter_str))

    def resolve_filter(self, filter_str: str | None) -> str:
        """Convert a supported SVG filter reference into draw.io style fragments."""
        return "".join(f"{key}={value};" for key, value in self.resolve_filter_entries(filter_str))


def _simple_marker_shape(marker: Element) -> str | None:
    """Infer a simple editable endpoint shape from a marker definition."""
    marker_id = (marker.get("id") or "").lower()
    for child in marker:
        tag = strip_ns(child.tag)
        if tag == "circle":
            return "ellipse"
        if tag == "rect":
            return "square"
        if tag == "polygon":
            coords = _POINT_RE.findall(child.get("points", ""))
            point_count = len(coords) // 2
            if point_count == 3:
                return "triangle"
            if point_count == 4:
                return "diamond"
        if tag == "path":
            if "diamond" in marker_id:
                return "diamond"
            if any(token in marker_id for token in ("triangle", "arrow", "arrowhead")):
                return "triangle"
    return None
