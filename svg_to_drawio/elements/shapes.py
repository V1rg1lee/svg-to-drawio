import math

from ..transforms import apply_pt, scale_x, scale_y, stroke_scale
from ..styles import get_visual, gradient_style, opacity_pct
from ..path_utils import (
    path_commands,
    commands_bbox,
    make_stencil_style_from_commands,
    make_stencil_style_from_xml,
)
from ..utils import parse_length, tooltip_style, link_style


def _rotation_deg(m):
    """Rotation angle (degrees, clockwise) encoded in the transform matrix."""
    return math.degrees(math.atan2(m[1], m[0]))


def _has_shear(m):
    """True when the matrix has a shear component (column vectors not perpendicular)."""
    return abs(m[0] * m[2] + m[1] * m[3]) > 1e-6


def _polygon_stencil(conv, elem, corners, fill, grad, stroke, sw, op, fill_op, stroke_op, dash=''):
    """
    Emit a closed polygon stencil from a list of (x, y) points in draw.io space.
    Used when a shape cannot be represented as an axis-aligned rectangle.
    """
    xs = [c[0] for c in corners]
    ys = [c[1] for c in corners]
    bx, by = min(xs), min(ys)
    bw = max(xs) - bx or 1
    bh = max(ys) - by or 1

    def nx(x):
        return (x - bx) / bw * 100

    def ny(y):
        return (y - by) / bh * 100

    path_xml = f'<move x="{nx(corners[0][0]):.2f}" y="{ny(corners[0][1]):.2f}"/>'
    for cx, cy in corners[1:]:
        path_xml += f'<line x="{nx(cx):.2f}" y="{ny(cy):.2f}"/>'
    path_xml += '<close/>'

    xml = ('<shape w="100" h="100" aspect="variable" strokewidth="inherit">'
           f'<background><path>{path_xml}</path><fillstroke/></background></shape>')
    style = make_stencil_style_from_xml(xml, fill, stroke, sw, op)
    if not style:
        return
    tip = tooltip_style(elem)
    lnk = link_style(conv)
    cid = conv.next_id()
    conv.add(
        f'    <mxCell id="{cid}" value="" '
        f'style="{style}fillOpacity={fill_op};strokeOpacity={stroke_op};{gradient_style(grad)}{dash}{tip}{lnk}" '
        f'vertex="1" parent="{conv.parent_id}">\n'
        f'      <mxGeometry x="{bx:.2f}" y="{by:.2f}" width="{bw:.2f}" height="{bh:.2f}" as="geometry"/>\n'
        f'    </mxCell>'
    )


def _emit_stencil_commands(conv, elem, commands, fill, grad, stroke, sw, op, fill_op, stroke_op,
                            dash='', fill_rule='nonzero', linecap='flat', linejoin='miter'):
    bbox = commands_bbox(commands)
    if not bbox:
        return
    bx, by, bw, bh = bbox
    style = make_stencil_style_from_commands(
        commands, bx, by, bw, bh, fill, stroke, sw, op,
        fill_rule=fill_rule, linecap=linecap, linejoin=linejoin
    )
    if not style:
        return
    tip = tooltip_style(elem)
    lnk = link_style(conv)
    cid = conv.next_id()
    conv.add(
        f'    <mxCell id="{cid}" value="" '
        f'style="{style}fillOpacity={fill_op};strokeOpacity={stroke_op};{gradient_style(grad)}{dash}{tip}{lnk}" '
        f'vertex="1" parent="{conv.parent_id}">\n'
        f'      <mxGeometry x="{bx:.2f}" y="{by:.2f}" width="{bw:.2f}" height="{bh:.2f}" as="geometry"/>\n'
        f'    </mxCell>'
    )


def _emit_transformed_path_stencil(conv, elem, d, m, fill, grad, stroke, sw, op, fill_op, stroke_op,
                                    dash='', linecap='flat', linejoin='miter'):
    commands = path_commands(d, point_transform=lambda x, y: apply_pt(m, x, y))
    _emit_stencil_commands(conv, elem, commands, fill, grad, stroke, sw, op, fill_op, stroke_op,
                           dash, linecap=linecap, linejoin=linejoin)


def _ellipse_path_d(cx, cy, rx, ry):
    return (
        f'M {cx - rx:.6f} {cy:.6f} '
        f'A {rx:.6f} {ry:.6f} 0 1 0 {cx + rx:.6f} {cy:.6f} '
        f'A {rx:.6f} {ry:.6f} 0 1 0 {cx - rx:.6f} {cy:.6f} Z'
    )


def _rect_path_d(x, y, w, h):
    return f'M {x:.6f} {y:.6f} H {x + w:.6f} V {y + h:.6f} H {x:.6f} Z'


def _rounded_rect_path_d(x, y, w, h, rx, ry):
    rx = max(0.0, min(rx, w / 2))
    ry = max(0.0, min(ry, h / 2))
    if rx == 0 or ry == 0:
        return _rect_path_d(x, y, w, h)
    return (
        f'M {x + rx:.6f} {y:.6f} '
        f'H {x + w - rx:.6f} '
        f'A {rx:.6f} {ry:.6f} 0 0 1 {x + w:.6f} {y + ry:.6f} '
        f'V {y + h - ry:.6f} '
        f'A {rx:.6f} {ry:.6f} 0 0 1 {x + w - rx:.6f} {y + h:.6f} '
        f'H {x + rx:.6f} '
        f'A {rx:.6f} {ry:.6f} 0 0 1 {x:.6f} {y + h - ry:.6f} '
        f'V {y + ry:.6f} '
        f'A {rx:.6f} {ry:.6f} 0 0 1 {x + rx:.6f} {y:.6f} Z'
    )


def emit_line(conv, elem, m, css=None):
    v = get_visual(elem, css)
    x1, y1 = apply_pt(m, parse_length(elem.get('x1')), parse_length(elem.get('y1')))
    x2, y2 = apply_pt(m, parse_length(elem.get('x2')), parse_length(elem.get('y2')))
    sc = v['stroke'] or '#000000'
    op = opacity_pct(v['opacity'])
    stroke_op = opacity_pct(v['stroke_opacity'])
    sw = v['stroke_width'] * stroke_scale(m)
    s_arrow = conv.defs.resolve_marker(v['marker_start'])
    e_arrow = conv.defs.resolve_marker(v['marker_end'])
    dash = v['dash_style']
    tip = tooltip_style(elem)
    lnk = link_style(conv)
    filt = conv.defs.resolve_filter(v['filter'])
    lc = v['linecap']
    lc_style = f'lineCap={lc};' if lc != 'flat' else ''
    cid = conv.next_id()
    conv.add(
        f'    <mxCell id="{cid}" value="" '
        f'style="rounded=0;{lc_style}startArrow={s_arrow};endArrow={e_arrow};html=1;'
        f'strokeColor={sc};strokeWidth={sw:.2f};opacity={op};strokeOpacity={stroke_op};{dash}{tip}{lnk}{filt}" '
        f'edge="1" parent="{conv.parent_id}">\n'
        f'      <mxGeometry relative="1" as="geometry">\n'
        f'        <mxPoint x="{x1:.2f}" y="{y1:.2f}" as="sourcePoint"/>\n'
        f'        <mxPoint x="{x2:.2f}" y="{y2:.2f}" as="targetPoint"/>\n'
        f'      </mxGeometry>\n'
        f'    </mxCell>'
    )


def emit_circle(conv, elem, m, css=None):
    v = get_visual(elem, css)
    cx0 = parse_length(elem.get('cx'))
    cy0 = parse_length(elem.get('cy'))
    r = parse_length(elem.get('r'))
    fill, grad = conv.defs.resolve_fill(v['fill'] or 'none')
    stroke = v['stroke'] or 'none'
    op = opacity_pct(v['opacity'])
    fill_op = opacity_pct(v['fill_opacity'])
    stroke_op = opacity_pct(v['stroke_opacity'])
    sw = v['stroke_width'] * stroke_scale(m)
    dash = v['dash_style']
    tip = tooltip_style(elem)
    lnk = link_style(conv)
    filt = conv.defs.resolve_filter(v['filter'])

    if _has_shear(m):
        _emit_transformed_path_stencil(
            conv, elem,
            _ellipse_path_d(cx0, cy0, r, r),
            m, fill, grad, stroke, sw, op, fill_op, stroke_op, dash,
            linecap=v['linecap'], linejoin=v['linejoin'],
        )
        return

    cx, cy = apply_pt(m, cx0, cy0)
    rx = r * scale_x(m)
    ry = r * scale_y(m)
    angle = _rotation_deg(m)
    rot_style = f'rotation={angle:.2f};' if abs(angle) > 0.01 and abs(rx - ry) > 0.01 else ''
    cid = conv.next_id()
    conv.add(
        f'    <mxCell id="{cid}" value="" '
        f'style="ellipse;whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};'
        f'strokeWidth={sw};opacity={op};fillOpacity={fill_op};strokeOpacity={stroke_op};'
        f'{gradient_style(grad)}{dash}{rot_style}{tip}{lnk}{filt}" '
        f'vertex="1" parent="{conv.parent_id}">\n'
        f'      <mxGeometry x="{cx - rx:.2f}" y="{cy - ry:.2f}" width="{rx * 2:.2f}" height="{ry * 2:.2f}" as="geometry"/>\n'
        f'    </mxCell>'
    )


def emit_ellipse(conv, elem, m, css=None):
    v = get_visual(elem, css)
    cx0 = parse_length(elem.get('cx'))
    cy0 = parse_length(elem.get('cy'))
    rx0 = parse_length(elem.get('rx'))
    ry0 = parse_length(elem.get('ry'))
    fill, grad = conv.defs.resolve_fill(v['fill'] or 'none')
    stroke = v['stroke'] or 'none'
    op = opacity_pct(v['opacity'])
    fill_op = opacity_pct(v['fill_opacity'])
    stroke_op = opacity_pct(v['stroke_opacity'])
    sw = v['stroke_width'] * stroke_scale(m)
    dash = v['dash_style']
    tip = tooltip_style(elem)
    lnk = link_style(conv)
    filt = conv.defs.resolve_filter(v['filter'])

    if _has_shear(m):
        _emit_transformed_path_stencil(
            conv, elem,
            _ellipse_path_d(cx0, cy0, rx0, ry0),
            m, fill, grad, stroke, sw, op, fill_op, stroke_op, dash,
            linecap=v['linecap'], linejoin=v['linejoin'],
        )
        return

    cx, cy = apply_pt(m, cx0, cy0)
    rx = rx0 * scale_x(m)
    ry = ry0 * scale_y(m)
    angle = _rotation_deg(m)
    rot_style = f'rotation={angle:.2f};' if abs(angle) > 0.01 else ''
    cid = conv.next_id()
    conv.add(
        f'    <mxCell id="{cid}" value="" '
        f'style="ellipse;whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};'
        f'strokeWidth={sw};opacity={op};fillOpacity={fill_op};strokeOpacity={stroke_op};'
        f'{gradient_style(grad)}{dash}{rot_style}{tip}{lnk}{filt}" '
        f'vertex="1" parent="{conv.parent_id}">\n'
        f'      <mxGeometry x="{cx - rx:.2f}" y="{cy - ry:.2f}" width="{rx * 2:.2f}" height="{ry * 2:.2f}" as="geometry"/>\n'
        f'    </mxCell>'
    )


def emit_rect(conv, elem, m, css=None):
    v = get_visual(elem, css)
    x0 = parse_length(elem.get('x'))
    y0 = parse_length(elem.get('y'))
    w0 = parse_length(elem.get('width'))
    h0 = parse_length(elem.get('height'))
    rx = parse_length(elem.get('rx', '0')) or 0.0
    ry = parse_length(elem.get('ry', '0')) or 0.0
    if rx <= 0 < ry:
        rx = ry
    if ry <= 0 < rx:
        ry = rx

    fill, grad = conv.defs.resolve_fill(v['fill'] or '#ffffff')
    stroke = v['stroke'] or 'none'
    op = opacity_pct(v['opacity'])
    fill_op = opacity_pct(v['fill_opacity'])
    stroke_op = opacity_pct(v['stroke_opacity'])
    sw = v['stroke_width'] * stroke_scale(m)
    dash = v['dash_style']
    tip = tooltip_style(elem)
    lnk = link_style(conv)
    filt = conv.defs.resolve_filter(v['filter'])

    if _has_shear(m):
        if rx > 0 or ry > 0:
            _emit_transformed_path_stencil(
                conv, elem,
                _rounded_rect_path_d(x0, y0, w0, h0, rx, ry),
                m, fill, grad, stroke, sw, op, fill_op, stroke_op, dash,
                linecap=v['linecap'], linejoin=v['linejoin'],
            )
            return
        corners = [
            apply_pt(m, x0, y0),
            apply_pt(m, x0 + w0, y0),
            apply_pt(m, x0 + w0, y0 + h0),
            apply_pt(m, x0, y0 + h0),
        ]
        _polygon_stencil(conv, elem, corners, fill, grad, stroke, sw, op, fill_op, stroke_op, dash)
        return

    cx, cy = apply_pt(m, x0 + w0 / 2, y0 + h0 / 2)
    w = w0 * scale_x(m)
    h = h0 * scale_y(m)
    angle = _rotation_deg(m)
    rot_style = f'rotation={angle:.2f};' if abs(angle) > 0.01 else ''
    if rx > 0 or ry > 0:
        shorter = min(w0, h0) if w0 > 0 and h0 > 0 else 1.0
        arc_pct = min(50, round(max(rx, ry) / shorter * 100))
        rounded = f'rounded=1;arcSize={arc_pct};'
    else:
        rounded = 'rounded=0;'
    cid = conv.next_id()
    conv.add(
        f'    <mxCell id="{cid}" value="" '
        f'style="{rounded}whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};'
        f'strokeWidth={sw};opacity={op};fillOpacity={fill_op};strokeOpacity={stroke_op};'
        f'{gradient_style(grad)}{dash}{rot_style}{tip}{lnk}{filt}" '
        f'vertex="1" parent="{conv.parent_id}">\n'
        f'      <mxGeometry x="{cx - w / 2:.2f}" y="{cy - h / 2:.2f}" width="{w:.2f}" height="{h:.2f}" as="geometry"/>\n'
        f'    </mxCell>'
    )
