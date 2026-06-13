"""
Convert SVG files to draw.io (.drawio) format, decomposing each SVG element
into individual editable draw.io cells instead of embedding as a single image.

Usage:
    python svg_decompose_to_drawio.py <svg_file_or_folder>
"""

import xml.etree.ElementTree as ET
import re
import math
from base64 import b64encode
from sys import argv
from os import listdir, path


# ── Utilities ────────────────────────────────────────────────────────────────

def strip_ns(tag):
    return tag.split('}', 1)[1] if '}' in tag else tag

def parse_style_attr(s):
    result = {}
    for item in (s or '').split(';'):
        if ':' in item:
            k, v = item.split(':', 1)
            result[k.strip().lower()] = v.strip()
    return result

def parse_float(val, default=0.0):
    if val is None:
        return default
    try:
        cleaned = re.sub(r'[^\d.eE+\-]', '', str(val))
        return float(cleaned) if cleaned else default
    except ValueError:
        return default

def normalize_color(c):
    if not c:
        return None
    c = str(c).strip()
    if c.lower() in ('none', 'transparent'):
        return 'none'
    m = re.match(r'rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)', c)
    if m:
        return '#{:02x}{:02x}{:02x}'.format(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return c

def get_visual(elem):
    s = parse_style_attr(elem.get('style', ''))
    def g(attr, default=None):
        return s.get(attr) or elem.get(attr) or default
    return {
        'fill':         normalize_color(g('fill', 'none')),
        'stroke':       normalize_color(g('stroke', 'none')),
        'stroke_width': parse_float(re.sub(r'[^\d.]', '', g('stroke-width', '1'))),
        'opacity':      parse_float(g('opacity', '1')),
        'fill_opacity': parse_float(g('fill-opacity', '1')),
        'font_size':    parse_float(re.sub(r'[^\d.]', '', g('font-size', '12'))),
        'font_family':  g('font-family', 'Helvetica'),
        'text_anchor':  g('text-anchor', 'start'),
        'text_fill':    normalize_color(g('fill', '#000000')),
    }


# ── 2-D affine transform ─────────────────────────────────────────────────────

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

def scale_x(m): return math.sqrt(m[0]**2 + m[1]**2)
def scale_y(m): return math.sqrt(m[2]**2 + m[3]**2)

def parse_transform(t):
    if not t:
        return IDENTITY[:]
    result = IDENTITY[:]
    for match in re.finditer(r'(\w+)\(([^)]+)\)', t):
        fn = match.group(1)
        ns = [float(n) for n in re.findall(r'[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?', match.group(2))]
        if fn == 'translate':
            tx, ty = (ns + [0, 0])[:2]
            mat = [1, 0, 0, 1, tx, ty]
        elif fn == 'scale':
            sx = ns[0] if ns else 1
            sy = ns[1] if len(ns) > 1 else sx
            mat = [sx, 0, 0, sy, 0, 0]
        elif fn == 'rotate':
            a = math.radians(ns[0]) if ns else 0
            cx, cy = (ns + [0, 0, 0])[1:3]
            ca, sa = math.cos(a), math.sin(a)
            mat = [ca, sa, -sa, ca, cx - cx*ca + cy*sa, cy - cx*sa - cy*ca]
        elif fn == 'matrix' and len(ns) >= 6:
            mat = ns[:6]
        else:
            continue
        result = mat_mul(result, mat)
    return result


# ── SVG path helpers ─────────────────────────────────────────────────────────

def tokenize_path(d):
    return re.findall(
        r'[MmLlHhVvCcSsQqTtAaZz]|[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?',
        d or ''
    )

def path_points(d):
    """Yield approximate (x,y) key-points from SVG path data."""
    tokens = tokenize_path(d)
    i, cx, cy = 0, 0.0, 0.0
    while i < len(tokens):
        tok = tokens[i]
        if tok not in 'MmLlHhVvCcSsQqTtAaZz':
            i += 1; continue
        cmd, i = tok, i + 1
        if cmd in 'Zz':
            continue
        while i < len(tokens) and tokens[i] not in 'MmLlHhVvCcSsQqTtAaZz':
            try:
                if cmd in 'ML':
                    cx, cy = float(tokens[i]), float(tokens[i+1])
                    yield cx, cy; i += 2
                    if cmd == 'M': cmd = 'L'
                elif cmd in 'ml':
                    ox, oy = cx, cy
                    cx, cy = ox + float(tokens[i]), oy + float(tokens[i+1])
                    yield cx, cy; i += 2
                    if cmd == 'm': cmd = 'l'
                elif cmd == 'H':
                    cx = float(tokens[i]); yield cx, cy; i += 1
                elif cmd == 'h':
                    cx += float(tokens[i]); yield cx, cy; i += 1
                elif cmd == 'V':
                    cy = float(tokens[i]); yield cx, cy; i += 1
                elif cmd == 'v':
                    cy += float(tokens[i]); yield cx, cy; i += 1
                elif cmd == 'C':
                    for j in range(0, 6, 2):
                        yield float(tokens[i+j]), float(tokens[i+j+1])
                    cx, cy = float(tokens[i+4]), float(tokens[i+5]); i += 6
                elif cmd == 'c':
                    ox, oy = cx, cy
                    for j in range(0, 6, 2):
                        yield ox + float(tokens[i+j]), oy + float(tokens[i+j+1])
                    cx, cy = ox + float(tokens[i+4]), oy + float(tokens[i+5]); i += 6
                elif cmd in 'Ss':
                    ox, oy = cx, cy
                    off = (0, 0) if cmd == 'S' else (ox, oy)
                    yield off[0]+float(tokens[i]), off[1]+float(tokens[i+1])
                    cx = off[0]+float(tokens[i+2]); cy = off[1]+float(tokens[i+3])
                    yield cx, cy; i += 4
                elif cmd in 'Qq':
                    ox, oy = cx, cy
                    off = (0, 0) if cmd == 'Q' else (ox, oy)
                    yield off[0]+float(tokens[i]), off[1]+float(tokens[i+1])
                    cx = off[0]+float(tokens[i+2]); cy = off[1]+float(tokens[i+3])
                    yield cx, cy; i += 4
                elif cmd in 'Tt':
                    ox, oy = cx, cy
                    off = (0, 0) if cmd == 'T' else (ox, oy)
                    cx = off[0]+float(tokens[i]); cy = off[1]+float(tokens[i+1])
                    yield cx, cy; i += 2
                elif cmd in 'Aa' and i + 6 < len(tokens):
                    ox, oy = cx, cy
                    off = (0, 0) if cmd == 'A' else (ox, oy)
                    cx = off[0]+float(tokens[i+5]); cy = off[1]+float(tokens[i+6])
                    yield cx, cy; i += 7
                else:
                    i += 1
            except (IndexError, ValueError):
                i += 1


def path_to_stencil(d, ox, oy, w, h):
    """Convert SVG path d attribute to draw.io stencil path XML (coords in 0-100 space)."""
    def nx(x): return (x - ox) / w * 100 if w else 0
    def ny(y): return (y - oy) / h * 100 if h else 0

    parts = []
    tokens = tokenize_path(d)
    i, cx, cy = 0, 0.0, 0.0
    sx, sy = 0.0, 0.0

    while i < len(tokens):
        tok = tokens[i]
        if tok not in 'MmLlHhVvCcSsQqTtAaZz':
            i += 1; continue
        cmd, i = tok, i + 1
        if cmd in 'Zz':
            parts.append('<close/>'); cx, cy = sx, sy; continue
        while i < len(tokens) and tokens[i] not in 'MmLlHhVvCcSsQqTtAaZz':
            try:
                if cmd == 'M':
                    cx, cy = float(tokens[i]), float(tokens[i+1]); sx, sy = cx, cy
                    parts.append(f'<move x="{nx(cx):.2f}" y="{ny(cy):.2f}"/>'); i += 2; cmd = 'L'
                elif cmd == 'm':
                    ox_, oy_ = cx, cy
                    cx, cy = ox_+float(tokens[i]), oy_+float(tokens[i+1]); sx, sy = cx, cy
                    parts.append(f'<move x="{nx(cx):.2f}" y="{ny(cy):.2f}"/>'); i += 2; cmd = 'l'
                elif cmd == 'L':
                    cx, cy = float(tokens[i]), float(tokens[i+1])
                    parts.append(f'<line x="{nx(cx):.2f}" y="{ny(cy):.2f}"/>'); i += 2
                elif cmd == 'l':
                    cx += float(tokens[i]); cy += float(tokens[i+1])
                    parts.append(f'<line x="{nx(cx):.2f}" y="{ny(cy):.2f}"/>'); i += 2
                elif cmd == 'H':
                    cx = float(tokens[i])
                    parts.append(f'<line x="{nx(cx):.2f}" y="{ny(cy):.2f}"/>'); i += 1
                elif cmd == 'h':
                    cx += float(tokens[i])
                    parts.append(f'<line x="{nx(cx):.2f}" y="{ny(cy):.2f}"/>'); i += 1
                elif cmd == 'V':
                    cy = float(tokens[i])
                    parts.append(f'<line x="{nx(cx):.2f}" y="{ny(cy):.2f}"/>'); i += 1
                elif cmd == 'v':
                    cy += float(tokens[i])
                    parts.append(f'<line x="{nx(cx):.2f}" y="{ny(cy):.2f}"/>'); i += 1
                elif cmd == 'C':
                    x1,y1 = float(tokens[i]),float(tokens[i+1])
                    x2,y2 = float(tokens[i+2]),float(tokens[i+3])
                    cx,cy = float(tokens[i+4]),float(tokens[i+5])
                    parts.append(f'<curve x1="{nx(x1):.2f}" y1="{ny(y1):.2f}" x2="{nx(x2):.2f}" y2="{ny(y2):.2f}" x3="{nx(cx):.2f}" y3="{ny(cy):.2f}"/>'); i += 6
                elif cmd == 'c':
                    bx, by = cx, cy
                    x1,y1 = bx+float(tokens[i]),by+float(tokens[i+1])
                    x2,y2 = bx+float(tokens[i+2]),by+float(tokens[i+3])
                    cx,cy = bx+float(tokens[i+4]),by+float(tokens[i+5])
                    parts.append(f'<curve x1="{nx(x1):.2f}" y1="{ny(y1):.2f}" x2="{nx(x2):.2f}" y2="{ny(y2):.2f}" x3="{nx(cx):.2f}" y3="{ny(cy):.2f}"/>'); i += 6
                elif cmd in 'Ss':
                    bx, by = cx, cy
                    off = (0.0, 0.0) if cmd == 'S' else (bx, by)
                    x2,y2 = off[0]+float(tokens[i]),off[1]+float(tokens[i+1])
                    cx,cy = off[0]+float(tokens[i+2]),off[1]+float(tokens[i+3])
                    parts.append(f'<curve x1="{nx(bx):.2f}" y1="{ny(by):.2f}" x2="{nx(x2):.2f}" y2="{ny(y2):.2f}" x3="{nx(cx):.2f}" y3="{ny(cy):.2f}"/>'); i += 4
                elif cmd in 'Qq':
                    bx, by = cx, cy
                    off = (0.0, 0.0) if cmd == 'Q' else (bx, by)
                    qx1,qy1 = off[0]+float(tokens[i]),off[1]+float(tokens[i+1])
                    cx,cy   = off[0]+float(tokens[i+2]),off[1]+float(tokens[i+3])
                    # Convert quadratic to cubic bezier
                    cx1 = bx + 2/3*(qx1-bx); cy1 = by + 2/3*(qy1-by)
                    cx2 = cx + 2/3*(qx1-cx);  cy2 = cy + 2/3*(qy1-cy)
                    parts.append(f'<curve x1="{nx(cx1):.2f}" y1="{ny(cy1):.2f}" x2="{nx(cx2):.2f}" y2="{ny(cy2):.2f}" x3="{nx(cx):.2f}" y3="{ny(cy):.2f}"/>'); i += 4
                elif cmd in 'Aa' and i + 6 < len(tokens):
                    bx, by = cx, cy
                    off = (0.0, 0.0) if cmd == 'A' else (bx, by)
                    cx,cy = off[0]+float(tokens[i+5]),off[1]+float(tokens[i+6])
                    parts.append(f'<line x="{nx(cx):.2f}" y="{ny(cy):.2f}"/>'); i += 7
                else:
                    i += 1
            except (IndexError, ValueError):
                i += 1
    return ''.join(parts)


def make_stencil_style(d, ox, oy, w, h, fill, stroke, sw, op):
    """Build a draw.io stencil style string from an SVG path."""
    sp = path_to_stencil(d, ox, oy, w, h)
    if not sp:
        return None
    xml = f'<shape w="{w:.2f}" h="{h:.2f}"><background><path>{sp}</path><fillstroke/></background></shape>'
    b64 = b64encode(xml.encode('utf-8')).decode('ascii')
    return f'shape=stencil({b64});fillColor={fill};strokeColor={stroke};strokeWidth={sw};opacity={op};'


# ── Converter ────────────────────────────────────────────────────────────────

class Converter:
    def __init__(self):
        self._id = 2
        self.cells = []

    def _nid(self):
        cid = str(self._id); self._id += 1; return cid

    def _add(self, xml):
        self.cells.append(xml)

    # ---- shape emitters ----

    def emit_line(self, elem, m):
        v = get_visual(elem)
        x1, y1 = apply_pt(m, parse_float(elem.get('x1')), parse_float(elem.get('y1')))
        x2, y2 = apply_pt(m, parse_float(elem.get('x2')), parse_float(elem.get('y2')))
        sc = v['stroke'] or '#000000'
        op = int(v['opacity'] * 100)
        cid = self._nid()
        self._add(
            f'    <mxCell id="{cid}" value="" '
            f'style="endArrow=none;html=1;strokeColor={sc};strokeWidth={v["stroke_width"]};opacity={op};" '
            f'edge="1" parent="1">\n'
            f'      <mxGeometry relative="1" as="geometry">\n'
            f'        <mxPoint x="{x1:.2f}" y="{y1:.2f}" as="sourcePoint"/>\n'
            f'        <mxPoint x="{x2:.2f}" y="{y2:.2f}" as="targetPoint"/>\n'
            f'      </mxGeometry>\n'
            f'    </mxCell>'
        )

    def emit_circle(self, elem, m):
        v = get_visual(elem)
        cx = parse_float(elem.get('cx'))
        cy = parse_float(elem.get('cy'))
        r  = parse_float(elem.get('r'))
        cx, cy = apply_pt(m, cx, cy)
        rx = r * scale_x(m); ry = r * scale_y(m)
        fill = v['fill'] or 'none'
        stroke = v['stroke'] or 'none'
        op = int(v['opacity'] * 100)
        cid = self._nid()
        self._add(
            f'    <mxCell id="{cid}" value="" '
            f'style="ellipse;whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};'
            f'strokeWidth={v["stroke_width"]};opacity={op};" '
            f'vertex="1" parent="1">\n'
            f'      <mxGeometry x="{cx-rx:.2f}" y="{cy-ry:.2f}" width="{rx*2:.2f}" height="{ry*2:.2f}" as="geometry"/>\n'
            f'    </mxCell>'
        )

    def emit_ellipse(self, elem, m):
        v = get_visual(elem)
        cx = parse_float(elem.get('cx'))
        cy = parse_float(elem.get('cy'))
        rx0 = parse_float(elem.get('rx'))
        ry0 = parse_float(elem.get('ry'))
        cx, cy = apply_pt(m, cx, cy)
        rx = rx0 * scale_x(m); ry = ry0 * scale_y(m)
        fill = v['fill'] or 'none'
        stroke = v['stroke'] or 'none'
        op = int(v['opacity'] * 100)
        cid = self._nid()
        self._add(
            f'    <mxCell id="{cid}" value="" '
            f'style="ellipse;whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};'
            f'strokeWidth={v["stroke_width"]};opacity={op};" '
            f'vertex="1" parent="1">\n'
            f'      <mxGeometry x="{cx-rx:.2f}" y="{cy-ry:.2f}" width="{rx*2:.2f}" height="{ry*2:.2f}" as="geometry"/>\n'
            f'    </mxCell>'
        )

    def emit_rect(self, elem, m):
        v = get_visual(elem)
        x0 = parse_float(elem.get('x'))
        y0 = parse_float(elem.get('y'))
        w0 = parse_float(elem.get('width'))
        h0 = parse_float(elem.get('height'))
        rx = parse_float(elem.get('rx', '0'))
        x, y = apply_pt(m, x0, y0)
        w, h = w0 * scale_x(m), h0 * scale_y(m)
        fill = v['fill'] or '#ffffff'
        stroke = v['stroke'] or 'none'
        op = int(v['opacity'] * 100)
        rounded = 'rounded=1;arcSize=50;' if rx > 0 else 'rounded=0;'
        cid = self._nid()
        self._add(
            f'    <mxCell id="{cid}" value="" '
            f'style="{rounded}whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};'
            f'strokeWidth={v["stroke_width"]};opacity={op};" '
            f'vertex="1" parent="1">\n'
            f'      <mxGeometry x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" as="geometry"/>\n'
            f'    </mxCell>'
        )

    def emit_text(self, elem, m):
        v = get_visual(elem)
        x0 = parse_float(elem.get('x'))
        y0 = parse_float(elem.get('y'))
        x, y = apply_pt(m, x0, y0)

        content = (elem.text or '').strip()
        for child in elem:
            if strip_ns(child.tag) == 'tspan':
                content += (child.text or '')
        content = content.strip()
        if not content:
            return

        font_color = v['text_fill'] or '#000000'
        fs = max(v['font_size'], 6)
        op = int(v['opacity'] * 100)
        align = {'start': 'left', 'middle': 'center', 'end': 'right'}.get(v['text_anchor'], 'left')

        est_w = max(len(content) * fs * 0.62, 20)
        est_h = fs * 1.8
        tx = x - (est_w/2 if align == 'center' else est_w if align == 'right' else 0)
        ty = y - fs * 0.85  # SVG y is baseline

        safe = content.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
        cid = self._nid()
        self._add(
            f'    <mxCell id="{cid}" value="{safe}" '
            f'style="text;html=1;strokeColor=none;fillColor=none;align={align};'
            f'verticalAlign=middle;whiteSpace=wrap;rounded=0;'
            f'fontSize={fs};fontColor={font_color};opacity={op};" '
            f'vertex="1" parent="1">\n'
            f'      <mxGeometry x="{tx:.2f}" y="{ty:.2f}" width="{est_w:.2f}" height="{est_h:.2f}" as="geometry"/>\n'
            f'    </mxCell>'
        )

    def emit_polyline(self, elem, m, closed=False):
        v = get_visual(elem)
        coords = re.findall(r'[-\d.]+', elem.get('points', ''))
        pts = [apply_pt(m, float(coords[i]), float(coords[i+1]))
               for i in range(0, len(coords)-1, 2)]
        if len(pts) < 2:
            return

        sc = v['stroke'] or '#000000'
        fill = v['fill'] or 'none'
        op = int(v['opacity'] * 100)
        sw = v['stroke_width']

        if closed and fill != 'none':
            xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
            bx, by = min(xs), min(ys)
            bw = max(xs) - bx or 1; bh = max(ys) - by or 1
            moves = [f'<move x="{(pts[0][0]-bx)/bw*100:.2f}" y="{(pts[0][1]-by)/bh*100:.2f}"/>']
            moves += [f'<line x="{(px-bx)/bw*100:.2f}" y="{(py-by)/bh*100:.2f}"/>' for px, py in pts[1:]]
            moves.append('<close/>')
            xml = f'<shape w="{bw:.2f}" h="{bh:.2f}"><background><path>{"".join(moves)}</path><fillstroke/></background></shape>'
            b64 = b64encode(xml.encode('utf-8')).decode('ascii')
            cid = self._nid()
            self._add(
                f'    <mxCell id="{cid}" value="" '
                f'style="shape=stencil({b64});fillColor={fill};strokeColor={sc};strokeWidth={sw};opacity={op};" '
                f'vertex="1" parent="1">\n'
                f'      <mxGeometry x="{bx:.2f}" y="{by:.2f}" width="{bw:.2f}" height="{bh:.2f}" as="geometry"/>\n'
                f'    </mxCell>'
            )
        else:
            src, *mid, tgt = pts
            wp = ''.join(f'        <mxPoint x="{px:.2f}" y="{py:.2f}"/>\n' for px, py in mid)
            wp_block = f'      <Array as="points">\n{wp}      </Array>\n' if mid else ''
            cid = self._nid()
            self._add(
                f'    <mxCell id="{cid}" value="" '
                f'style="endArrow=none;html=1;strokeColor={sc};strokeWidth={sw};opacity={op};" '
                f'edge="1" parent="1">\n'
                f'      <mxGeometry relative="1" as="geometry">\n'
                f'        <mxPoint x="{src[0]:.2f}" y="{src[1]:.2f}" as="sourcePoint"/>\n'
                f'        <mxPoint x="{tgt[0]:.2f}" y="{tgt[1]:.2f}" as="targetPoint"/>\n'
                f'{wp_block}'
                f'      </mxGeometry>\n'
                f'    </mxCell>'
            )

    def emit_path(self, elem, m):
        v = get_visual(elem)
        d = elem.get('d', '')
        if not d:
            return

        pts = list(path_points(d))
        if not pts:
            return

        pts_t = [apply_pt(m, px, py) for px, py in pts]
        xs = [p[0] for p in pts_t]; ys = [p[1] for p in pts_t]
        bx, by = min(xs), min(ys)
        bw = max(xs) - bx or 1; bh = max(ys) - by or 1

        # Build stencil from original (untransformed) path coords
        xs0 = [p[0] for p in pts]; ys0 = [p[1] for p in pts]
        ox0, oy0 = min(xs0), min(ys0)
        w0, h0 = max(xs0)-ox0 or 1, max(ys0)-oy0 or 1

        fill = v['fill'] or 'none'
        sc = v['stroke'] or '#000000'
        op = int(v['opacity'] * 100)
        style = make_stencil_style(d, ox0, oy0, w0, h0, fill, sc, v['stroke_width'], op)
        if not style:
            return

        cid = self._nid()
        self._add(
            f'    <mxCell id="{cid}" value="" style="{style}" vertex="1" parent="1">\n'
            f'      <mxGeometry x="{bx:.2f}" y="{by:.2f}" width="{bw:.2f}" height="{bh:.2f}" as="geometry"/>\n'
            f'    </mxCell>'
        )

    # ---- dispatch ----

    def convert(self, elem, parent_m=None):
        if parent_m is None:
            parent_m = IDENTITY[:]
        m = mat_mul(parent_m, parse_transform(elem.get('transform')))
        tag = strip_ns(elem.tag)

        if tag in ('defs', 'title', 'desc', 'metadata', 'style', 'symbol', 'clipPath', 'mask'):
            return
        if tag == 'g':
            for child in elem:
                self.convert(child, m)
        elif tag == 'line':      self.emit_line(elem, m)
        elif tag == 'circle':    self.emit_circle(elem, m)
        elif tag == 'ellipse':   self.emit_ellipse(elem, m)
        elif tag == 'rect':      self.emit_rect(elem, m)
        elif tag == 'text':      self.emit_text(elem, m)
        elif tag == 'polyline':  self.emit_polyline(elem, m, closed=False)
        elif tag == 'polygon':   self.emit_polyline(elem, m, closed=True)
        elif tag == 'path':      self.emit_path(elem, m)
        # <use>, <image>, etc. are silently skipped

    def to_xml(self, title='Diagram'):
        body = '\n'.join(self.cells)
        return (
            '<mxfile>\n'
            f'  <diagram name="{title}">\n'
            '    <mxGraphModel>\n'
            '      <root>\n'
            '        <mxCell id="0"/>\n'
            '        <mxCell id="1" parent="0"/>\n'
            f'{body}\n'
            '      </root>\n'
            '    </mxGraphModel>\n'
            '  </diagram>\n'
            '</mxfile>\n'
        )


# ── Entry point ──────────────────────────────────────────────────────────────

def convert_file(svg_path, out_path=None):
    tree = ET.parse(svg_path)
    root = tree.getroot()
    title = path.splitext(path.basename(svg_path))[0]
    conv = Converter()
    # The SVG root itself may have a transform from its viewBox; skip it — use child elements directly.
    for child in root:
        conv.convert(child)
    xml = conv.to_xml(title)
    if out_path is None:
        out_path = path.splitext(svg_path)[0] + '.drawio'
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(xml)
    return out_path


if __name__ == '__main__':
    try:
        input_path = argv[1]
    except IndexError:
        input_path = input('Enter SVG file or folder path: ')

    if path.isdir(input_path):
        svgs = [f for f in listdir(input_path) if f.endswith('.svg')]
        if not svgs:
            print('No SVG files found in folder.')
        for fname in svgs:
            fp = path.join(input_path, fname)
            out = convert_file(fp)
            print(f'Converted: {fname} -> {path.basename(out)}')
    elif path.isfile(input_path) and input_path.endswith('.svg'):
        out = convert_file(input_path)
        print(f'Converted: {path.basename(input_path)} -> {path.basename(out)}')
    else:
        print(f'Error: "{input_path}" is not a valid SVG file or directory.')
