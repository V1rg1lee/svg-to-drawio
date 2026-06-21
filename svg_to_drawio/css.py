"""CSS parsing and cascade helpers used during SVG conversion."""

from __future__ import annotations

import re
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from xml.etree.ElementTree import Element

from .utils import parse_float, parse_length, parse_style_attr, strip_ns

Specificity = tuple[int, int, int]


@dataclass(frozen=True)
class AncestorInfo:
    """Selector-relevant metadata for one ancestor element."""

    tag: str
    elem_id: str
    classes: frozenset[str]
    element: Element


def ancestor_info(elem: Element) -> AncestorInfo:
    """Build selector metadata for an element before traversing its children."""
    return AncestorInfo(
        tag=strip_ns(elem.tag),
        elem_id=elem.get("id", ""),
        classes=frozenset((elem.get("class") or "").split()),
        element=elem,
    )


_PRESENTATION_ATTR_SPECIFICITY: Specificity = (0, 0, 0)
_PRESENTATION_ATTR_ORDER = -1
_INHERITED_PRESENTATION_ATTRS: tuple[str, ...] = (
    "baseline-shift",
    "color",
    "dominant-baseline",
    "fill",
    "fill-opacity",
    "fill-rule",
    "font-family",
    "font-size",
    "font-style",
    "font-weight",
    "letter-spacing",
    "stroke",
    "stroke-dasharray",
    "stroke-linecap",
    "stroke-linejoin",
    "stroke-miterlimit",
    "stroke-opacity",
    "stroke-width",
    "text-anchor",
    "text-decoration",
    "visibility",
)


@dataclass
class CssRule:
    """A parsed stylesheet rule with selector metadata for cascade resolution."""

    selector: str
    props: dict[str, str]
    specificity: Specificity
    order: int


def _apply_presentation_attributes(
    elem: Element,
    computed: dict[str, str],
    winners: dict[str, tuple[Specificity, int]],
    custom_props: dict[str, str],
) -> None:
    """Apply inheritable SVG presentation attributes for descendant style propagation.

    SVG presentation attributes such as `fill="#000"` are not part of the stylesheet
    rule list, but they must still override inherited values on the current element
    and then become inheritable for descendants. They behave like author styles with
    zero specificity, so normal stylesheet rules and inline styles can still override
    them later in the cascade.
    """
    for key in _INHERITED_PRESENTATION_ATTRS:
        value = elem.get(key)
        if value is None:
            continue
        resolved = _resolve_vars(str(value), custom_props)
        if resolved.strip().lower() == "inherit":
            continue
        computed[key] = resolved
        winners[key] = (_PRESENTATION_ATTR_SPECIFICITY, _PRESENTATION_ATTR_ORDER)


def extract_custom_props(css_rules: Sequence[CssRule]) -> dict[str, str]:
    """Collect CSS custom properties declared on global selectors.

    Pre-compute this once per document and pass it to every `apply_css` call
    to avoid O(R × N) rescanning of the rule list for each element.
    """
    custom: dict[str, str] = {}
    for rule in css_rules:
        if rule.selector.strip() in (":root", "html", "*"):
            custom.update({key: value for key, value in rule.props.items() if key.startswith("--")})
    return custom


def _resolve_vars(value: str, custom_props: dict[str, str]) -> str:
    """Resolve `var(--name, fallback)` expressions using the collected custom properties."""
    if not custom_props or "var(" not in value:
        return value

    def replace_var(match: re.Match[str]) -> str:
        name = match.group(1).strip()
        fallback = (match.group(2) or "").strip()
        return custom_props.get(name, fallback)

    return re.sub(r"var\(\s*(--[\w-]+)\s*(?:,\s*([^)]*))?\s*\)", replace_var, value)


def _resolve_font_size(value: str, parent_px: float = 12.0) -> float:
    """Resolve a CSS font size into pixels, including relative units."""
    text = str(value).strip()
    if text.endswith("rem"):
        return parse_float(text[:-3]) * 16.0
    if text.endswith("em"):
        return parse_float(text[:-2]) * parent_px
    if text.endswith("%"):
        return parse_float(text[:-1]) / 100.0 * parent_px
    return parse_length(text, parent_px)


def _match_type_selector(selector: str, tag: str) -> tuple[bool, str]:
    """Match the type component (tag name, universal, :root) of a simple selector.

    Returns ``(matched, remaining)`` where *remaining* is the unparsed suffix.
    """
    remainder = selector.strip()
    if not remainder or remainder == "*":
        return True, ""
    if remainder == ":root":
        return tag == "svg", ""
    tag_match = re.match(r"^([a-zA-Z][a-zA-Z0-9-]*)", remainder)
    if tag_match:
        if tag_match.group(1) != tag:
            return False, remainder
        remainder = remainder[tag_match.end() :]
    return True, remainder


def _match_simple_sel(
    selector: str,
    tag: str,
    elem_id: str,
    elem_classes: Collection[str],
    elem: Element,
) -> bool:
    """Match a simple selector without combinators against an element.

    The only supported pseudo-class is a standalone `:root` (handled entirely inside
    `_match_type_selector`). Any other `:pseudo-class` reaching the loop below hits the
    `else: return False` branch, so the whole rule never matches anything - it is safely
    ignored rather than mismatched, even though `_selector_specificity` still counts the
    colon. A rule that never matches cannot affect the cascade regardless of that count.
    """
    ok, remainder = _match_type_selector(selector, tag)
    if not ok:
        return False

    while remainder:
        if remainder[0] == ".":
            match = re.match(r"^\.([\w-]+)", remainder)
            if not match or match.group(1) not in elem_classes:
                return False
            remainder = remainder[match.end() :]
        elif remainder[0] == "#":
            match = re.match(r"^#([\w-]+)", remainder)
            if not match or match.group(1) != elem_id:
                return False
            remainder = remainder[match.end() :]
        elif remainder[0] == "[":
            end = remainder.find("]")
            if end < 0:
                return False
            condition = remainder[: end + 1]
            match = re.match(r'^\[([^\]~|^$*=]+?)(?:([~|^$*]?=)"?([^"\]]*)"?)?\]$', condition)
            if not match:
                return False
            attr_name, operator, required = match.group(1).strip(), match.group(2) or "", match.group(3) or ""
            elem_value = elem.get(attr_name)
            if elem_value is None:
                return False
            if operator == "=" and elem_value != required:
                return False
            if operator == "~=" and required not in elem_value.split():
                return False
            if operator == "^=" and not elem_value.startswith(required):
                return False
            if operator == "$=" and not elem_value.endswith(required):
                return False
            if operator == "*=" and required not in elem_value:
                return False
            remainder = remainder[end + 1 :]
        else:
            return False
    return True


def _split_selector_chain(selector: str) -> tuple[list[str], list[str]]:
    """Split one selector into simple selectors and ` ` / `>` combinators.

    Whitespace and `>` inside attribute values are ignored so selectors such as
    `[data-label="A > B"] .node` remain parseable.
    """
    parts: list[str] = []
    combinators: list[str] = []
    buffer: list[str] = []
    bracket_depth = 0
    quote: str | None = None
    pending_descendant = False
    index = 0

    def flush_part() -> None:
        nonlocal buffer
        part = "".join(buffer).strip()
        if part:
            parts.append(part)
        buffer = []

    while index < len(selector):
        char = selector[index]
        if quote is not None:
            buffer.append(char)
            if char == quote:
                quote = None
            index += 1
            continue
        if char in {'"', "'"} and bracket_depth:
            quote = char
            buffer.append(char)
            index += 1
            continue
        if char == "[":
            bracket_depth += 1
            buffer.append(char)
            index += 1
            continue
        if char == "]" and bracket_depth:
            bracket_depth -= 1
            buffer.append(char)
            index += 1
            continue
        if bracket_depth:
            buffer.append(char)
            index += 1
            continue
        if char.isspace():
            if buffer:
                flush_part()
                pending_descendant = True
            index += 1
            continue
        if char == ">":
            if buffer:
                flush_part()
            pending_descendant = False
            if parts and len(combinators) < len(parts):
                combinators.append(">")
            index += 1
            while index < len(selector) and selector[index].isspace():
                index += 1
            continue
        if pending_descendant:
            if parts and len(combinators) < len(parts):
                combinators.append(" ")
            pending_descendant = False
        buffer.append(char)
        index += 1

    flush_part()
    if len(parts) != len(combinators) + 1:
        return [], []
    return parts, combinators


def _info_matches(selector: str, info: AncestorInfo) -> bool:
    """Return whether one simple selector matches stored element metadata."""
    return _match_simple_sel(selector, info.tag, info.elem_id, info.classes, info.element)


def _selector_matches(
    selector: str,
    tag: str,
    elem_id: str,
    elem_classes: set[str],
    elem: Element,
    ancestors: Sequence[AncestorInfo],
) -> bool:
    """Match an arbitrary descendant/child selector chain from right to left."""
    selector = selector.strip()
    if not selector:
        return False

    parts, combinators = _split_selector_chain(selector)
    if not parts:
        return False

    current = AncestorInfo(tag, elem_id, frozenset(elem_classes), elem)
    nodes = [*ancestors, current]
    node_index = len(nodes) - 1
    if not _info_matches(parts[-1], nodes[node_index]):
        return False

    for part_index in range(len(parts) - 2, -1, -1):
        combinator = combinators[part_index]
        if combinator == ">":
            node_index -= 1
            if node_index < 0 or not _info_matches(parts[part_index], nodes[node_index]):
                return False
            continue

        matched_index: int | None = None
        for candidate_index in range(node_index - 1, -1, -1):
            if _info_matches(parts[part_index], nodes[candidate_index]):
                matched_index = candidate_index
                break
        if matched_index is None:
            return False
        node_index = matched_index
    return True


def _selector_specificity(selector: str) -> Specificity:
    """Compute a simplified CSS specificity tuple for supported selector syntax."""
    id_count = 0
    class_count = 0
    tag_count = 0
    for part in re.split(r"\s*>\s*|\s+", selector.strip()):
        if not part:
            continue
        id_count += part.count("#")
        class_count += part.count(".")
        class_count += part.count("[")
        class_count += part.count(":")
        tag_match = re.match(r"^([a-zA-Z][a-zA-Z0-9-]*)", part)
        if tag_match and tag_match.group(1) != "*":
            tag_count += 1
    return id_count, class_count, tag_count


def parse_css_rules(style_text: str, start_order: int = 0) -> tuple[list[CssRule], int]:
    """Parse a stylesheet text block into ordered `CssRule` instances."""
    rules: list[CssRule] = []
    order = start_order
    cleaned_text = re.sub(r"/\*.*?\*/", "", style_text, flags=re.DOTALL)
    for match in re.finditer(r"([^{]+)\{([^}]*)\}", cleaned_text):
        props = parse_style_attr(match.group(2))
        for raw_selector in match.group(1).split(","):
            selector = raw_selector.strip()
            if not selector:
                continue
            rules.append(
                CssRule(
                    selector=selector,
                    props=dict(props),
                    specificity=_selector_specificity(selector),
                    order=order,
                )
            )
            order += 1
    return rules, order


def collect_css(svg_root: Element) -> list[CssRule]:
    """Collect rules from every `<style>` element while preserving source order."""
    rules: list[CssRule] = []
    order = 0
    for elem in svg_root.iter():
        if strip_ns(elem.tag) != "style":
            continue
        text = (elem.text or "") + "".join(child.text or "" for child in elem)
        parsed_rules, order = parse_css_rules(text, start_order=order)
        rules.extend(parsed_rules)
    return rules


CssRuleIndex = dict[tuple[str, str], list[CssRule]]
_UNIVERSAL_INDEX_KEY: tuple[str, str] = ("*", "*")


def _subject_selector(selector: str) -> str:
    """Return the rightmost simple selector: the part that must match the current element.

    For combinator selectors (`a > b`, `a b`) only this trailing part is matched against
    the element itself; the rest is matched against ancestors. It is therefore the only
    part that can drive a cheap necessary-condition index for the element being styled.
    """
    selector = selector.strip()
    if ">" in selector:
        return selector.rsplit(">", 1)[-1].strip()
    if " " in selector:
        return selector.rsplit(None, 1)[-1].strip()
    return selector


def _subject_index_key(subject: str) -> tuple[str, str]:
    """Return a cheap necessary-condition key for one rule's subject selector.

    Any element that could possibly match *subject* must satisfy this single condition
    (have this id, have this class, or have this tag name), so grouping rules by it lets
    `apply_css` skip rules that cannot possibly match instead of testing every rule's full
    selector against every element. Falls back to a universal bucket for selectors with no
    id/class/tag component (`*`, bare attribute selectors, unsupported pseudo-classes).
    """
    id_match = re.search(r"#([\w-]+)", subject)
    if id_match:
        return ("id", id_match.group(1))
    class_match = re.search(r"\.([\w-]+)", subject)
    if class_match:
        return ("class", class_match.group(1))
    if subject == ":root":
        return ("tag", "svg")
    tag_match = re.match(r"^([a-zA-Z][a-zA-Z0-9-]*)", subject)
    if tag_match:
        return ("tag", tag_match.group(1))
    return _UNIVERSAL_INDEX_KEY


def index_css_rules(css_rules: Sequence[CssRule]) -> CssRuleIndex:
    """Bucket *css_rules* by `_subject_index_key` for fast per-element candidate lookup.

    Build this once per document (alongside `collect_css`) and pass it to every
    `apply_css` call as `rule_index` to turn the per-element rule scan from O(rules) into
    roughly O(candidate rules), which matters on large SVGs styled by a sizeable
    stylesheet (e.g. Figma/Illustrator exports with hundreds of class rules).
    """
    index: CssRuleIndex = {}
    for rule in css_rules:
        key = _subject_index_key(_subject_selector(rule.selector))
        index.setdefault(key, []).append(rule)
    return index


def _candidate_rules(
    css_rules: Sequence[CssRule],
    rule_index: CssRuleIndex | None,
    tag: str,
    elem_id: str,
    elem_classes: set[str],
) -> Sequence[CssRule]:
    """Return the reduced set of rules that could possibly match, given *rule_index*.

    Each rule lives in exactly one bucket (see `_subject_index_key`), so concatenating
    the relevant buckets cannot yield duplicates. Falls back to the full rule list when
    no index was provided, preserving the older, unindexed behavior exactly.
    """
    if rule_index is None:
        return css_rules

    candidates: list[CssRule] = list(rule_index.get(_UNIVERSAL_INDEX_KEY, ()))
    candidates.extend(rule_index.get(("tag", tag), ()))
    for elem_class in elem_classes:
        candidates.extend(rule_index.get(("class", elem_class), ()))
    if elem_id:
        candidates.extend(rule_index.get(("id", elem_id), ()))
    return candidates


def apply_css(
    elem: Element,
    css_rules: Sequence[CssRule],
    tag: str,
    inherited_styles: dict[str, str] | None = None,
    ancestors: Sequence[AncestorInfo] | None = None,
    *,
    custom_props: dict[str, str] | None = None,
    _match_cache: dict | None = None,
    rule_index: CssRuleIndex | None = None,
) -> dict[str, str]:
    """Compute the effective style dictionary for an element.

    Cascade order:
    inherited styles -> matching stylesheet rules by specificity/source order -> inline style

    Pass *custom_props* (from `extract_custom_props`) to avoid recomputing it on every call.
    Pass *_match_cache* (a plain dict) to cache selector-match results across elements with the
    same tag/id/class combination - only effective for simple selectors without combinators or
    attribute tests.
    Pass *rule_index* (from `index_css_rules`, built once per document) to scan only the rules
    that could possibly match this element instead of the full rule list.
    """
    inherited = inherited_styles or {}
    computed = dict(inherited)
    winners: dict[str, tuple[Specificity, int]] = {}
    if custom_props is None:
        custom_props = extract_custom_props(css_rules)

    elem_id = elem.get("id", "")
    elem_classes = set((elem.get("class") or "").split())
    ancestor_list = list(ancestors or [])

    _apply_presentation_attributes(elem, computed, winners, custom_props)

    # Single pass over rules: collect custom properties from matching rules first so that
    # var() expressions in later properties can reference element-scoped variables
    # (e.g. --color defined on .my-class rather than only on :root).
    element_custom_props = dict(custom_props or {})
    matched_rules: list[CssRule] = []
    for rule in _candidate_rules(css_rules, rule_index, tag, elem_id, elem_classes):
        sel = rule.selector
        if _match_cache is not None and ">" not in sel and "[" not in sel and " " not in sel.strip():
            cache_key = (sel, tag, elem_id, frozenset(elem_classes))
            if cache_key not in _match_cache:
                _match_cache[cache_key] = _selector_matches(sel, tag, elem_id, elem_classes, elem, ancestor_list)
            if not _match_cache[cache_key]:
                continue
        elif not _selector_matches(sel, tag, elem_id, elem_classes, elem, ancestor_list):
            continue
        matched_rules.append(rule)
        for key, value in rule.props.items():
            if key.startswith("--"):
                element_custom_props[key] = value

    # Also collect custom properties from the inline style so self-referencing vars work.
    inline_props = parse_style_attr(elem.get("style", ""))
    for key, value in inline_props.items():
        if key.startswith("--"):
            element_custom_props[key] = value

    # Apply matched rules using the element-scoped variable map.
    for rule in matched_rules:
        for key, value in rule.props.items():
            if key.startswith("--"):
                continue
            resolved = _resolve_vars(str(value), element_custom_props)
            if resolved.strip().lower() == "inherit":
                continue
            current = winners.get(key, ((-1, -1, -1), -1))
            candidate = (rule.specificity, rule.order)
            if candidate >= current:
                computed[key] = resolved
                winners[key] = candidate

    inline_order = len(css_rules)
    inline_specificity: Specificity = (10**6, 0, 0)
    for key, value in inline_props.items():
        if key.startswith("--"):
            continue
        resolved = _resolve_vars(str(value), element_custom_props)
        if resolved.strip().lower() == "inherit":
            continue
        computed[key] = resolved
        winners[key] = (inline_specificity, inline_order)

    if "font-size" in computed:
        parent_px = _resolve_font_size(inherited.get("font-size", "12"), 12.0)
        computed["font-size"] = str(_resolve_font_size(computed["font-size"], parent_px))

    return computed
