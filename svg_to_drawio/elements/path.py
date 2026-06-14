from ..transforms import apply_pt
from ..styles import get_visual, gradient_style, opacity_pct
from ..path_utils import (
    path_points,
    path_commands,
    commands_bbox,
    make_stencil_style_from_commands,
)


def _is_closed(d):
    """Return True if the path data contains a Z/z close command."""
    return bool(d) and any(c in d for c in ('Z', 'z'))


def _emit_open_path_as_edge(conv, d, pts, m, v):
    """
    Render an open, unfilled path as a draw.io curved edge through key waypoints.
    draw.io cannot represent arbitrary bezier curves natively, so we approximate
    by passing the sampled key points and enabling curved routing.
    """
    pts_t = [apply_pt(m, px, py) for px, py in pts]
    if len(pts_t) < 2:
        return

    sc = v['stroke'] or '#000000'
    op = opacity_pct(v['opacity'])
    stroke_op = opacity_pct(v['stroke_opacity'])
    sw = v['stroke_width']
    dash = v['dash_style']
    s_arrow = conv.defs.resolve_marker(v['marker_start'])
    e_arrow = conv.defs.resolve_marker(v['marker_end'])

    src, *mid, tgt = pts_t
    wp = ''.join(f'        <mxPoint x="{px:.2f}" y="{py:.2f}"/>\n' for px, py in mid)
    wp_block = f'      <Array as="points">\n{wp}      </Array>\n' if mid else ''

    cid = conv.next_id()
    conv.add(
        f'    <mxCell id="{cid}" value="" '
        f'style="curved=1;startArrow={s_arrow};endArrow={e_arrow};html=1;'
        f'strokeColor={sc};strokeWidth={sw};opacity={op};strokeOpacity={stroke_op};{dash}" '
        f'edge="1" parent="1">\n'
        f'      <mxGeometry relative="1" as="geometry">\n'
        f'        <mxPoint x="{src[0]:.2f}" y="{src[1]:.2f}" as="sourcePoint"/>\n'
        f'        <mxPoint x="{tgt[0]:.2f}" y="{tgt[1]:.2f}" as="targetPoint"/>\n'
        f'{wp_block}'
        f'      </mxGeometry>\n'
        f'    </mxCell>'
    )


def emit_path(conv, elem, m, css=None):
    v = get_visual(elem, css)
    d = elem.get('d', '')
    if not d:
        return

    fill, grad = conv.defs.resolve_fill(v['fill'] or 'none')

    pts = list(path_points(d))
    if not pts:
        return

    # Open + unfilled paths: stencils render as bounding-box rectangles in draw.io
    # because stencils are designed for closed filled shapes. Use a curved edge instead.
    if fill == 'none' and not _is_closed(d):
        _emit_open_path_as_edge(conv, d, pts, m, v)
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
    style = make_stencil_style_from_commands(
        commands, bx, by, bw, bh, fill, sc, v['stroke_width'], op
    )
    if not style:
        return

    extra = f'fillOpacity={fill_op};strokeOpacity={stroke_op};' + gradient_style(grad) + v['dash_style']
    cid = conv.next_id()
    conv.add(
        f'    <mxCell id="{cid}" value="" style="{style}{extra}" vertex="1" parent="1">\n'
        f'      <mxGeometry x="{bx:.2f}" y="{by:.2f}" width="{bw:.2f}" height="{bh:.2f}" as="geometry"/>\n'
        f'    </mxCell>'
    )
