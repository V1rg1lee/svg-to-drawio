import re

from ..transforms import apply_pt, stroke_scale
from ..styles import get_visual, opacity_pct
from ..path_utils import make_stencil_style_from_xml
from ..utils import tooltip_style, link_style


def emit_polyline(conv, elem, m, closed=False, css=None):
    v = get_visual(elem, css)
    coords = re.findall(r'[-\d.eE+]+', elem.get('points', ''))
    pts = [apply_pt(m, float(coords[i]), float(coords[i+1]))
           for i in range(0, len(coords) - 1, 2)]
    if len(pts) < 2:
        return

    sc   = v['stroke'] or '#000000'
    fill = v['fill']   or 'none'
    op   = opacity_pct(v['opacity'])
    fill_op = opacity_pct(v['fill_opacity'])
    stroke_op = opacity_pct(v['stroke_opacity'])
    sw   = v['stroke_width'] * stroke_scale(m)
    dash = v['dash_style']
    tip  = tooltip_style(elem)
    lnk  = link_style(conv)
    filt = conv.defs.resolve_filter(v['filter'])
    lc = v['linecap']
    lj = v['linejoin']
    lc_style = f'lineCap={lc};' if lc != 'flat' else ''
    lj_style = f'lineJoin={lj};' if lj != 'miter' else ''

    if closed and fill != 'none':
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        bx, by = min(xs), min(ys)
        bw = max(xs) - bx or 1; bh = max(ys) - by or 1
        moves = [f'<move x="{(pts[0][0]-bx)/bw*100:.2f}" y="{(pts[0][1]-by)/bh*100:.2f}"/>']
        moves += [f'<line x="{(px-bx)/bw*100:.2f}" y="{(py-by)/bh*100:.2f}"/>' for px, py in pts[1:]]
        moves.append('<close/>')
        xml = ('<shape w="100" h="100" aspect="variable" strokewidth="inherit">'
               f'<background><path>{"".join(moves)}</path><fillstroke/></background></shape>')
        style = make_stencil_style_from_xml(xml, fill, sc, sw, op)
        if not style:
            return
        cid = conv.next_id()
        conv.add(
            f'    <mxCell id="{cid}" value="" '
            f'style="{style}fillOpacity={fill_op};strokeOpacity={stroke_op};{dash}{tip}{lnk}{filt}" '
            f'vertex="1" parent="{conv.parent_id}">\n'
            f'      <mxGeometry x="{bx:.2f}" y="{by:.2f}" width="{bw:.2f}" height="{bh:.2f}" as="geometry"/>\n'
            f'    </mxCell>'
        )
    else:
        s_arrow = conv.defs.resolve_marker(v['marker_start'])
        e_arrow = conv.defs.resolve_marker(v['marker_end'])
        src, *mid, tgt = pts
        wp = ''.join(f'        <mxPoint x="{px:.2f}" y="{py:.2f}"/>\n' for px, py in mid)
        wp_block = f'      <Array as="points">\n{wp}      </Array>\n' if mid else ''
        rounded_style = 'rounded=1;' if lj == 'round' else 'rounded=0;'
        cid = conv.next_id()
        conv.add(
            f'    <mxCell id="{cid}" value="" '
            f'style="{rounded_style}{lc_style}{lj_style}startArrow={s_arrow};endArrow={e_arrow};html=1;'
            f'strokeColor={sc};strokeWidth={sw};opacity={op};strokeOpacity={stroke_op};{dash}{tip}{lnk}{filt}" '
            f'edge="1" parent="{conv.parent_id}">\n'
            f'      <mxGeometry relative="1" as="geometry">\n'
            f'        <mxPoint x="{src[0]:.2f}" y="{src[1]:.2f}" as="sourcePoint"/>\n'
            f'        <mxPoint x="{tgt[0]:.2f}" y="{tgt[1]:.2f}" as="targetPoint"/>\n'
            f'{wp_block}'
            f'      </mxGeometry>\n'
            f'    </mxCell>'
        )

        # Feature 14: marker-mid - emit small marker dots at intermediate waypoints
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
