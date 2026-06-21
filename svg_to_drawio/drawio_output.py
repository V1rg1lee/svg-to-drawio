"""XML serialization helpers for the final draw.io document."""

from __future__ import annotations

from collections.abc import Iterable
from xml.sax.saxutils import escape

from .drawio_model import Cell, cells_to_xml


def _graph_model_attrs(background: str | None) -> str:
    """Build the `<mxGraphModel>` opening tag attributes, including an optional background."""
    if not background:
        return "<mxGraphModel>"
    safe_background = escape(background, {'"': "&quot;"})
    return f'<mxGraphModel background="{safe_background}">'


def _diagram_xml(title: str, cells: Iterable[Cell], background: str | None) -> str:
    """Serialize one `<diagram>` block (page) containing the given cells."""
    body = cells_to_xml(cells)
    safe_title = escape(title, {'"': "&quot;"})
    return (
        f'  <diagram name="{safe_title}">\n'
        f"    {_graph_model_attrs(background)}\n"
        "      <root>\n"
        '        <mxCell id="0"/>\n'
        '        <mxCell id="1" parent="0"/>\n'
        f"{body}\n"
        "      </root>\n"
        "    </mxGraphModel>\n"
        "  </diagram>"
    )


def make_xml(cells: Iterable[Cell], title: str = "Diagram", *, background: str | None = None) -> str:
    """Serialize the draw.io document wrapper around the generated cells."""
    return f"<mxfile>\n{_diagram_xml(title, cells, background)}\n</mxfile>\n"


def make_multi_diagram_xml(pages: Iterable[tuple[str, Iterable[Cell]]], *, background: str | None = None) -> str:
    """Serialize several independent pages into one `<mxfile>` with one `<diagram>` each.

    Each page gets its own `<mxGraphModel>/<root>`, so cell ids only need to be unique
    within their own page - exactly how each `Converter` run already numbers its cells.
    """
    diagrams = "\n".join(_diagram_xml(title, cells, background) for title, cells in pages)
    return f"<mxfile>\n{diagrams}\n</mxfile>\n"
