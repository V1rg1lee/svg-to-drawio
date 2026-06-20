"""Combine several independently-converted SVGs into one draw.io document."""

from __future__ import annotations

import copy
import math
from collections.abc import Iterable, Sequence

from .drawio_model import Cell, Geometry, group_bbox
from .drawio_output import make_multi_diagram_xml, make_xml

MERGED_DIAGRAM_TITLE = "Merged diagram"
_GRID_GAP = 40.0
_GRID_LABEL_HEIGHT = 30.0
_GRID_LABEL_STYLE = "text;html=1;align=center;verticalAlign=middle;fontStyle=1;"
_GRID_GROUP_STYLE = "group;"

NamedCells = tuple[str, list[Cell]]


def merge_pages(named_cells: Sequence[NamedCells], *, background: str | None = None) -> str:
    """Combine several SVGs into one `.drawio` file with one page per SVG."""
    return make_multi_diagram_xml(named_cells, background=background)


def _remap_cells_for_tile(
    cells: Iterable[Cell], *, prefix: str, wrapper_id: str, origin: tuple[float, float]
) -> list[Cell]:
    """Prefix every id/parent in *cells* and shift root-level geometry into *wrapper_id*'s frame."""
    origin_x, origin_y = origin
    remapped: list[Cell] = []
    for cell in cells:
        is_root_level = cell.parent == "1"
        new_parent = wrapper_id if is_root_level else f"{prefix}{cell.parent}"
        geometry = copy.deepcopy(cell.geometry)
        if geometry is not None and is_root_level:
            geometry.shift(origin_x, origin_y)
        remapped.append(
            Cell(
                id=f"{prefix}{cell.id}",
                value=cell.value,
                style=cell.style,
                parent=new_parent,
                vertex=cell.vertex,
                edge=cell.edge,
                geometry=geometry,
            )
        )
    return remapped


def build_grid_cells(
    named_cells: Sequence[NamedCells],
    *,
    columns: int | None = None,
    gap: float = _GRID_GAP,
) -> list[Cell]:
    """Assemble the labeled grid-of-tiles cell list, without serializing it to XML.

    Exposed separately from `merge_grid` so post-processing (the legend) can be applied to the
    fully assembled grid - including the per-tile wrapper and label cells - before the
    document is serialized.
    """
    if not named_cells:
        return []

    bboxes = [group_bbox(cells) for _title, cells in named_cells]
    tile_width = max(bbox[2] for bbox in bboxes)
    tile_height = max(bbox[3] for bbox in bboxes)
    grid_columns = columns or math.ceil(math.sqrt(len(named_cells)))

    all_cells: list[Cell] = []
    for index, ((title, cells), (bx, by, bw, bh)) in enumerate(zip(named_cells, bboxes)):
        row, col = divmod(index, grid_columns)
        slot_x = col * (tile_width + gap)
        slot_y = row * (tile_height + gap + _GRID_LABEL_HEIGHT)

        prefix = f"m{index}_"
        wrapper_id = f"{prefix}group"
        all_cells.extend(_remap_cells_for_tile(cells, prefix=prefix, wrapper_id=wrapper_id, origin=(bx, by)))
        all_cells.append(
            Cell(
                id=wrapper_id,
                style=_GRID_GROUP_STYLE,
                parent="1",
                vertex=True,
                geometry=Geometry(x=slot_x, y=slot_y + _GRID_LABEL_HEIGHT, width=bw, height=bh),
            )
        )
        all_cells.append(
            Cell(
                id=f"{prefix}label",
                value=title,
                style=_GRID_LABEL_STYLE,
                parent="1",
                vertex=True,
                geometry=Geometry(x=slot_x, y=slot_y, width=tile_width, height=_GRID_LABEL_HEIGHT),
            )
        )

    return all_cells


def merge_grid(
    named_cells: Sequence[NamedCells],
    *,
    columns: int | None = None,
    gap: float = _GRID_GAP,
    background: str | None = None,
) -> str:
    """Combine several SVGs into one `.drawio` page, laid out as a labeled grid of tiles."""
    cells = build_grid_cells(named_cells, columns=columns, gap=gap)
    return make_xml(cells, MERGED_DIAGRAM_TITLE, background=background)
