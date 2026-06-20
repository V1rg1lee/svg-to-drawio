"""Lightweight post-conversion document hooks: page background and a notes legend.

Deliberately scoped to document-level/native draw.io attributes (the `mxGraphModel.background`
attribute and a plain legend layer) rather than rewriting every cell's style string into a
visual "theme" - that would require parsing and rewriting every emitted style, which is
invasive and fragile against already-custom styles.
"""

from __future__ import annotations

from dataclasses import dataclass
from xml.sax.saxutils import escape

from .diagnostics import ConversionReport
from .drawio_model import Cell, Geometry, group_bbox, layer_cell

_LEGEND_MARGIN = 30.0
_LEGEND_HEIGHT = 90.0
_LEGEND_WIDTH = 320.0
_LEGEND_STYLE = (
    "text;html=1;align=left;verticalAlign=top;whiteSpace=wrap;rounded=0;"
    "fillColor=#FFF9C4;strokeColor=#D4AC0D;spacing=8;"
)


@dataclass(frozen=True)
class PostProcessOptions:
    """User-configurable post-conversion document hooks."""

    legend: bool = False
    background: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Serialize the options into a JSON-friendly dictionary (used for cache signatures)."""
        return {
            "legend": self.legend,
            "background": self.background,
        }

    def is_noop(self) -> bool:
        """Return whether applying these options would leave the cells unchanged."""
        return not self.legend


def _legend_text(report: ConversionReport, title: str) -> str:
    """Build the multi-line HTML body summarizing one conversion report."""
    lines = [
        f"<b>{escape(title)}</b>",
        f"Compatibility score: {report.compatibility_score}/100",
        f"Warnings: {report.warning_count} &nbsp; Fallbacks: {report.fallback_count}",
    ]
    if report.source_path:
        lines.append(escape(report.source_path))
    return "<br>".join(lines)


def _make_legend_cells(cells: list[Cell], report: ConversionReport, title: str, *, next_id: int) -> list[Cell]:
    """Build a "Notes" layer plus one summary text cell, placed below the existing content."""
    bbox = group_bbox(cells)
    x, y, _width, height = bbox
    legend_y = y + height + _LEGEND_MARGIN

    layer = layer_cell(str(next_id), "Notes")
    body = Cell(
        id=str(next_id + 1),
        value=_legend_text(report, title),
        style=_LEGEND_STYLE,
        parent=layer.id,
        vertex=True,
        geometry=Geometry(x=x, y=legend_y, width=_LEGEND_WIDTH, height=_LEGEND_HEIGHT),
    )
    return [layer, body]


def apply_post_process(
    cells: list[Cell],
    report: ConversionReport,
    *,
    options: PostProcessOptions,
    title: str,
) -> list[Cell]:
    """Apply the notes legend (if enabled) to a finished cell list; returns a new list."""
    if options.is_noop():
        return cells

    result = list(cells)
    existing_ids = {int(cell.id) for cell in result if cell.id.isdigit()}
    next_id = max(existing_ids, default=1) + 1
    result.extend(_make_legend_cells(result, report, title, next_id=next_id))
    return result
