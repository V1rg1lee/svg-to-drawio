import re
import math

from .utils import strip_ns, parse_float, parse_style_attr
from .styles import normalize_color

# Heuristic mapping of common marker element IDs to draw.io arrow names
_MARKER_ID_MAP = {
    'arrow':     'block',
    'arrowhead': 'block',
    'triangle':  'block',
    'circle':    'oval',
    'dot':       'oval',
    'diamond':   'diamond',
    'open':      'open',
}


def _stop_color(stop_elem):
    props = parse_style_attr(stop_elem.get('style', ''))
    raw = props.get('stop-color') or stop_elem.get('stop-color', '#000000')
    color = normalize_color(raw) or '#000000'
    raw_opacity = props.get('stop-opacity') or stop_elem.get('stop-opacity', '1')
    alpha = max(0.0, min(1.0, parse_float(raw_opacity, 1.0)))
    if alpha < 1.0 and color.startswith('#') and len(color) == 7:
        r = int(color[1:3], 16)
        g = int(color[3:5], 16)
        b = int(color[5:7], 16)
        r = round(r * alpha + 255 * (1 - alpha))
        g = round(g * alpha + 255 * (1 - alpha))
        b = round(b * alpha + 255 * (1 - alpha))
        color = f'#{r:02x}{g:02x}{b:02x}'
    return color


def _parse_stops(elem):
    stops = []
    for child in elem:
        if strip_ns(child.tag) == 'stop':
            offset = parse_float(child.get('offset', '0'))
            stops.append((offset, _stop_color(child)))
    stops.sort(key=lambda x: x[0])
    return stops


class DefsIndex:
    """Indexes all <defs> content (gradients, markers, filters, reusable elements) for later lookup."""

    def __init__(self):
        self._elements  = {}   # id -> element
        self._gradients = {}   # id -> gradient dict
        self._markers   = {}   # id -> draw.io arrow name
        self._filters   = {}   # id -> filter dict

    # -- Indexing -------------------------------------------------------------

    def index(self, svg_root):
        for elem in svg_root.iter():
            tag = strip_ns(elem.tag)
            eid = elem.get('id')
            if eid:
                self._elements[eid] = elem
            if tag == 'linearGradient':
                self._index_linear(elem, eid)
            elif tag == 'radialGradient':
                self._index_radial(elem, eid)
            elif tag == 'marker':
                self._index_marker(elem, eid)
            elif tag == 'filter':
                self._index_filter(elem, eid)

    def _index_linear(self, elem, eid):
        stops = _parse_stops(elem)
        if not stops or not eid:
            return
        x1 = parse_float(elem.get('x1', '0'))
        y1 = parse_float(elem.get('y1', '0'))
        x2 = parse_float(elem.get('x2', '1'))
        y2 = parse_float(elem.get('y2', '0'))
        dx, dy = x2 - x1, y2 - y1
        direction = ('east' if dx >= 0 else 'west') if abs(dx) >= abs(dy) else ('south' if dy >= 0 else 'north')

        # gradientTransform overrides the direction computed from x1/y1/x2/y2
        gt = elem.get('gradientTransform', '')
        if gt:
            from .transforms import parse_transform
            gm = parse_transform(gt)
            angle = math.degrees(math.atan2(gm[1], gm[0]))
            if -45 <= angle <= 45:
                direction = 'east'
            elif 45 < angle <= 135:
                direction = 'south'
            elif angle > 135 or angle < -135:
                direction = 'west'
            else:
                direction = 'north'

        self._gradients[eid] = {
            'color':     stops[0][1],
            'color2':    stops[-1][1],
            'direction': direction,
        }

    def _index_radial(self, elem, eid):
        stops = _parse_stops(elem)
        if not stops or not eid:
            return
        self._gradients[eid] = {
            'color':  stops[0][1],
            'color2': stops[-1][1],
            'direction': 'radial',
        }

    def _index_marker(self, elem, eid):
        if not eid:
            return
        # Check heuristic ID mapping first
        for key, arrow in _MARKER_ID_MAP.items():
            if key in eid.lower():
                self._markers[eid] = arrow
                return
        # Fall back to inspecting the marker's child shapes
        for child in elem.iter():
            tag = strip_ns(child.tag)
            if tag == 'circle':
                self._markers[eid] = 'oval'; return
            if tag in ('polygon', 'path'):
                self._markers[eid] = 'block'; return
        self._markers[eid] = 'open'

    def _index_filter(self, elem, eid):
        if not eid:
            return
        for child in elem.iter():
            ctag = strip_ns(child.tag)
            if ctag == 'feDropShadow':
                dx = parse_float(child.get('dx', '2'))
                dy = parse_float(child.get('dy', '2'))
                color = normalize_color(child.get('flood-color', '#000000')) or '#000000'
                opacity = int(parse_float(child.get('flood-opacity', '0.5')) * 100)
                self._filters[eid] = {
                    'type':    'shadow',
                    'dx':      dx,
                    'dy':      dy,
                    'color':   color,
                    'opacity': opacity,
                }
                return

    # -- Resolution -----------------------------------------------------------

    def get_element(self, ref_id):
        return self._elements.get(ref_id)

    def resolve_fill(self, fill_str):
        """
        If fill_str is url(#id), return (first-stop-color, gradient-dict).
        Otherwise return (fill_str, None).
        """
        if not fill_str:
            return fill_str, None
        m = re.match(r'url\(#([^)]+)\)', fill_str or '')
        if m:
            grad = self._gradients.get(m.group(1))
            if grad:
                return grad['color'], grad
        return fill_str, None

    def resolve_marker(self, marker_str):
        """Return a draw.io arrow name for a marker-start/end value, or 'none'."""
        if not marker_str:
            return 'none'
        m = re.match(r'url\(#([^)]+)\)', marker_str)
        if m:
            return self._markers.get(m.group(1), 'open')
        return 'none'

    def resolve_filter(self, filter_str):
        """Return draw.io style fragments for a filter attribute value."""
        if not filter_str:
            return ''
        m = re.match(r'url\(#([^)]+)\)', filter_str or '')
        if m:
            f = self._filters.get(m.group(1))
            if f and f['type'] == 'shadow':
                return (f'shadow=1;shadowColor={f["color"]};shadowOpacity={f["opacity"]};'
                        f'shadowOffsetX={f["dx"]:.0f};shadowOffsetY={f["dy"]:.0f};')
        return ''
