"""CSS parsing and cascade helpers used during SVG conversion."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from xml.etree.ElementTree import Element

from .utils import parse_float, parse_length, parse_style_attr, strip_ns

Specificity = tuple[int, int, int]
AncestorInfo = tuple[str, set[str]]


@dataclass
class CssRule:
    """A parsed stylesheet rule with selector metadata for cascade resolution."""

    selector: str
    props: dict[str, str]
    specificity: Specificity
    order: int


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
    elem_classes: set[str],
    elem: Element,
) -> bool:
    """Match a simple selector without combinators against an element."""
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


def _match_ancestor_sel(selector: str, ancestor_tag: str, ancestor_classes: set[str]) -> bool:
    """Match a simplified ancestor selector used in descendant and child combinators."""
    ok, remainder = _match_type_selector(selector, ancestor_tag)
    if not ok:
        return False
    while remainder:
        if remainder[0] != ".":
            return False
        match = re.match(r"^\.([\w-]+)", remainder)
        if not match or match.group(1) not in ancestor_classes:
            return False
        remainder = remainder[match.end() :]
    return True


def _selector_matches(
    selector: str,
    tag: str,
    elem_id: str,
    elem_classes: set[str],
    elem: Element,
    ancestors: Sequence[AncestorInfo],
) -> bool:
    """Return whether a selector matches an element within its ancestor context."""
    selector = selector.strip()
    if not selector:
        return False

    has_child_combinator = ">" in selector
    has_descendant_combinator = " " in selector and not has_child_combinator

    if not has_child_combinator and not has_descendant_combinator:
        return _match_simple_sel(selector, tag, elem_id, elem_classes, elem)

    parts = re.split(r"\s*>\s*", selector, maxsplit=1) if has_child_combinator else selector.split(None, 1)
    if len(parts) != 2:
        return False

    ancestor_selector, descendant_selector = parts[0].strip(), parts[1].strip()
    if not _match_simple_sel(descendant_selector, tag, elem_id, elem_classes, elem):
        return False

    if has_child_combinator:
        if not ancestors:
            return False
        ancestor_tag, ancestor_classes = ancestors[-1]
        return _match_ancestor_sel(ancestor_selector, ancestor_tag, ancestor_classes)

    for ancestor_tag, ancestor_classes in ancestors:
        if _match_ancestor_sel(ancestor_selector, ancestor_tag, ancestor_classes):
            return True
    return False


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


def apply_css(
    elem: Element,
    css_rules: Sequence[CssRule],
    tag: str,
    inherited_styles: dict[str, str] | None = None,
    ancestors: Sequence[AncestorInfo] | None = None,
    *,
    custom_props: dict[str, str] | None = None,
) -> dict[str, str]:
    """Compute the effective style dictionary for an element.

    Cascade order:
    inherited styles -> matching stylesheet rules by specificity/source order -> inline style

    Pass *custom_props* (from `extract_custom_props`) to avoid recomputing it on every call.
    """
    inherited = inherited_styles or {}
    computed = dict(inherited)
    winners: dict[str, tuple[Specificity, int]] = {}
    if custom_props is None:
        custom_props = extract_custom_props(css_rules)

    elem_id = elem.get("id", "")
    elem_classes = set((elem.get("class") or "").split())
    ancestor_list = list(ancestors or [])

    for rule in css_rules:
        if not _selector_matches(rule.selector, tag, elem_id, elem_classes, elem, ancestor_list):
            continue
        for key, value in rule.props.items():
            resolved = _resolve_vars(str(value), custom_props)
            if resolved.strip().lower() == "inherit":
                continue
            current = winners.get(key, ((-1, -1, -1), -1))
            candidate = (rule.specificity, rule.order)
            if candidate >= current:
                computed[key] = resolved
                winners[key] = candidate

    inline_order = len(css_rules)
    inline_specificity: Specificity = (10**6, 0, 0)
    for key, value in parse_style_attr(elem.get("style", "")).items():
        resolved = _resolve_vars(str(value), custom_props)
        if resolved.strip().lower() == "inherit":
            continue
        computed[key] = resolved
        winners[key] = (inline_specificity, inline_order)

    if "font-size" in computed:
        parent_px = _resolve_font_size(inherited.get("font-size", "12"), 12.0)
        computed["font-size"] = str(_resolve_font_size(computed["font-size"], parent_px))

    return computed
