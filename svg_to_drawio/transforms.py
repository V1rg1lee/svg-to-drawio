import re
import math

from .utils import parse_float

IDENTITY = [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]


def mat_mul(a, b):
    return [
        a[0]*b[0] + a[2]*b[1],
        a[1]*b[0] + a[3]*b[1],
        a[0]*b[2] + a[2]*b[3],
        a[1]*b[2] + a[3]*b[3],
        a[0]*b[4] + a[2]*b[5] + a[4],
        a[1]*b[4] + a[3]*b[5] + a[5],
    ]


def apply_pt(m, x, y):
    return m[0]*x + m[2]*y + m[4], m[1]*x + m[3]*y + m[5]


def scale_x(m):
    return math.sqrt(m[0]**2 + m[1]**2)


def scale_y(m):
    return math.sqrt(m[2]**2 + m[3]**2)


def parse_transform(t):
    if not t:
        return IDENTITY[:]
    result = IDENTITY[:]
    for match in re.finditer(r'(\w+)\(([^)]+)\)', t):
        fn = match.group(1)
        ns = [float(n) for n in re.findall(r'[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?', match.group(2))]
        if fn == 'translate':
            tx, ty = (ns + [0.0, 0.0])[:2]
            mat = [1, 0, 0, 1, tx, ty]
        elif fn == 'scale':
            sx = ns[0] if ns else 1.0
            sy = ns[1] if len(ns) > 1 else sx
            mat = [sx, 0, 0, sy, 0, 0]
        elif fn == 'rotate':
            a = math.radians(ns[0]) if ns else 0.0
            cx_r, cy_r = (ns + [0.0, 0.0, 0.0])[1:3]
            ca, sa = math.cos(a), math.sin(a)
            mat = [ca, sa, -sa, ca, cx_r - cx_r*ca + cy_r*sa, cy_r - cx_r*sa - cy_r*ca]
        elif fn == 'skewX':
            a = math.radians(ns[0]) if ns else 0.0
            mat = [1, 0, math.tan(a), 1, 0, 0]
        elif fn == 'skewY':
            a = math.radians(ns[0]) if ns else 0.0
            mat = [1, math.tan(a), 0, 1, 0, 0]
        elif fn == 'matrix' and len(ns) >= 6:
            mat = ns[:6]
        else:
            continue
        result = mat_mul(result, mat)
    return result


def viewbox_transform(svg_root):
    """Return a transform matrix that maps the SVG viewBox coordinate space to pixels."""
    vb = svg_root.get('viewBox')
    if not vb:
        return IDENTITY[:]
    vals = [float(v) for v in re.split(r'[\s,]+', vb.strip()) if v]
    if len(vals) < 4:
        return IDENTITY[:]
    vb_x, vb_y, vb_w, vb_h = vals
    if vb_w == 0 or vb_h == 0:
        return IDENTITY[:]
    w_str = svg_root.get('width', str(vb_w))
    h_str = svg_root.get('height', str(vb_h))
    w = parse_float(re.sub(r'[a-zA-Z%]', '', w_str)) or vb_w
    h = parse_float(re.sub(r'[a-zA-Z%]', '', h_str)) or vb_h
    sx = w / vb_w
    sy = h / vb_h
    return [sx, 0.0, 0.0, sy, -vb_x * sx, -vb_y * sy]
