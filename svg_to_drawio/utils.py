import re


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


def parse_style_attr(s):
    result = {}
    for item in (s or '').split(';'):
        if ':' in item:
            k, v = item.split(':', 1)
            result[k.strip().lower()] = v.strip()
    return result
