"""Draw.io stencil serialization helpers for parsed SVG paths."""

from __future__ import annotations

import functools
import zlib
from base64 import b64encode
from collections.abc import Sequence
from urllib.parse import quote

from .path_parser import path_commands
from .path_types import PathCommand
from .style_builder import StyleBuilder

_URI_SAFE = "-_.!~*'()"


def commands_to_stencil_path(
    commands: Sequence[PathCommand],
    ox: float,
    oy: float,
    width: float,
    height: float,
) -> str:
    """Serialize path commands into draw.io stencil XML path nodes."""

    def norm_x(x: float) -> float:
        return (x - ox) / width * 100 if width else 0.0

    def norm_y(y: float) -> float:
        return (y - oy) / height * 100 if height else 0.0

    parts: list[str] = []
    for kind, points in commands:
        if kind == "move":
            x, y = points[0]
            parts.append(f'<move x="{norm_x(x):.2f}" y="{norm_y(y):.2f}"/>')
        elif kind == "line":
            x, y = points[0]
            parts.append(f'<line x="{norm_x(x):.2f}" y="{norm_y(y):.2f}"/>')
        elif kind == "curve":
            (x1, y1), (x2, y2), (x3, y3) = points
            parts.append(
                f'<curve x1="{norm_x(x1):.2f}" y1="{norm_y(y1):.2f}"'
                f' x2="{norm_x(x2):.2f}" y2="{norm_y(y2):.2f}"'
                f' x3="{norm_x(x3):.2f}" y3="{norm_y(y3):.2f}"/>'
            )
        elif kind == "close":
            parts.append("<close/>")
    return "".join(parts)


def path_to_stencil(path_data: str | None, ox: float, oy: float, width: float, height: float) -> str:
    """Convert an SVG path string into draw.io stencil XML path content."""
    return commands_to_stencil_path(path_commands(path_data), ox, oy, width, height)


@functools.lru_cache(maxsize=256)
def _compress_drawio_text(text: str) -> str:
    """Encode inline draw.io payloads using the diagrams.net compression format."""
    data = quote(text, safe=_URI_SAFE).encode("utf-8")
    compressor = zlib.compressobj(level=9, wbits=-15)
    compressed = compressor.compress(data) + compressor.flush()
    return b64encode(compressed).decode("ascii")


def make_stencil_style_from_xml(
    xml: str,
    fill: str | None,
    stroke: str | None,
    stroke_width: float,
    opacity: int,
) -> str | None:
    """Build a draw.io stencil style string from raw stencil XML."""
    if not xml:
        return None
    encoded = _compress_drawio_text(xml)
    return (
        StyleBuilder()
        .add("shape", f"stencil({encoded})")
        .add("fillColor", fill)
        .add("strokeColor", stroke)
        .add("strokeWidth", stroke_width)
        .add("opacity", opacity)
        .build()
    )


def make_stencil_style_from_commands(
    commands: Sequence[PathCommand],
    ox: float,
    oy: float,
    width: float,
    height: float,
    fill: str | None,
    stroke: str | None,
    stroke_width: float,
    opacity: int,
    fill_rule: str = "nonzero",
    linecap: str = "flat",
    linejoin: str = "miter",
) -> str | None:
    """Build a draw.io stencil style from already parsed path commands."""
    stencil_path = commands_to_stencil_path(commands, ox, oy, width, height)
    if not stencil_path:
        return None
    if fill_rule == "evenodd":
        path_elem = f'<path fillrule="evenodd">{stencil_path}</path>'
    else:
        path_elem = f"<path>{stencil_path}</path>"

    paint = "stroke" if fill == "none" else "fillstroke"
    xml = (
        f'<shape w="100" h="100" aspect="variable" strokewidth="inherit"'
        f' strokelinecap="{linecap}" strokelinejoin="{linejoin}">'
        f"<background>{path_elem}<{paint}/></background></shape>"
    )
    return make_stencil_style_from_xml(xml, fill, stroke, stroke_width, opacity)


def make_stencil_style(
    path_data: str | None,
    ox: float,
    oy: float,
    width: float,
    height: float,
    fill: str | None,
    stroke: str | None,
    stroke_width: float,
    opacity: int,
    fill_rule: str = "nonzero",
    linecap: str = "flat",
    linejoin: str = "miter",
) -> str | None:
    """Build a draw.io stencil style string from an SVG path string."""
    return make_stencil_style_from_commands(
        path_commands(path_data),
        ox,
        oy,
        width,
        height,
        fill,
        stroke,
        stroke_width,
        opacity,
        fill_rule,
        linecap,
        linejoin,
    )
