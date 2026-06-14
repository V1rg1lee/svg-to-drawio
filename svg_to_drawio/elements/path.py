from ..transforms import apply_pt, stroke_scale
from ..styles import get_visual, gradient_style, opacity_pct
import re

from ..path_utils import (
    path_points,
    sample_open_path,
    path_commands,
    commands_bbox,
    make_stencil_style_from_commands,
)
from ..utils import tooltip_style, link_style


def _is_closed(d):
    """Return True if the path data contains a Z/z close command."""
    return bool(d) and any(c in d for c in ('Z', 'z'))


def _has_curve_commands(d):
    """Return True if path data contains any bezier or arc curve commands."""
    return bool(re.search(r'[CcSsQqTtAa]', d or ''))


def _emit_open_path_as_edge(conv, elem, d, m, v):
    """
    Render an open, unfilled path as a draw.io edge through sampled on-curve waypoints.
    Uses sample_open_path to get actual on-curve points instead of control points.
    curved=1 is only applied when the path has curve commands AND intermediate waypoints.
    """
    pts_t = [apply_pt(m, px, py) for px, py in sample_open_path(d)]
    if len(pts_t) < 2:
        return

    sc = v['stroke'] or '#000000'
    op = opacity_pct(v['opacity'])
    stroke_op = opacity_pct(v['stroke_opacity'])
    sw = v['stroke_width'] * stroke_scale(m)
    dash = v['dash_style']
    s_arrow = conv.defs.resolve_marker(v['marker_start'])
    e_arrow = conv.defs.resolve_marker(v['marker_end'])
    tip = tooltip_style(elem)
    lnk = link_style(conv)
    filt = conv.defs.resolve_filter(v['filter'])

    src, *mid, tgt = pts_t
    wp = ''.join(f'        <mxPoint x="{px:.2f}" y="{py:.2f}"/>\n' for px, py in mid)
    wp_block = f'      <Array as="points">\n{wp}      </Array>\n' if mid else ''

    curved = 'curved=1;' if (_has_curve_commands(d) and mid) else ''

    cid = conv.next_id()
    conv.add(
        f'    <mxCell id="{cid}" value="" '
        f'style="{curved}startArrow={s_arrow};endArrow={e_arrow};html=1;'
        f'strokeColor={sc};strokeWidth={sw};opacity={op};strokeOpacity={stroke_op};{dash}{tip}{lnk}{filt}" '
        f'edge="1" parent="{conv.parent_id}">\n'
        f'      <mxGeometry relative="1" as="geometry">\n'
        f'        <mxPoint x="{src[0]:.2f}" y="{src[1]:.2f}" as="sourcePoint"/>\n'
        f'        <mxPoint x="{tgt[0]:.2f}" y="{tgt[1]:.2f}" as="targetPoint"/>\n'
        f'{wp_block}'
        f'      </mxGeometry>\n'
        f'    </mxCell>'
    )

    # marker-mid: emit dots at intermediate waypoints
    if v.get('marker_mid') and mid:
        marker_size = 8
        for px, py in mid:
            mcid = conv.next_id()
            conv.add(
                f'    <mxCell id="{mcid}" value="" '
                f'style="ellipse;fillColor={sc};strokeColor={sc};opacity={op};" '
                f'vertex="1" parent="{conv.parent_id}">\n'
                f'      <mxGeometry x="{px - marker_size/2:.2f}" y="{py - marker_size/2:.2f}" '
                f'width="{marker_size}" height="{marker_size}" as="geometry"/>\n'
                f'    </mxCell>'
            )


def emit_path(conv, elem, m, css=None):
    v = get_visual(elem, css)
    d = elem.get('d', '')
    if not d:
        return

    fill, grad = conv.defs.resolve_fill(v['fill'] or 'none')

    # Open + unfilled paths: stencils render as bounding-box rectangles in draw.io
    # because stencils are designed for closed filled shapes. Use an edge instead.
    if fill == 'none' and not _is_closed(d):
        _emit_open_path_as_edge(conv, elem, d, m, v)
        return

    pts = list(path_points(d))
    if not pts:
        return

    commands = path_commands(d, point_transform=lambda x, y: apply_pt(m, x, y))
    bbox = commands_bbox(commands)
    if not bbox:
        return
    bx, by, bw, bh = bbox

    sc = v['stroke'] or '#000000'
    op = opacity_pct(v['opacity'])
    fill_op = opacity_pct(v['fill_opacity'])
    stroke_op = opacity_pct(v['stroke_opacity'])
    tip = tooltip_style(elem)
    lnk = link_style(conv)
    filt = conv.defs.resolve_filter(v['filter'])
    fill_rule = v.get('fill_rule', 'nonzero')

    style = make_stencil_style_from_commands(
        commands, bx, by, bw, bh, fill, sc, v['stroke_width'], op, fill_rule=fill_rule
    )
    if not style:
        return

    extra = (f'fillOpacity={fill_op};strokeOpacity={stroke_op};'
             + gradient_style(grad) + v['dash_style'] + tip + lnk + filt)
    cid = conv.next_id()
    conv.add(
        f'    <mxCell id="{cid}" value="" style="{style}{extra}" vertex="1" parent="{conv.parent_id}">\n'
        f'      <mxGeometry x="{bx:.2f}" y="{by:.2f}" width="{bw:.2f}" height="{bh:.2f}" as="geometry"/>\n'
        f'    </mxCell>'
    )
