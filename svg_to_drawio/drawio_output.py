"""XML serialization helpers for the final draw.io document."""

from __future__ import annotations

from collections.abc import Iterable
from xml.sax.saxutils import escape

from .drawio_model import Cell, cells_to_xml


def make_xml(cells: Iterable[Cell], title: str = "Diagram") -> str:
    """Serialize the draw.io document wrapper around the generated cells."""
    body = cells_to_xml(cells)
    safe_title = escape(title, {'"': "&quot;"})
    return (
        "<mxfile>\n"
        f'  <diagram name="{safe_title}">\n'
        "    <mxGraphModel>\n"
        "      <root>\n"
        '        <mxCell id="0"/>\n'
        '        <mxCell id="1" parent="0"/>\n'
        f"{body}\n"
        "      </root>\n"
        "    </mxGraphModel>\n"
        "  </diagram>\n"
        "</mxfile>\n"
    )
