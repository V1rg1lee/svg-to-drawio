import re

from .utils import parse_style_attr, strip_ns


def parse_css_rules(style_text):
    """Parse a CSS text block into {selector: {prop: value}} dict."""
    rules = {}
    style_text = re.sub(r'/\*.*?\*/', '', style_text, flags=re.DOTALL)
    for match in re.finditer(r'([^{]+)\{([^}]*)\}', style_text):
        props = parse_style_attr(match.group(2))
        for sel in match.group(1).split(','):
            sel = sel.strip()
            if sel:
                rules.setdefault(sel, {}).update(props)
    return rules


def collect_css(svg_root):
    """Collect and merge all CSS rules from <style> elements in the SVG."""
    combined = {}
    for elem in svg_root.iter():
        if strip_ns(elem.tag) == 'style':
            text = (elem.text or '') + ''.join(c.text or '' for c in elem)
            combined.update(parse_css_rules(text))
    return combined


def apply_css(elem, css_rules, tag, inherited_styles=None):
    """
    Compute the effective style dict for an element by merging (low→high priority):
      inherited → element-type CSS → class CSS → inline style=""
    Direct SVG presentation attributes (fill="red") are NOT included here;
    they are resolved later in get_visual as the lowest-priority fallback.
    """
    computed = dict(inherited_styles or {})
    computed.update(css_rules.get(tag, {}))
    for cls in (elem.get('class') or '').split():
        computed.update(css_rules.get(f'.{cls}', {}))
        computed.update(css_rules.get(f'{tag}.{cls}', {}))
    computed.update(parse_style_attr(elem.get('style', '')))
    return computed
