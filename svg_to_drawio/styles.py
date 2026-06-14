import re
import math

from .utils import parse_float, parse_length

_LINECAP = {'butt': 'flat', 'round': 'round', 'square': 'square'}
_LINEJOIN = {'miter': 'miter', 'round': 'round', 'bevel': 'bevel'}
_RGBA_RE = re.compile(
    r'rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)'
    r'(?:\s*,\s*([^)]+))?\s*\)',
    re.IGNORECASE,
)
_HSL_RE = re.compile(
    r'hsla?\(\s*([\d.]+)\s*,\s*([\d.]+)%\s*,\s*([\d.]+)%'
    r'(?:\s*,\s*([^)]+))?\s*\)',
    re.IGNORECASE,
)


def _hsl_to_rgb(h, s, l):
    """Convert HSL (h in degrees, s and l in 0-1) to (r, g, b) each in 0-255."""
    h = h % 360
    c = (1 - abs(2 * l - 1)) * s
    x = c * (1 - abs((h / 60) % 2 - 1))
    m = l - c / 2
    if h < 60:
        r, g, b = c, x, 0
    elif h < 120:
        r, g, b = x, c, 0
    elif h < 180:
        r, g, b = 0, c, x
    elif h < 240:
        r, g, b = 0, x, c
    elif h < 300:
        r, g, b = x, 0, c
    else:
        r, g, b = c, 0, x
    return int((r + m) * 255), int((g + m) * 255), int((b + m) * 255)


def _clamp01(value):
    return max(0.0, min(1.0, value))


def _parse_alpha(value):
    if value is None:
        return 1.0
    value = str(value).strip()
    if not value:
        return 1.0
    if value.endswith('%'):
        return _clamp01(parse_float(value[:-1]) / 100.0)
    return _clamp01(parse_float(value))


def _paint_with_alpha(c):
    if not c:
        return None, 1.0
    c = str(c).strip()
    if c.lower() in ('none', 'transparent'):
        return 'none', 1.0
    m = _RGBA_RE.match(c)
    if m:
        color = '#{:02x}{:02x}{:02x}'.format(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        return color, _parse_alpha(m.group(4))
    mh = _HSL_RE.match(c)
    if mh:
        r, g, b = _hsl_to_rgb(float(mh.group(1)), float(mh.group(2)) / 100, float(mh.group(3)) / 100)
        return '#{:02x}{:02x}{:02x}'.format(r, g, b), _parse_alpha(mh.group(4))
    m3 = re.match(r'^#([0-9a-fA-F]{3})$', c)
    if m3:
        h = m3.group(1)
        return '#{0}{0}{1}{1}{2}{2}'.format(h[0], h[1], h[2]), 1.0
    return c, 1.0


def opacity_pct(value):
    return int(round(_clamp01(value) * 100))


def normalize_color(c):
    return _paint_with_alpha(c)[0]


def get_visual(elem, computed_css=None):
    """
    Extract visual properties for an element.
    computed_css: dict from css.apply_css (inherited + class CSS + inline style).
    Direct SVG presentation attributes are the lowest-priority fallback.
    """
    css = computed_css or {}

    def g(attr, default=None):
        return css.get(attr) or elem.get(attr) or default

    # Resolve currentColor to the inherited 'color' property
    def resolve_color(val):
        if val and val.strip().lower() == 'currentcolor':
            return css.get('color') or elem.get('color') or '#000000'
        return val

    da = g('stroke-dasharray')
    dash_style = ''
    if da and da.lower() not in ('none', '0'):
        nums = re.findall(r'[\d.]+', da)
        if nums:
            dash_style = 'dashed=1;dashPattern={};'.format(' '.join(nums))

    fill_raw = resolve_color(g('fill', 'none'))
    stroke_raw = resolve_color(g('stroke', 'none'))
    text_fill_raw = resolve_color(g('fill', '#000000'))

    fill, fill_alpha = _paint_with_alpha(fill_raw)
    stroke, stroke_alpha = _paint_with_alpha(stroke_raw)
    text_fill, text_alpha = _paint_with_alpha(text_fill_raw)
    opacity = _clamp01(parse_float(g('opacity', '1')))
    fill_opacity = _clamp01(parse_float(g('fill-opacity', '1')) * fill_alpha)
    stroke_opacity = _clamp01(parse_float(g('stroke-opacity', '1')) * stroke_alpha)
    text_opacity = _clamp01(parse_float(g('fill-opacity', '1')) * text_alpha)

    return {
        'fill':           fill,
        'stroke':         stroke,
        'stroke_width':   parse_length(g('stroke-width', '1')),
        'opacity':        opacity,
        'fill_opacity':   fill_opacity,
        'stroke_opacity': stroke_opacity,
        'font_size':      parse_float(re.sub(r'[^\d.]', '', g('font-size', '12'))),
        'font_family':    g('font-family', 'Helvetica'),
        'text_anchor':    g('text-anchor', 'start'),
        'text_fill':      text_fill,
        'text_opacity':   text_opacity,
        'font_weight':    g('font-weight', 'normal'),
        'font_style_v':   g('font-style', 'normal'),
        'linecap':        _LINECAP.get(g('stroke-linecap', 'butt'), 'flat'),
        'linejoin':       _LINEJOIN.get(g('stroke-linejoin', 'miter'), 'miter'),
        'dash_style':     dash_style,
        'marker_start':   g('marker-start'),
        'marker_end':     g('marker-end'),
        'marker_mid':     g('marker-mid'),
        'filter':         g('filter'),
        'fill_rule':      g('fill-rule', 'nonzero'),
        'text_decoration': g('text-decoration', 'none'),
    }


def gradient_style(grad):
    """Build draw.io gradient style fragment from a gradient definition dict."""
    if not grad:
        return ''
    if grad.get('direction') == 'radial':
        return f'fillStyle=5;gradientColor={grad["color2"]};'
    return f'fillStyle=1;gradientColor={grad["color2"]};gradientDirection={grad["direction"]};'


def font_style_flag(v):
    """draw.io fontStyle bitmask: 1=bold, 2=italic, 4=underline, 8=line-through."""
    bold = 1 if v.get('font_weight') in ('bold', '700', '800', '900') else 0
    italic = 2 if v.get('font_style_v') == 'italic' else 0
    td = v.get('text_decoration', 'none') or 'none'
    underline = 4 if 'underline' in td else 0
    strikethrough = 8 if 'line-through' in td else 0
    return bold | italic | underline | strikethrough
