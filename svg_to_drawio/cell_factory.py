"""Factory helpers for constructing draw.io cells and geometries."""

from __future__ import annotations

from collections.abc import Sequence

from .drawio_model import Cell, Geometry, Point, edge_cell, layer_cell, vertex_cell
from .element_geometry import BoundsBox
from .emitter_context import EmitterContext

Point2D = tuple[float, float]


def bounds_geometry(x: float, y: float, width: float, height: float) -> Geometry:
    """Build a rectangular draw.io geometry."""
    return Geometry(x=x, y=y, width=width, height=height)


def edge_geometry(
    source: Point2D,
    target: Point2D,
    waypoints: Sequence[Point2D] = (),
) -> Geometry:
    """Build a relative edge geometry from source, target, and optional waypoints."""
    return Geometry(
        relative=True,
        source_point=Point(source[0], source[1]),
        target_point=Point(target[0], target[1]),
        points=[Point(px, py) for px, py in waypoints],
    )


def make_vertex(
    ctx: EmitterContext,
    style: str,
    geometry: Geometry,
    *,
    value: str = "",
    cell_id: str | None = None,
    parent_id: str | None = None,
) -> Cell:
    """Build a vertex cell using the active context defaults unless overridden."""
    return vertex_cell(
        cell_id or ctx.next_id(),
        style,
        geometry,
        value=value,
        parent=parent_id or ctx.parent_id,
    )


def make_bounds_vertex(
    ctx: EmitterContext,
    style: str,
    x: float,
    y: float,
    width: float,
    height: float,
    *,
    value: str = "",
    cell_id: str | None = None,
    parent_id: str | None = None,
) -> Cell:
    """Build a vertex cell from simple rectangular bounds."""
    return make_vertex(
        ctx,
        style,
        bounds_geometry(x, y, width, height),
        value=value,
        cell_id=cell_id,
        parent_id=parent_id,
    )


def make_box_vertex(
    ctx: EmitterContext,
    style: str,
    box: BoundsBox,
    *,
    value: str = "",
    cell_id: str | None = None,
    parent_id: str | None = None,
) -> Cell:
    """Build a vertex cell directly from a `BoundsBox` helper object."""
    return make_bounds_vertex(
        ctx,
        style,
        box.x,
        box.y,
        box.width,
        box.height,
        value=value,
        cell_id=cell_id,
        parent_id=parent_id,
    )


def make_layer_cell(ctx: EmitterContext, label: str = "", cell_id: str | None = None) -> Cell:
    """Build a draw.io layer cell with no geometry at the diagram root."""
    return layer_cell(cell_id or ctx.next_id(), label)


def make_edge(
    ctx: EmitterContext,
    style: str,
    source: Point2D,
    target: Point2D,
    *,
    waypoints: Sequence[Point2D] = (),
    value: str = "",
    cell_id: str | None = None,
    parent_id: str | None = None,
) -> Cell:
    """Build an edge cell from source/target points and optional waypoints."""
    return edge_cell(
        cell_id or ctx.next_id(),
        style,
        edge_geometry(source, target, waypoints),
        value=value,
        parent=parent_id or ctx.parent_id,
    )
