import base64
import binascii
import math
import mimetypes
from os import path
from urllib.parse import quote_from_bytes, unquote_to_bytes

from ..styles import get_visual, opacity_pct
from ..transforms import apply_pt, scale_x, scale_y
from ..utils import parse_length, tooltip_style, link_style


def _rotation_deg(m):
    return math.degrees(math.atan2(m[1], m[0]))


def _has_shear(m):
    return abs(m[0] * m[2] + m[1] * m[3]) > 1e-6


def _data_uri_from_bytes(mime, raw_bytes):
    # Use percent-encoded payload instead of ;base64 to keep the draw.io style
    # string free of raw semicolons, which would break style parsing.
    return f'data:{mime},{quote_from_bytes(raw_bytes, safe="")}'


def _base64_data_uri_from_bytes(mime, raw_bytes):
    payload = base64.b64encode(raw_bytes).decode('ascii')
    return f'data:{mime};base64,{payload}'


def _normalize_data_uri(href):
    try:
        header, payload = href.split(',', 1)
    except ValueError:
        return None, None

    media = header[5:] or 'text/plain'
    media_type = media.split(';', 1)[0] or 'text/plain'

    if ';base64' in media.lower():
        try:
            raw = base64.b64decode(payload)
        except (ValueError, binascii.Error):
            return None, None
    else:
        raw = unquote_to_bytes(payload)

    if media_type == 'image/svg+xml':
        return _data_uri_from_bytes(media_type, raw), media_type
    return _base64_data_uri_from_bytes(media_type, raw), media_type


def _escape_xml_attr(value):
    return (value
            .replace('&', '&amp;')
            .replace('"', '&quot;')
            .replace('<', '&lt;')
            .replace('>', '&gt;'))


def _svg_wrapper_data_uri(image_ref, width, height, preserve):
    preserve = preserve or 'xMidYMid meet'
    safe_href = _escape_xml_attr(image_ref)
    safe_preserve = _escape_xml_attr(preserve)
    svg = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.6f} {height:.6f}" '
        f'width="{width:.6f}" height="{height:.6f}">\n'
        f'  <image href="{safe_href}" x="0" y="0" width="{width:.6f}" height="{height:.6f}" '
        f'preserveAspectRatio="{safe_preserve}"/>\n'
        '</svg>\n'
    )
    return _data_uri_from_bytes('image/svg+xml', svg.encode('utf-8'))


def _resolve_image_href(conv, href):
    if not href:
        return None, None

    href = href.strip()
    if not href:
        return None, None

    if href.startswith('data:'):
        return _normalize_data_uri(href)

    if '://' in href:
        mime = mimetypes.guess_type(href)[0] or ''
        return href, mime

    source_dir = getattr(conv, 'source_dir', '')
    asset_path = href
    if not path.isabs(asset_path):
        asset_path = path.join(source_dir, asset_path)
    asset_path = path.normpath(asset_path)
    if not path.isfile(asset_path):
        return None, None

    mime = mimetypes.guess_type(asset_path)[0] or 'application/octet-stream'
    with open(asset_path, 'rb') as f:
        raw = f.read()
    if mime == 'image/svg+xml':
        return _data_uri_from_bytes(mime, raw), mime
    return _base64_data_uri_from_bytes(mime, raw), mime


def emit_image(conv, elem, m, css=None):
    href = (elem.get('href') or
            elem.get('{http://www.w3.org/1999/xlink}href') or '')
    image_ref, mime = _resolve_image_href(conv, href)
    if not image_ref:
        return

    x0 = parse_length(elem.get('x'))
    y0 = parse_length(elem.get('y'))
    w0 = parse_length(elem.get('width'))
    h0 = parse_length(elem.get('height'))
    if w0 <= 0 or h0 <= 0:
        return

    v = get_visual(elem, css)
    op = opacity_pct(v['opacity'])
    tip = tooltip_style(elem)
    lnk = link_style(conv)

    if _has_shear(m):
        corners = [
            apply_pt(m, x0, y0),
            apply_pt(m, x0 + w0, y0),
            apply_pt(m, x0 + w0, y0 + h0),
            apply_pt(m, x0, y0 + h0),
        ]
        xs = [c[0] for c in corners]
        ys = [c[1] for c in corners]
        bx = min(xs)
        by = min(ys)
        bw = max(xs) - bx or 1.0
        bh = max(ys) - by or 1.0
        rot_style = ''
    else:
        cx, cy = apply_pt(m, x0 + w0 / 2, y0 + h0 / 2)
        bw = w0 * scale_x(m)
        bh = h0 * scale_y(m)
        bx = cx - bw / 2
        by = cy - bh / 2
        angle = _rotation_deg(m)
        rot_style = f'rotation={angle:.2f};' if abs(angle) > 0.01 else ''

    preserve_raw = (elem.get('preserveAspectRatio') or '').strip()
    preserve = preserve_raw.lower()
    aspect_style = 'imageAspect=0;' if preserve == 'none' else 'imageAspect=1;'
    if mime and mime != 'image/svg+xml':
        image_ref = _svg_wrapper_data_uri(image_ref, w0, h0, preserve_raw)

    cid = conv.next_id()
    conv.add(
        f'    <mxCell id="{cid}" value="" '
        f'style="shape=image;html=1;image={image_ref};'
        f'aspect=fixed;{aspect_style}opacity={op};strokeColor=none;fillColor=none;'
        f'{rot_style}{tip}{lnk}" '
        f'vertex="1" parent="{conv.parent_id}">\n'
        f'      <mxGeometry x="{bx:.2f}" y="{by:.2f}" width="{bw:.2f}" height="{bh:.2f}" as="geometry"/>\n'
        f'    </mxCell>'
    )
