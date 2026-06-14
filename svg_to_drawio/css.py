import re

from .utils import parse_float, parse_length, parse_style_attr, strip_ns


# CSS custom properties (var())

def _extract_custom_props(css_rules):
    """Collect CSS custom properties (--name) from :root / html / * rules."""
    custom = {}
    for sel, props in css_rules.items():
        if sel.strip() in (':root', 'html', '*'):
            custom.update({k: v for k, v in props.items() if k.startswith('--')})
    return custom


def _resolve_vars(value, custom_props):
    """Replace var(--name, fallback) with resolved values from custom_props."""
    if not custom_props or 'var(' not in str(value):
        return value

    def _sub(match):
        name = match.group(1).strip()
        fallback = (match.group(2) or '').strip()
        return custom_props.get(name, fallback)

    return re.sub(r'var\(\s*(--[\w-]+)\s*(?:,\s*([^)]*))?\s*\)', _sub, str(value))


# Font-size em/rem/% resolution

def _resolve_font_size(val, parent_px=12.0):
    """Resolve a CSS font-size value to pixels, supporting em / rem / %."""
    s = str(val).strip()
    if s.endswith('rem'):
        return parse_float(s[:-3]) * 16.0
    if s.endswith('em'):
        return parse_float(s[:-2]) * parent_px
    if s.endswith('%'):
        return parse_float(s[:-1]) / 100.0 * parent_px
    return parse_length(s, parent_px)


# Selector matching

def _match_simple_sel(sel, tag, elem_id, elem_classes, elem):
    """
    Match a simple CSS selector (no combinators) against an element.
    Handles tag, .cls, #id, [attr], [attr=val] and combinations thereof.
    """
    s = sel.strip()
    if not s or s == '*':
        return True

    tm = re.match(r'^([a-zA-Z][a-zA-Z0-9-]*)', s)
    if tm:
        if tm.group(1) != tag:
            return False
        s = s[tm.end():]

    while s:
        if s[0] == '.':
            m = re.match(r'^\.([\w-]+)', s)
            if not m or m.group(1) not in elem_classes:
                return False
            s = s[m.end():]
        elif s[0] == '#':
            m = re.match(r'^#([\w-]+)', s)
            if not m or m.group(1) != elem_id:
                return False
            s = s[m.end():]
        elif s[0] == '[':
            end = s.find(']')
            if end < 0:
                return False
            cond = s[:end + 1]
            m = re.match(r'^\[([^\]~|^$*=]+?)(?:([~|^$*]?=)"?([^"\]]*)"?)?\]$', cond)
            if not m:
                return False
            attr_name, op, req = m.group(1).strip(), m.group(2) or '', m.group(3) or ''
            ev = elem.get(attr_name)
            if ev is None:
                return False
            if op == '=' and ev != req:
                return False
            if op == '~=' and req not in ev.split():
                return False
            if op == '^=' and not ev.startswith(req):
                return False
            if op == '$=' and not ev.endswith(req):
                return False
            if op == '*=' and req not in ev:
                return False
            s = s[end + 1:]
        else:
            return False
    return True


def _match_ancestor_sel(sel, anc_tag, anc_classes):
    """Match a simple ancestor selector (tag and .cls qualifiers only)."""
    s = sel.strip()
    if not s or s == '*':
        return True

    tm = re.match(r'^([a-zA-Z][a-zA-Z0-9-]*)', s)
    if tm:
        if tm.group(1) != anc_tag:
            return False
        s = s[tm.end():]

    while s:
        if s[0] == '.':
            m = re.match(r'^\.([\w-]+)', s)
            if not m or m.group(1) not in anc_classes:
                return False
            s = s[m.end():]
        else:
            return False
    return True


def _is_simple_sel(sel):
    """True if selector is a pure simple selector handled by basic apply_css steps."""
    return bool(
        re.match(r'^[a-zA-Z][a-zA-Z0-9-]*$', sel) or
        re.match(r'^#[\w-]+$', sel) or
        re.match(r'^\.[\w-]+$', sel) or
        re.match(r'^[a-zA-Z][a-zA-Z0-9-]*\.[\w-]+$', sel)
    )


def _apply_complex_sel(sel, props, tag, elem_id, elem_classes, elem, anc_list, merge_fn):
    """
    Match complex CSS selectors and call merge_fn if matched.
    Handles: multi-class (.a.b), attribute ([attr=val]), child (A > B),
    descendant (A B), and combinations.
    """
    if _is_simple_sel(sel):
        return

    has_child_comb = ' > ' in sel
    has_space = ' ' in sel and not has_child_comb

    # No combinator: simple selector with extra qualifiers (multi-class, attr, etc.)
    if not has_child_comb and not has_space:
        if _match_simple_sel(sel, tag, elem_id, elem_classes, elem):
            merge_fn(props)
        return

    if has_child_comb:
        parts = re.split(r'\s*>\s*', sel, maxsplit=1)
    else:
        parts = sel.split(None, 1)

    if len(parts) != 2:
        return

    ancestor_part, descendant_part = parts[0].strip(), parts[1].strip()
    if not _match_simple_sel(descendant_part, tag, elem_id, elem_classes, elem):
        return

    if has_child_comb:
        if not anc_list:
            return
        last = anc_list[-1]
        anc_tag, anc_classes = last if isinstance(last, tuple) else (last, set())
        if _match_ancestor_sel(ancestor_part, anc_tag, anc_classes):
            merge_fn(props)
    else:
        for entry in anc_list:
            anc_tag, anc_classes = entry if isinstance(entry, tuple) else (entry, set())
            if _match_ancestor_sel(ancestor_part, anc_tag, anc_classes):
                merge_fn(props)
                break


# Rule collection

def parse_css_rules(style_text):
    """Parse a CSS text block into {selector: {prop: value}}."""
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


# Style application

def apply_css(elem, css_rules, tag, inherited_styles=None, ancestors=None):
    """
    Compute the effective style dict for an element (low -> high priority):
      inherited -> element-type -> complex selectors -> ID -> class -> inline style.

    Also resolves:
      - CSS var(--name) custom properties from :root
      - font-size in em / rem / % against the inherited font-size
    """
    inherited = inherited_styles or {}
    computed = dict(inherited)
    custom_props = _extract_custom_props(css_rules)

    def _merge(props):
        for key, value in props.items():
            resolved = _resolve_vars(str(value), custom_props)
            if resolved.strip().lower() != 'inherit':
                computed[key] = resolved

    elem_id = elem.get('id', '')
    elem_classes = set((elem.get('class') or '').split())
    anc_list = ancestors or []

    _merge(css_rules.get(tag, {}))

    for sel, props in css_rules.items():
        _apply_complex_sel(sel, props, tag, elem_id, elem_classes, elem, anc_list, _merge)

    if elem_id:
        _merge(css_rules.get(f'#{elem_id}', {}))

    for cls in elem_classes:
        _merge(css_rules.get(f'.{cls}', {}))
        _merge(css_rules.get(f'{tag}.{cls}', {}))

    for key, value in parse_style_attr(elem.get('style', '')).items():
        resolved = _resolve_vars(str(value), custom_props)
        if resolved.strip().lower() != 'inherit':
            computed[key] = resolved

    if 'font-size' in computed:
        parent_px = _resolve_font_size(inherited.get('font-size', '12'), 12.0)
        computed['font-size'] = str(_resolve_font_size(computed['font-size'], parent_px))

    return computed
