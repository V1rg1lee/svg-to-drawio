"""Shared parsing and style helpers used across the converter."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote, urlparse
from xml.etree.ElementTree import Element

_UNIT_TO_PX: dict[str, float] = {
    "px": 1.0,
    "pt": 4.0 / 3.0,
    "pc": 16.0,
    "in": 96.0,
    "cm": 96.0 / 2.54,
    "mm": 96.0 / 25.4,
}

_SAFE_LINK_SCHEMES = frozenset({"http", "https", "mailto", "ftp", "ftps", "tel", "sms"})
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x1f\x7f-\x9f]")


def strip_ns(tag: str) -> str:
    """Remove an XML namespace prefix from a tag name when one is present."""
    return tag.split("}", 1)[1] if "}" in tag else tag


def parse_float(value: Any, default: float = 0.0) -> float:
    """Parse a loosely formatted numeric string into a float.

    The parser intentionally strips non-numeric suffixes such as `px` so the helper can be
    used on raw SVG attributes without each caller reimplementing the cleanup.
    """
    if value is None:
        return default
    try:
        cleaned = re.sub(r"[^\d.eE+\-]", "", str(value))
        return float(cleaned) if cleaned else default
    except ValueError:
        return default


def parse_length(value: Any, default: float = 0.0) -> float:
    """Parse an SVG length into CSS pixels.

    Supported absolute units are `px`, `pt`, `pc`, `in`, `cm`, and `mm`. Unsupported or
    malformed values fall back to *default*.
    """
    if value is None:
        return default
    text = str(value).strip()
    for unit, factor in _UNIT_TO_PX.items():
        if text.endswith(unit):
            try:
                return float(text[: -len(unit)].strip()) * factor
            except ValueError:
                return default
    return parse_float(value, default)


def parse_style_attr(style: str | None) -> dict[str, str]:
    """Parse an inline CSS `style` attribute into a normalized dictionary."""
    result: dict[str, str] = {}
    for item in (style or "").split(";"):
        if ":" not in item:
            continue
        key, value = item.split(":", 1)
        result[key.strip().lower()] = value.strip()
    return result


def format_style_attr(style_map: dict[str, str] | None) -> str:
    """Serialize a normalized style dictionary into a stable inline CSS string."""
    if not style_map:
        return ""
    return ";".join(f"{key}:{value}" for key, value in sorted(style_map.items()) if value)


def get_tooltip(element: Element) -> str:
    """Return the text content of the first child `<title>` element, if any."""
    for child in element:
        if strip_ns(child.tag) == "title":
            return (child.text or "").strip()
    return ""


def tooltip_value(element: Element) -> str | None:
    """Return a sanitized tooltip value suitable for a draw.io style entry."""
    tooltip = get_tooltip(element)
    if not tooltip:
        return None
    return " ".join(tooltip.split()).replace(";", ",")


def tooltip_style(element: Element) -> str:
    """Return a draw.io `tooltip=...;` style fragment for an SVG element."""
    tooltip = tooltip_value(element)
    if tooltip is None:
        return ""
    return f"tooltip={tooltip};"


def link_value(url: str | None) -> str | None:
    """Return a safe draw.io link value or None for unsupported URLs."""
    if not url:
        return None

    url = url.strip()
    if not url or _CONTROL_CHAR_RE.search(url):
        return None

    try:
        parsed = urlparse(url)
    except ValueError:
        return None

    if parsed.scheme and parsed.scheme.lower() not in _SAFE_LINK_SCHEMES:
        return None

    return quote(url, safe="/:#?&=%+,-._~[]@!$'()*")


def link_style(converter: Any) -> str:
    """Return a draw.io `link=...;` style fragment for the active converter context."""
    url = getattr(converter, "link_url", getattr(converter, "_link_url", ""))
    safe = link_value(url)
    if safe is None:
        return ""
    return f"link={safe};"
