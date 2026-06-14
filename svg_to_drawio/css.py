import re

from .utils import parse_style_attr, strip_ns


def parse_css_rules(style_text):
    """Parse a CSS text block into [(selector, {prop: value})] list."""
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


def apply_css(elem, css_rules, tag, inherited_styles=None, ancestors=None):
    """
    Compute the effective style dict for an element by merging (low->high priority):
      inherited -> element-type CSS -> descendant CSS -> ID CSS -> class CSS -> inline style=""
    Direct SVG presentation attributes (fill="red") are NOT included here;
    they are resolved later in get_visual as the lowest-priority fallback.

    ancestors: list of tag strings from outermost to direct parent (optional).
    """
    computed = dict(inherited_styles or {})
    def _merge(props):
        for k, v in props.items():
            if v.strip().lower() != 'inherit':
                computed[k] = v

    # Element-type selector (e.g. "rect")
    _merge(css_rules.get(tag, {}))

    # Descendant selectors: "A B" or "A.cls B" where A is an ancestor tag
    # ancestors is a list of (tag, classes_set) tuples
    anc_list = ancestors or []
    for sel, props in css_rules.items():
        parts = sel.split()
        if len(parts) == 2:
            ancestor_sel, descendant_sel = parts
            # descendant must match current tag (possibly with class, e.g. "rect" or "rect.foo")
            if '.' in descendant_sel:
                desc_tag, desc_cls = descendant_sel.split('.', 1)
                desc_match = (desc_tag == tag or desc_tag == '') and desc_cls in (elem.get('class') or '').split()
            else:
                desc_match = descendant_sel == tag
            if not desc_match:
                continue
            # ancestor selector may be "tag" or "tag.cls"
            for anc_entry in anc_list:
                # Support both old-style (plain tag string) and new-style (tag, classes_set) tuples
                if isinstance(anc_entry, tuple):
                    anc_tag, anc_classes = anc_entry
                else:
                    anc_tag, anc_classes = anc_entry, set()
                if '.' in ancestor_sel:
                    anc_tag_part, anc_cls = ancestor_sel.split('.', 1)
                    if anc_tag_part == anc_tag and anc_cls in anc_classes:
                        _merge(props)
                        break
                else:
                    if ancestor_sel == anc_tag:
                        _merge(props)
                        break

    # ID selector (higher specificity than class)
    elem_id = elem.get('id', '')
    if elem_id:
        _merge(css_rules.get(f'#{elem_id}', {}))

    # Class selectors
    for cls in (elem.get('class') or '').split():
        _merge(css_rules.get(f'.{cls}', {}))
        _merge(css_rules.get(f'{tag}.{cls}', {}))

    # Inline style (highest priority); skip 'inherit' so the parent value stays
    for k, v in parse_style_attr(elem.get('style', '')).items():
        if v.strip().lower() != 'inherit':
            computed[k] = v
    return computed
