"""Main SVG-to-draw.io conversion orchestration."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Callable
from os import PathLike, fspath, path
from xml.etree.ElementTree import Element

from .cell_factory import make_bounds_vertex
from .css import AncestorInfo, CssRule, apply_css, collect_css, extract_custom_props
from .defs import DefsIndex
from .drawio_model import Cell, group_bbox, shift_cells
from .drawio_output import make_xml
from .elements.image import emit_image
from .elements.path import emit_path
from .elements.poly import emit_polyline
from .elements.shapes import emit_circle, emit_ellipse, emit_line, emit_rect
from .elements.text import emit_text
from .emitter_context import EmitterContext
from .transforms import Matrix, mat_mul, parse_transform, viewbox_transform
from .utils import parse_length, strip_ns

_SKIP_TAGS: frozenset[str] = frozenset(
    {
        "defs",
        "title",
        "desc",
        "metadata",
        "style",
        "symbol",
        "clipPath",
        "mask",
        "linearGradient",
        "radialGradient",
        "marker",
        "pattern",
        "filter",
        "animate",
        "animateTransform",
    }
)

ElementEmitter = Callable[[EmitterContext, Element, Matrix, dict[str, str] | None], None]


def _emit_open_polyline(
    ctx: EmitterContext,
    elem: Element,
    matrix: Matrix,
    css: dict[str, str] | None,
) -> None:
    """Dispatch a `<polyline>` element."""
    emit_polyline(ctx, elem, matrix, closed=False, css=css)


def _emit_closed_polygon(
    ctx: EmitterContext,
    elem: Element,
    matrix: Matrix,
    css: dict[str, str] | None,
) -> None:
    """Dispatch a `<polygon>` element."""
    emit_polyline(ctx, elem, matrix, closed=True, css=css)


_DISPATCH: dict[str, ElementEmitter] = {
    "line": emit_line,
    "circle": emit_circle,
    "ellipse": emit_ellipse,
    "rect": emit_rect,
    "text": emit_text,
    "polyline": _emit_open_polyline,
    "polygon": _emit_closed_polygon,
    "path": emit_path,
    "image": emit_image,
}


class Converter:
    """Convert SVG files into draw.io XML by walking the SVG element tree."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        """Reset all per-file conversion state."""
        self._id: int = 2
        self.cells: list[Cell] = []
        self.defs = DefsIndex()
        self.source_dir: str = ""
        self.css_rules: list[CssRule] = []
        self._custom_props: dict[str, str] = {}

    def next_id(self) -> str:
        """Return the next unique draw.io cell identifier."""
        cell_id = str(self._id)
        self._id += 1
        return cell_id

    def _make_context(self) -> EmitterContext:
        """Create the root emitter context for the current conversion run."""
        return EmitterContext(
            defs=self.defs,
            parent_id="1",
            link_url="",
            source_dir=self.source_dir,
            css_rules=self.css_rules,
            custom_props=self._custom_props,
            add_cell=self.cells.append,
            next_id_callback=self.next_id,
        )

    def convert_file(
        self,
        svg_path: str | PathLike[str],
        out_path: str | PathLike[str] | None = None,
    ) -> str:
        """Convert one SVG file into a `.drawio` file and return the output path."""
        self.reset()

        svg_path_str = fspath(svg_path)
        tree = ET.parse(svg_path_str)
        root = tree.getroot()
        self.source_dir = path.dirname(path.abspath(svg_path_str))

        self.defs.index(root)
        self.css_rules = collect_css(root)
        self._custom_props = extract_custom_props(self.css_rules)
        root_matrix = viewbox_transform(root)
        context = self._make_context()

        title = path.splitext(path.basename(svg_path_str))[0]
        for child in root:
            self._convert(child, context, root_matrix, {}, ancestors=[])

        xml = make_xml(self.cells, title)
        output_path = fspath(out_path) if out_path is not None else path.splitext(svg_path_str)[0] + ".drawio"
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(xml)
        return output_path

    def _convert(
        self,
        elem: Element,
        ctx: EmitterContext,
        parent_matrix: Matrix,
        inherited_css: dict[str, str],
        ancestors: list[AncestorInfo] | None = None,
    ) -> None:
        """Convert a single SVG element and recurse into its children when needed."""
        ancestor_list = list(ancestors or [])
        tag = strip_ns(elem.tag)
        if tag in _SKIP_TAGS:
            return

        matrix = mat_mul(parent_matrix, parse_transform(elem.get("transform")))
        css = apply_css(elem, ctx.css_rules, tag, inherited_css, ancestors=ancestor_list, custom_props=ctx.custom_props)

        display_value = css.get("display") or elem.get("display") or ""
        visibility_value = css.get("visibility") or elem.get("visibility") or ""
        if display_value == "none" or visibility_value == "hidden":
            return

        elem_classes = set((elem.get("class") or "").split())
        child_ancestors = ancestor_list + [(tag, elem_classes)]

        if tag == "g":
            self._convert_group(elem, ctx, matrix, css, child_ancestors)
        elif tag == "a":
            self._convert_link(elem, ctx, matrix, css, child_ancestors)
        elif tag == "use":
            self._resolve_use(elem, ctx, matrix, css, child_ancestors)
        elif tag == "svg":
            inner_matrix = mat_mul(matrix, viewbox_transform(elem))
            for child in elem:
                self._convert(child, ctx, inner_matrix, css, ancestors=child_ancestors)
        elif tag in _DISPATCH:
            _DISPATCH[tag](ctx, elem, matrix, css)

    def _convert_group(
        self,
        elem: Element,
        ctx: EmitterContext,
        matrix: Matrix,
        css: dict[str, str],
        ancestors: list[AncestorInfo],
    ) -> None:
        """Render an SVG group as a draw.io container with relative child coordinates."""
        group_id = ctx.next_id()
        start_index = len(self.cells)

        group_ctx = ctx.with_parent(group_id)
        for child in elem:
            self._convert(child, group_ctx, matrix, css, ancestors=ancestors)

        new_cells = list(self.cells[start_index:])
        del self.cells[start_index:]

        direct_children = [cell for cell in new_cells if cell.parent == group_id]
        gx, gy, gw, gh = group_bbox(direct_children)

        self.cells.append(
            make_bounds_vertex(
                ctx,
                "group;",
                gx,
                gy,
                gw,
                gh,
                cell_id=group_id,
            )
        )

        shift_cells(direct_children, gx, gy)
        self.cells.extend(new_cells)

    def _convert_link(
        self,
        elem: Element,
        ctx: EmitterContext,
        matrix: Matrix,
        css: dict[str, str],
        ancestors: list[AncestorInfo],
    ) -> None:
        """Propagate the current `<a>` link target to all nested drawable children."""
        href = elem.get("href") or elem.get("{http://www.w3.org/1999/xlink}href") or ""
        link_ctx = ctx.with_link(href or ctx.link_url)
        for child in elem:
            self._convert(child, link_ctx, matrix, css, ancestors=ancestors)

    def _resolve_use(
        self,
        elem: Element,
        ctx: EmitterContext,
        matrix: Matrix,
        inherited_css: dict[str, str],
        ancestors: list[AncestorInfo] | None = None,
    ) -> None:
        """Resolve and render the target of a `<use>` element."""
        href = elem.get("href") or elem.get("{http://www.w3.org/1999/xlink}href") or ""
        if not href.startswith("#"):
            return

        ref_elem = self.defs.get_element(href[1:])
        if ref_elem is None:
            return

        use_x = parse_length(elem.get("x", "0"))
        use_y = parse_length(elem.get("y", "0"))
        use_translate: Matrix = [1.0, 0.0, 0.0, 1.0, use_x, use_y]

        ref_tag = strip_ns(ref_elem.tag)
        if ref_tag == "symbol":
            use_width = parse_length(elem.get("width", "0")) or None
            use_height = parse_length(elem.get("height", "0")) or None
            symbol_matrix = mat_mul(matrix, use_translate)
            inner_matrix = mat_mul(
                symbol_matrix,
                viewbox_transform(ref_elem, override_w=use_width, override_h=use_height),
            )
            for child in ref_elem:
                self._convert(child, ctx, inner_matrix, inherited_css, ancestors=ancestors or [])
            return

        use_matrix = mat_mul(matrix, use_translate)
        self._convert(ref_elem, ctx, use_matrix, inherited_css, ancestors=ancestors or [])
