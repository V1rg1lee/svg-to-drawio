import xml.etree.ElementTree as ET
from os import path

from .utils import strip_ns, parse_float
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
            self._convert(child, root_m, css_rules, {})

        xml = make_xml(self.cells, title)
        if out_path is None:
            out_path = path.splitext(svg_path)[0] + '.drawio'
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(xml)
        return out_path

    def _convert(self, elem, parent_m, css_rules, inherited_css):
        tag = strip_ns(elem.tag)
        if tag in _SKIP_TAGS:
            return

        m = mat_mul(parent_m, parse_transform(elem.get('transform')))
        css = apply_css(elem, css_rules, tag, inherited_css)

        if tag == 'g':
            for child in elem:
                self._convert(child, m, css_rules, css)
        elif tag == 'use':
            self._resolve_use(elem, m, css_rules, css)
        elif tag == 'svg':
            # Nested <svg> with its own viewBox
            inner_m = mat_mul(m, viewbox_transform(elem))
            for child in elem:
                self._convert(child, inner_m, css_rules, css)
        elif tag in _DISPATCH:
            _DISPATCH[tag](self, elem, m, css)

    def _resolve_use(self, elem, m, css_rules, inherited_css):
        href = (elem.get('href') or
                elem.get('{http://www.w3.org/1999/xlink}href') or '')
        if not href.startswith('#'):
            return
        ref_elem = self.defs.get_element(href[1:])
        if ref_elem is None:
            return
        ux = parse_float(elem.get('x', '0'))
        uy = parse_float(elem.get('y', '0'))
        use_m = mat_mul(m, [1, 0, 0, 1, ux, uy])
        self._convert(ref_elem, use_m, css_rules, inherited_css)
