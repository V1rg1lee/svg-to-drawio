import re

_UNIT_TO_PX = {
    'px': 1.0,
    'pt': 4.0 / 3.0,
    'pc': 16.0,
    'in': 96.0,
    'cm': 96.0 / 2.54,
    'mm': 96.0 / 25.4,
}


def strip_ns(tag):
    return tag.split('}', 1)[1] if '}' in tag else tag


def parse_float(val, default=0.0):
    if val is None:
        return default
    try:
        cleaned = re.sub(r'[^\d.eE+\-]', '', str(val))
        return float(cleaned) if cleaned else default
    except ValueError:
        return default


def parse_length(val, default=0.0):
    """Parse an SVG length string with optional unit (mm, cm, pt, pc, in, px) to pixels."""
    if val is None:
        return default
    s = str(val).strip()
    for unit, factor in _UNIT_TO_PX.items():
        if s.endswith(unit):
            try:
                return float(s[:-len(unit)].strip()) * factor
            except ValueError:
                return default
    return parse_float(val, default)


def parse_style_attr(s):
    result = {}
    for item in (s or '').split(';'):
        if ':' in item:
            k, v = item.split(':', 1)
            result[k.strip().lower()] = v.strip()
    return result


def get_tooltip(elem):
    """Return the text content of the first <title> child, or empty string."""
    for child in elem:
        if strip_ns(child.tag) == 'title':
            return (child.text or '').strip()
    return ''


def tooltip_style(elem):
    """Return 'tooltip=TEXT;' style fragment if the element has a <title> child."""
    tip = get_tooltip(elem)
    if tip:
        safe = (tip
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;'))
        return f'tooltip={safe};'
    return ''


def link_style(conv):
    """Return 'link=URL;' style fragment if the converter has an active link URL."""
    url = getattr(conv, '_link_url', '')
    return f'link={url};' if url else ''
