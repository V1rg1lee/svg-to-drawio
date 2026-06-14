import re
import xml.etree.ElementTree as ET
from os import path

from .utils import strip_ns, parse_float

# ── Group geometry helpers ────────────────────────────────────────────────────
# In draw.io, group children use coordinates *relative* to the group's top-left.
# These helpers extract bboxes from already-emitted cell strings and shift them.

_GEOM_RE = re.compile(
    r'<mxGeometry x="([-\d.]+)" y="([-\d.]+)" width="([-\d.]+)" height="([-\d.]+)"'
)
_POINT_RE = re.compile(r'<mxPoint x="([-\d.]+)" y="([-\d.]+)"')


def _cell_bbox(xml):
    """Return (x, y, w, h) from a vertex mxCell's mxGeometry, or None for edges."""
    m = _GEOM_RE.search(xml)
    return (float(m.group(1)), float(m.group(2)),
            float(m.group(3)), float(m.group(4))) if m else None


def _shift_cell(xml, dx, dy):
    """Subtract (dx, dy) from all geometry/point coordinates in a mxCell string."""
    if dx == 0.0 and dy == 0.0:
        return xml

    def adj_geom(m):
        return (f'<mxGeometry x="{float(m.group(1)) - dx:.2f}"'
                f' y="{float(m.group(2)) - dy:.2f}"'
                f' width="{m.group(3)}" height="{m.group(4)}"')

    def adj_point(m):
        return (f'<mxPoint x="{float(m.group(1)) - dx:.2f}"'
                f' y="{float(m.group(2)) - dy:.2f}"')

    return _POINT_RE.sub(adj_point, _GEOM_RE.sub(adj_geom, xml))
from .transforms import IDENTITY, mat_mul, parse_transform, viewbox_transform
from .css import collect_css, apply_css
from .defs import DefsIndex
from .drawio_output import make_xml
from .elements.shapes import emit_line, emit_circle, emit_ellipse, emit_rect
from .elements.text import emit_text
from .elements.poly import emit_polyline
from .elements.path import emit_path

_SKIP_TAGS = frozenset({
    'defs', 'title', 'desc', 'metadata', 'style', 'symbol',
    'clipPath', 'mask', 'linearGradient', 'radialGradient',
    'marker', 'pattern', 'filter', 'animate', 'animateTransform',
    'image',
})

_DISPATCH = {
    'line':     emit_line,
    'circle':   emit_circle,
    'ellipse':  emit_ellipse,
    'rect':     emit_rect,
    'text':     emit_text,
    'polyline': lambda c, e, m, css: emit_polyline(c, e, m, closed=False, css=css),
    'polygon':  lambda c, e, m, css: emit_polyline(c, e, m, closed=True,  css=css),
    'path':     emit_path,
}


class Converter:
    def __init__(self):
        self._id = 2
        self.cells = []
        self.defs = DefsIndex()
        self._parent_id = '1'
        self._link_url = ''

    @property
    def parent_id(self):
        return self._parent_id

    def next_id(self):
        cid = str(self._id)
        self._id += 1
        return cid

    def add(self, xml):
        self.cells.append(xml)

    def convert_file(self, svg_path, out_path=None):
        tree = ET.parse(svg_path)
        root = tree.getroot()

        self.defs.index(root)
        css_rules = collect_css(root)
        root_m = viewbox_transform(root)

        title = path.splitext(path.basename(svg_path))[0]
        for child in root:
            self._convert(child, root_m, css_rules, {}, ancestors=[])

        xml = make_xml(self.cells, title)
        if out_path is None:
            out_path = path.splitext(svg_path)[0] + '.drawio'
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(xml)
        return out_path

    def _convert(self, elem, parent_m, css_rules, inherited_css, ancestors=None):
        if ancestors is None:
            ancestors = []
        tag = strip_ns(elem.tag)
        if tag in _SKIP_TAGS:
            return

        m = mat_mul(parent_m, parse_transform(elem.get('transform')))
        css = apply_css(elem, css_rules, tag, inherited_css, ancestors=ancestors)

        # Feature 1: skip hidden elements (check both CSS and SVG presentation attributes)
        display_val = css.get('display') or elem.get('display') or ''
        visibility_val = css.get('visibility') or elem.get('visibility') or ''
        if display_val == 'none' or visibility_val == 'hidden':
            return

        # ancestors is a list of (tag, classes_set) tuples for descendant selector matching
        elem_classes = set((elem.get('class') or '').split())
        child_ancestors = ancestors + [(tag, elem_classes)]

        if tag == 'g':
            # <g> as draw.io container group.
            # draw.io requires: group cell has explicit canvas bbox; children use
            # coordinates *relative* to the group's top-left corner.
            group_id = self.next_id()
            start = len(self.cells)

            prev_parent = self._parent_id
            self._parent_id = group_id
            for child in elem:
                self._convert(child, m, css_rules, css, ancestors=child_ancestors)
            self._parent_id = prev_parent

            # Collect and remove newly added cells
            new_cells = list(self.cells[start:])
            del self.cells[start:]

            # Compute group bbox from direct children only (parent=group_id)
            parent_marker = f'parent="{group_id}"'
            bboxes = [b for b in (
                _cell_bbox(c) for c in new_cells if parent_marker in c
            ) if b is not None]

            if bboxes:
                gx = min(b[0] for b in bboxes)
                gy = min(b[1] for b in bboxes)
                gw = max(b[0] + b[2] for b in bboxes) - gx
                gh = max(b[1] + b[3] for b in bboxes) - gy
            else:
                gx, gy, gw, gh = 0.0, 0.0, 1.0, 1.0

            # Emit group cell with its canvas bbox
            self.cells.append(
                f'    <mxCell id="{group_id}" value="" style="group;" '
                f'vertex="1" parent="{prev_parent}">\n'
                f'      <mxGeometry x="{gx:.2f}" y="{gy:.2f}" '
                f'width="{gw:.2f}" height="{gh:.2f}" as="geometry"/>\n'
                f'    </mxCell>'
            )

            # Emit children: direct children get coordinates relative to group
            for c in new_cells:
                if parent_marker in c:
                    c = _shift_cell(c, gx, gy)
                self.cells.append(c)

        elif tag == 'a':
            # Feature 12: <a> links
            href = (elem.get('href') or
                    elem.get('{http://www.w3.org/1999/xlink}href') or '')
            prev_link = self._link_url
            self._link_url = href or prev_link
            for child in elem:
                self._convert(child, m, css_rules, css, ancestors=child_ancestors)
            self._link_url = prev_link

        elif tag == 'use':
            self._resolve_use(elem, m, css_rules, css, ancestors=child_ancestors)

        elif tag == 'svg':
            # Nested <svg> with its own viewBox
            inner_m = mat_mul(m, viewbox_transform(elem))
            for child in elem:
                self._convert(child, inner_m, css_rules, css, ancestors=child_ancestors)

        elif tag in _DISPATCH:
            _DISPATCH[tag](self, elem, m, css)

    def _resolve_use(self, elem, m, css_rules, inherited_css, ancestors=None):
        href = (elem.get('href') or
                elem.get('{http://www.w3.org/1999/xlink}href') or '')
        if not href.startswith('#'):
            return
        ref_elem = self.defs.get_element(href[1:])
        if ref_elem is None:
            return

        ux = parse_float(elem.get('x', '0'))
        uy = parse_float(elem.get('y', '0'))
        use_translate = [1, 0, 0, 1, ux, uy]

        ref_tag = strip_ns(ref_elem.tag)
        if ref_tag == 'symbol':
            # Feature 8: symbol rendering
            uw = parse_float(elem.get('width', '0')) or None
            uh = parse_float(elem.get('height', '0')) or None
            symbol_m = mat_mul(m, use_translate)
            inner_m = mat_mul(symbol_m, viewbox_transform(ref_elem, override_w=uw, override_h=uh))
            for child in ref_elem:
                self._convert(child, inner_m, css_rules, inherited_css, ancestors=ancestors)
        else:
            use_m = mat_mul(m, use_translate)
            self._convert(ref_elem, use_m, css_rules, inherited_css, ancestors=ancestors)
