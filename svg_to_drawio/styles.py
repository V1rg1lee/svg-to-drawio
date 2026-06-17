"""Visual style extraction helpers shared by the element emitters."""

from __future__ import annotations

import re
from typing import TypedDict
from xml.etree.ElementTree import Element

from .utils import parse_float, parse_length


class VisualStyle(TypedDict):
    """Normalized drawing properties extracted from SVG/CSS styles."""

    fill: str | None
    stroke: str | None
    stroke_width: float
    opacity: float
    fill_opacity: float
    stroke_opacity: float
    font_size: float
    font_family: str
    text_anchor: str
    text_fill: str | None
    text_opacity: float
    font_weight: str
    font_style_v: str
    linecap: str
    linejoin: str
    dash_style: str
    marker_start: str | None
    marker_end: str | None
    marker_mid: str | None
    filter: str | None
    fill_rule: str
    text_decoration: str
    baseline_shift: str


class GradientStyle(TypedDict):
    """Resolved SVG gradient information used by native and approximated emitters."""

    color: str
    color2: str
    direction: str
    kind: str
    stops: list[GradientStop]


class GradientStop(TypedDict):
    """One normalized SVG gradient stop."""

    offset: float
    color: str


_LINECAP: dict[str, str] = {"butt": "flat", "round": "round", "square": "square"}
_LINEJOIN: dict[str, str] = {"miter": "miter", "round": "round", "bevel": "bevel"}
_RGBA_RE = re.compile(
    r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)"
    r"(?:\s*,\s*([^)]+))?\s*\)",
    re.IGNORECASE,
)
_HSL_RE = re.compile(
    r"hsla?\(\s*([\d.]+)\s*,\s*([\d.]+)%\s*,\s*([\d.]+)%"
    r"(?:\s*,\s*([^)]+))?\s*\)",
    re.IGNORECASE,
)


def _hsl_to_rgb(hue: float, saturation: float, lightness: float) -> tuple[int, int, int]:
    """Convert an HSL color value to an RGB tuple."""
    hue = hue % 360
    chroma = (1 - abs(2 * lightness - 1)) * saturation
    second = chroma * (1 - abs((hue / 60) % 2 - 1))
    match = lightness - chroma / 2

    if hue < 60:
        red, green, blue = chroma, second, 0.0
    elif hue < 120:
        red, green, blue = second, chroma, 0.0
    elif hue < 180:
        red, green, blue = 0.0, chroma, second
    elif hue < 240:
        red, green, blue = 0.0, second, chroma
    elif hue < 300:
        red, green, blue = second, 0.0, chroma
    else:
        red, green, blue = chroma, 0.0, second

    return (
        int((red + match) * 255),
        int((green + match) * 255),
        int((blue + match) * 255),
    )


def _clamp01(value: float) -> float:
    """Clamp a numeric value to the inclusive range `[0, 1]`."""
    return max(0.0, min(1.0, value))


def _parse_alpha(value: str | None) -> float:
    """Parse a CSS alpha channel value expressed either as a fraction or a percentage."""
    if value is None:
        return 1.0

    text = str(value).strip()
    if not text:
        return 1.0
    if text.endswith("%"):
        return _clamp01(parse_float(text[:-1]) / 100.0)
    return _clamp01(parse_float(text))


def _paint_with_alpha(color: str | None) -> tuple[str | None, float]:
    """Normalize a paint value and split its embedded alpha channel when present."""
    if not color:
        return None, 1.0

    text = str(color).strip()
    if text.lower() in ("none", "transparent"):
        return "none", 1.0

    rgba_match = _RGBA_RE.match(text)
    if rgba_match:
        normalized = f"#{int(rgba_match.group(1)):02x}{int(rgba_match.group(2)):02x}{int(rgba_match.group(3)):02x}"
        return normalized, _parse_alpha(rgba_match.group(4))

    hsl_match = _HSL_RE.match(text)
    if hsl_match:
        rgb = _hsl_to_rgb(
            float(hsl_match.group(1)),
            float(hsl_match.group(2)) / 100,
            float(hsl_match.group(3)) / 100,
        )
        normalized = f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
        return normalized, _parse_alpha(hsl_match.group(4))

    short_hex_match = re.match(r"^#([0-9a-fA-F]{3})$", text)
    if short_hex_match:
        short_hex = short_hex_match.group(1)
        return "#{0}{0}{1}{1}{2}{2}".format(short_hex[0], short_hex[1], short_hex[2]), 1.0

    # 4-digit hex: #rgba  →  expand to #rrggbb + alpha
    if re.match(r"^#[0-9a-fA-F]{4}$", text):
        r_h, g_h, b_h, a_h = text[1], text[2], text[3], text[4]
        return f"#{r_h}{r_h}{g_h}{g_h}{b_h}{b_h}", _clamp01(int(a_h + a_h, 16) / 255.0)

    # 8-digit hex: #rrggbbaa  →  extract alpha from last two digits
    if re.match(r"^#[0-9a-fA-F]{8}$", text):
        return f"#{text[1:7].lower()}", _clamp01(int(text[7:9], 16) / 255.0)

    return text, 1.0


def opacity_pct(value: float) -> int:
    """Convert a normalized opacity value to draw.io's 0-100 integer scale."""
    return int(round(_clamp01(value) * 100))


def normalize_color(color: str | None) -> str | None:
    """Normalize a CSS/SVG color string without preserving its alpha channel."""
    return _paint_with_alpha(color)[0]


def get_visual(element: Element, computed_css: dict[str, str] | None = None) -> VisualStyle:
    """Extract the resolved visual properties needed by the emitters.

    *computed_css* should contain the already-resolved CSS cascade for *element*. Direct SVG
    presentation attributes are still consulted as a fallback because some SVGs use a mix of
    inline attributes and stylesheet rules.
    """
    css = computed_css or {}

    def get_attr(name: str, default: str | None = None) -> str | None:
        return css.get(name) or element.get(name) or default

    def resolve_color(value: str | None) -> str | None:
        """Resolve `currentColor` against the inherited `color` property."""
        if value and value.strip().lower() == "currentcolor":
            return css.get("color") or element.get("color") or "#000000"
        return value

    dash_array = get_attr("stroke-dasharray")
    dash_style = ""
    if dash_array and dash_array.lower() not in ("none", "0"):
        numbers = re.findall(r"[\d.]+", dash_array)
        if numbers:
            dash_style = "dashed=1;dashPattern={};".format(" ".join(numbers))

    fill_raw = resolve_color(get_attr("fill", "none"))
    stroke_raw = resolve_color(get_attr("stroke", "none"))
    text_fill_raw = resolve_color(get_attr("fill", "#000000"))

    fill, fill_alpha = _paint_with_alpha(fill_raw)
    stroke, stroke_alpha = _paint_with_alpha(stroke_raw)
    text_fill, text_alpha = _paint_with_alpha(text_fill_raw)

    opacity = _clamp01(parse_float(get_attr("opacity", "1")))
    fill_opacity = _clamp01(parse_float(get_attr("fill-opacity", "1")) * fill_alpha)
    stroke_opacity = _clamp01(parse_float(get_attr("stroke-opacity", "1")) * stroke_alpha)
    text_opacity = _clamp01(parse_float(get_attr("fill-opacity", "1")) * text_alpha)

    return {
        "fill": fill,
        "stroke": stroke,
        "stroke_width": parse_length(get_attr("stroke-width", "1")),
        "opacity": opacity,
        "fill_opacity": fill_opacity,
        "stroke_opacity": stroke_opacity,
        "font_size": parse_float(re.sub(r"[^\d.]", "", get_attr("font-size", "12") or "12")),
        "font_family": get_attr("font-family", "Helvetica") or "Helvetica",
        "text_anchor": get_attr("text-anchor", "start") or "start",
        "text_fill": text_fill,
        "text_opacity": text_opacity,
        "font_weight": get_attr("font-weight", "normal") or "normal",
        "font_style_v": get_attr("font-style", "normal") or "normal",
        "linecap": _LINECAP.get(get_attr("stroke-linecap", "butt") or "butt", "flat"),
        "linejoin": _LINEJOIN.get(get_attr("stroke-linejoin", "miter") or "miter", "miter"),
        "dash_style": dash_style,
        "marker_start": get_attr("marker-start"),
        "marker_end": get_attr("marker-end"),
        "marker_mid": get_attr("marker-mid"),
        "filter": get_attr("filter"),
        "fill_rule": get_attr("fill-rule", "nonzero") or "nonzero",
        "text_decoration": get_attr("text-decoration", "none") or "none",
        "baseline_shift": get_attr("baseline-shift", "0") or "0",
    }


def gradient_entries(gradient: GradientStyle | None) -> list[tuple[str, str | int]]:
    """Return the draw.io style entries for a resolved SVG gradient."""
    if not gradient:
        return []
    return [
        ("fillStyle", 1),
        ("gradientColor", gradient["color2"]),
        ("gradientDirection", gradient["direction"]),
    ]


def gradient_style(gradient: GradientStyle | None) -> str:
    """Build the draw.io style fragment for a resolved SVG gradient."""
    return "".join(f"{key}={value};" if value is not True else f"{key};" for key, value in gradient_entries(gradient))


def font_style_flag(style: VisualStyle) -> int:
    """Return draw.io's font-style bitmask for the given text style."""
    bold = 1 if style.get("font_weight") in ("bold", "700", "800", "900") else 0
    italic = 2 if style.get("font_style_v") == "italic" else 0
    text_decoration = style.get("text_decoration", "none") or "none"
    underline = 4 if "underline" in text_decoration else 0
    strikethrough = 8 if "line-through" in text_decoration else 0
    return bold | italic | underline | strikethrough
