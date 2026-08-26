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
    """Return a sanitized link value suitable for a draw.io style entry.
    
    This function validates URL schemes to prevent injection of dangerous protocols
    such as javascript:, data:, file:, and other potentially harmful schemes.
    Only safe schemes (http, https, mailto, ftp, ftps, tel, sms) and relative URLs
    are permitted. URLs with dangerous or unrecognized schemes are rejected.
    """
    if not url:
        return None
    
    # Normalize whitespace and strip control characters that could be used for obfuscation
    url = url.strip()
    # Remove control characters (0x00-0x1F, 0x7F-0x9F) that could be used to bypass validation
    url = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', url)
    
    if not url:
        return None
    
    # Parse the URL to extract the scheme
    try:
        parsed = urlparse(url)
    except Exception:
        # If URL parsing fails, reject the URL
        return None
    
    # Define allowlist of safe URL schemes
    # These are schemes that are safe for use in draw.io links
    SAFE_SCHEMES = frozenset(['http', 'https', 'mailto', 'ftp', 'ftps', 'tel', 'sms'])
    
    # If there's a scheme, validate it against the allowlist
    if parsed.scheme:
        # Normalize scheme to lowercase for comparison
        scheme_lower = parsed.scheme.lower()
        
        # Reject dangerous schemes
        if scheme_lower not in SAFE_SCHEMES:
            # Dangerous schemes include: javascript, data, file, vbscript, about, etc.
            return None
    
    # For relative URLs (no scheme), allow them as they're resolved relative to the document
    # This includes fragment-only URLs (#anchor), path-relative (./path), etc.
    
    # Percent-encode the URL with a safe character set
    # Note: We preserve URL syntax characters but the scheme has already been validated
    return quote(url, safe="/:#?&=%+,-._~[]@!$'()*")


def link_style(converter: Any) -> str:
    """Return a draw.io `link=...;` style fragment for the active converter context."""
    url = getattr(converter, "link_url", getattr(converter, "_link_url", ""))
    safe = link_value(url)
    if safe is None:
        return ""
    return f"link={safe};"
