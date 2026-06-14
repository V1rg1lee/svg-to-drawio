from ..transforms import apply_pt
from ..styles import get_visual, font_style_flag, opacity_pct
from ..utils import parse_float, strip_ns


def _collect_text(elem):
    """Recursively collect text content from a <text> element and its <tspan> children."""
    parts = []
    if elem.text:
        parts.append(elem.text)
    for child in elem:
        if strip_ns(child.tag) == 'tspan':
            if child.text:
                parts.append(child.text)
            if child.tail:
                parts.append(child.tail)
    return ''.join(parts).strip()


def emit_text(conv, elem, m, css=None):
    v = get_visual(elem, css)
    x0 = parse_float(elem.get('x'))
    y0 = parse_float(elem.get('y'))
    x, y = apply_pt(m, x0, y0)

    content = _collect_text(elem)
    if not content:
        return

    font_color = v['text_fill'] or '#000000'
    fs = max(v['font_size'], 6)
    op = opacity_pct(v['opacity'] * v['text_opacity'])
    align = {'start': 'left', 'middle': 'center', 'end': 'right'}.get(v['text_anchor'], 'left')
    fs_flag = font_style_flag(v)

    est_w = max(len(content) * fs * 0.62, 20)
    est_h = fs * 1.8
    tx = x - (est_w / 2 if align == 'center' else est_w if align == 'right' else 0)
    ty = y - fs * 0.85  # SVG y is baseline; shift up

    safe = (content
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;'))
    cid = conv.next_id()
    conv.add(
        f'    <mxCell id="{cid}" value="{safe}" '
        f'style="text;html=1;strokeColor=none;fillColor=none;align={align};'
        f'verticalAlign=middle;whiteSpace=wrap;rounded=0;'
        f'fontSize={fs};fontColor={font_color};opacity={op};fontStyle={fs_flag};" '
        f'vertex="1" parent="1">\n'
        f'      <mxGeometry x="{tx:.2f}" y="{ty:.2f}" width="{est_w:.2f}" height="{est_h:.2f}" as="geometry"/>\n'
        f'    </mxCell>'
    )
