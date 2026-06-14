from ..transforms import apply_pt
from ..styles import get_visual, font_style_flag, opacity_pct
from ..utils import parse_float, parse_length, parse_style_attr, strip_ns, tooltip_style, link_style

# Tspan attributes that require separate cell rendering
_TSPAN_STYLE_ATTRS = (
    'x', 'y', 'dy', 'dx',
    'fill', 'font-size', 'font-weight', 'font-style',
    'font-family', 'text-decoration', 'text-anchor', 'style',
)


def _emit_text_cell(conv, elem, m, v, x0, y0, content):
    font_color = v['text_fill'] or '#000000'
    fs = max(v['font_size'], 6)
    font_family = v.get('font_family') or 'Helvetica'
    op = opacity_pct(v['opacity'] * v['text_opacity'])
    align = {'start': 'left', 'middle': 'center', 'end': 'right'}.get(v['text_anchor'], 'left')
    fs_flag = font_style_flag(v)
    tip = tooltip_style(elem)
    lnk = link_style(conv)
    filt = conv.defs.resolve_filter(v['filter'])

    x, y = apply_pt(m, x0, y0)
    est_w = max(len(content) * fs * 0.62, 20)
    est_h = fs * 1.8
    tx = x - (est_w / 2 if align == 'center' else est_w if align == 'right' else 0)
    ty = y - fs * 0.85

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
        f'fontSize={fs};fontColor={font_color};fontFamily={font_family};'
        f'opacity={op};fontStyle={fs_flag};{tip}{lnk}{filt}" '
        f'vertex="1" parent="{conv.parent_id}">\n'
        f'      <mxGeometry x="{tx:.2f}" y="{ty:.2f}" width="{est_w:.2f}" height="{est_h:.2f}" as="geometry"/>\n'
        f'    </mxCell>'
    )


def _collect_text(elem):
    """Collect all text content from a <text> element, ignoring tspan styling."""
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


def _has_styled_tspans(elem):
    """Return True if any tspan child needs its own cell (has positioning or style attrs)."""
    for child in elem:
        if strip_ns(child.tag) == 'tspan':
            if any(child.get(a) for a in _TSPAN_STYLE_ATTRS):
                return True
    return False


def _tspan_visual(tspan, parent_css):
    """Build a visual dict for a tspan, merging parent CSS with tspan's own attributes."""
    ts_css = dict(parent_css or {})
    ts_css.update(parse_style_attr(tspan.get('style', '')))
    for attr in ('fill', 'font-size', 'font-weight', 'font-style',
                 'font-family', 'text-decoration', 'text-anchor'):
        val = tspan.get(attr)
        if val:
            ts_css[attr] = val
    return get_visual(tspan, ts_css)


def emit_text(conv, elem, m, css=None):
    v = get_visual(elem, css)
    x0 = parse_length(elem.get('x'))
    y0 = parse_length(elem.get('y'))

    if _has_styled_tspans(elem):
        cur_x, cur_y = x0, y0

        # Text node before first tspan
        if elem.text and elem.text.strip():
            content = elem.text.strip()
            _emit_text_cell(conv, elem, m, v, cur_x, cur_y, content)
            cur_x += len(content) * max(v['font_size'], 6) * 0.62

        for tspan in elem:
            if strip_ns(tspan.tag) != 'tspan':
                continue

            # Update position: explicit x/y reset; dy/dx advance
            if tspan.get('x'):
                cur_x = parse_length(tspan.get('x'))
            if tspan.get('y'):
                cur_y = parse_length(tspan.get('y'))
            if tspan.get('dy'):
                cur_y += parse_float(tspan.get('dy'))
            if tspan.get('dx'):
                cur_x += parse_float(tspan.get('dx'))

            raw = tspan.text or ''
            content = raw.strip()
            if not content:
                # Still advance by whitespace width
                cur_x += len(raw) * max(v['font_size'], 6) * 0.62
                continue

            ts_v = _tspan_visual(tspan, css)
            fs = max(ts_v['font_size'], 6)

            # Whitespace prefix advances x before rendering the word
            prefix_spaces = len(raw) - len(raw.lstrip())
            cur_x += prefix_spaces * fs * 0.62

            _emit_text_cell(conv, elem, m, ts_v, cur_x, cur_y, content)
            cur_x += len(content) * fs * 0.62

            # Tail text (after closing </tspan>) rendered with parent style
            tail = tspan.tail or ''
            tail_content = tail.strip()
            if tail_content:
                prefix_spaces = len(tail) - len(tail.lstrip())
                cur_x += prefix_spaces * max(v['font_size'], 6) * 0.62
                _emit_text_cell(conv, elem, m, v, cur_x, cur_y, tail_content)
                cur_x += len(tail_content) * max(v['font_size'], 6) * 0.62
        return

    content = _collect_text(elem)
    if not content:
        return
    _emit_text_cell(conv, elem, m, v, x0, y0, content)
