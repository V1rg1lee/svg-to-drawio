"""In-memory draw.io cell model used before XML serialization."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from xml.sax.saxutils import escape


def _xml_attr(value: object) -> str:
    """Escape a value for use inside an XML attribute."""
    return escape(str(value), {'"': "&quot;"})


def _fmt_num(value: float | int) -> str:
    """Format numeric geometry values with stable two-decimal precision."""
    return f"{float(value):.2f}"


@dataclass
class Point:
    """A 2D point used inside draw.io geometry structures."""

    x: float
    y: float

    def shift(self, dx: float, dy: float) -> None:
        """Translate the point by subtracting the given offsets."""
        self.x -= dx
        self.y -= dy

    def to_xml(self, indent: str = "        ", role: str | None = None) -> str:
        """Serialize the point as an `<mxPoint>` node."""
        attrs = [f'x="{_fmt_num(self.x)}"', f'y="{_fmt_num(self.y)}"']
        if role:
            attrs.append(f'as="{_xml_attr(role)}"')
        return f"{indent}<mxPoint {' '.join(attrs)}/>"


@dataclass
class Geometry:
    """Geometry data for a draw.io cell."""

    x: float | None = None
    y: float | None = None
    width: float | None = None
    height: float | None = None
    relative: bool = False
    source_point: Point | None = None
    target_point: Point | None = None
    points: list[Point] = field(default_factory=list)

    def bbox(self) -> tuple[float, float, float, float] | None:
        """Return the bounding box covered by the geometry."""
        pts: list[tuple[float, float]] = []
        if None not in (self.x, self.y, self.width, self.height):
            assert self.x is not None and self.y is not None
            assert self.width is not None and self.height is not None
            pts.append((self.x, self.y))
            pts.append((self.x + self.width, self.y + self.height))
        for point in self.iter_points():
            pts.append((point.x, point.y))
        if not pts:
            return None
        xs = [point[0] for point in pts]
        ys = [point[1] for point in pts]
        return min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)

    def iter_points(self) -> list[Point]:
        """Return all point-like children in a predictable order."""
        points: list[Point] = []
        if self.source_point is not None:
            points.append(self.source_point)
        if self.target_point is not None:
            points.append(self.target_point)
        points.extend(self.points)
        return points

    def shift(self, dx: float, dy: float) -> None:
        """Translate the geometry by subtracting the given offsets."""
        if self.x is not None:
            self.x -= dx
        if self.y is not None:
            self.y -= dy
        for point in self.iter_points():
            point.shift(dx, dy)

    def to_xml(self, indent: str = "      ") -> str:
        """Serialize the geometry as an `<mxGeometry>` node."""
        attrs: list[str] = []
        if self.x is not None:
            attrs.append(f'x="{_fmt_num(self.x)}"')
        if self.y is not None:
            attrs.append(f'y="{_fmt_num(self.y)}"')
        if self.width is not None:
            attrs.append(f'width="{_fmt_num(self.width)}"')
        if self.height is not None:
            attrs.append(f'height="{_fmt_num(self.height)}"')
        if self.relative:
            attrs.append('relative="1"')
        attrs.append('as="geometry"')

        children: list[str] = []
        if self.source_point is not None:
            children.append(self.source_point.to_xml(indent + "  ", role="sourcePoint"))
        if self.target_point is not None:
            children.append(self.target_point.to_xml(indent + "  ", role="targetPoint"))
        if self.points:
            points_xml = "\n".join(point.to_xml(indent + "    ") for point in self.points)
            children.append(f'{indent}  <Array as="points">\n{points_xml}\n{indent}  </Array>')

        if not children:
            return f"{indent}<mxGeometry {' '.join(attrs)}/>"

        children_xml = "\n".join(children)
        return f"{indent}<mxGeometry {' '.join(attrs)}>\n{children_xml}\n{indent}</mxGeometry>"


@dataclass
class Cell:
    """A draw.io cell, either a vertex or an edge."""

    id: str
    value: str = ""
    style: str = ""
    parent: str = "1"
    vertex: bool = False
    edge: bool = False
    geometry: Geometry | None = None

    def bbox(self) -> tuple[float, float, float, float] | None:
        """Return the bounding box of the cell geometry."""
        if self.geometry is None:
            return None
        return self.geometry.bbox()

    def shift(self, dx: float, dy: float) -> None:
        """Translate the cell geometry by subtracting the given offsets."""
        if self.geometry is not None:
            self.geometry.shift(dx, dy)

    def to_xml(self, indent: str = "    ") -> str:
        """Serialize the cell as an `<mxCell>` node."""
        attrs = [
            f'id="{_xml_attr(self.id)}"',
            f'value="{_xml_attr(self.value)}"',
            f'style="{_xml_attr(self.style)}"',
            f'parent="{_xml_attr(self.parent)}"',
        ]
        if self.vertex:
            attrs.append('vertex="1"')
        if self.edge:
            attrs.append('edge="1"')
        if self.geometry is None:
            return f"{indent}<mxCell {' '.join(attrs)}/>"
        return f"{indent}<mxCell {' '.join(attrs)}>\n{self.geometry.to_xml(indent + '  ')}\n{indent}</mxCell>"


def vertex_cell(
    cell_id: str,
    style: str,
    geometry: Geometry,
    value: str = "",
    parent: str = "1",
) -> Cell:
    """Construct a vertex cell."""
    return Cell(id=cell_id, value=value, style=style, parent=parent, vertex=True, geometry=geometry)


def edge_cell(
    cell_id: str,
    style: str,
    geometry: Geometry,
    value: str = "",
    parent: str = "1",
) -> Cell:
    """Construct an edge cell."""
    return Cell(id=cell_id, value=value, style=style, parent=parent, edge=True, geometry=geometry)


def layer_cell(cell_id: str, label: str = "") -> Cell:
    """Construct a draw.io layer cell (no geometry, always a direct child of the diagram root)."""
    return Cell(id=cell_id, value=label, style="", parent="1", vertex=True)


def group_bbox(cells: Iterable[Cell]) -> tuple[float, float, float, float]:
    """Return the bounding box that contains all given cells."""
    points: list[tuple[float, float]] = []
    for cell in cells:
        bbox = cell.bbox()
        if bbox:
            x, y, width, height = bbox
            points.append((x, y))
            points.append((x + width, y + height))
    if not points:
        return 0.0, 0.0, 1.0, 1.0
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    x = min(xs)
    y = min(ys)
    width = max(xs) - x or 1.0
    height = max(ys) - y or 1.0
    return x, y, width, height


def shift_cells(cells: Iterable[Cell], dx: float, dy: float) -> None:
    """Translate every cell by subtracting the given offsets."""
    for cell in cells:
        cell.shift(dx, dy)


def cells_to_xml(cells: Iterable[Cell], indent: str = "    ") -> str:
    """Serialize a sequence of cells into a newline-separated XML block."""
    return "\n".join(cell.to_xml(indent) for cell in cells)
