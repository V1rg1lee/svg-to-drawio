"""Central registry describing engine capabilities and user-facing tradeoffs."""

from __future__ import annotations

from dataclasses import dataclass

from .rendering_options import RenderingOptions


@dataclass(frozen=True)
class CapabilityDescriptor:
    """User-facing description of one SVG feature family."""

    key: str
    label: str
    description: str
    default_behavior: str
    editability_note: str
    fidelity_note: str


_CAPABILITIES: dict[str, CapabilityDescriptor] = {
    "shapes": CapabilityDescriptor(
        key="shapes",
        label="Shapes and paths",
        description="Basic vectors such as rectangles, circles, polygons, and general paths.",
        default_behavior="Converted to native editable draw.io shapes whenever possible.",
        editability_note="Simple geometry stays editable; some transformed shapes may use stencil approximation.",
        fidelity_note="Very complex transformed geometry may still be baked into a stencil.",
    ),
    "text": CapabilityDescriptor(
        key="text",
        label="Text labels",
        description="SVG text, tspans, anchors, and text measurements.",
        default_behavior="Converted to editable draw.io text with automatic text measurement.",
        editability_note="Text stays editable even when some layout details must be approximated.",
        fidelity_note="System font metrics improve sizing, while heuristic mode favors deterministic output.",
    ),
    "gradients": CapabilityDescriptor(
        key="gradients",
        label="Gradients",
        description="Linear, radial, and multi-stop gradients.",
        default_behavior=(
            "Auto mode keeps native gradients when the engine can approximate them well, "
            "otherwise it falls back to embedded SVG."
        ),
        editability_note="Prefer-native keeps more output editable, but complex gradients may be simplified.",
        fidelity_note=(
            "Prefer-fallback preserves the original look through embedded SVG when "
            "native draw.io gradients are not enough."
        ),
    ),
    "filters": CapabilityDescriptor(
        key="filters",
        label="Filters and shadows",
        description="SVG filters such as drop shadows, blur, and similar effects.",
        default_behavior=(
            "Native draw.io shadow support is used when available; unsupported filters fall back to embedded SVG."
        ),
        editability_note=(
            "Prefer-native drops unsupported filters instead of falling back so nearby shapes stay editable."
        ),
        fidelity_note="Force-fallback preserves filtered content visually, but those fragments are less editable.",
    ),
    "clipping": CapabilityDescriptor(
        key="clipping",
        label="Clip paths and masks",
        description="SVG clipping and masking effects.",
        default_behavior="Simple cases may stay editable; more advanced clips and masks fall back to embedded SVG.",
        editability_note="Some simple clips and masks can be rewritten into editable replacement shapes.",
        fidelity_note="Complex clip and mask effects are preserved visually through embedded SVG fallback.",
    ),
    "patterns": CapabilityDescriptor(
        key="patterns",
        label="Pattern fills",
        description="Repeated fills defined with `<pattern>`.",
        default_behavior="Preserved with embedded SVG fallback when draw.io cannot express the fill natively.",
        editability_note="Pattern-heavy regions are usually less editable than flat fills or native gradients.",
        fidelity_note="SVG fallback keeps the visible pattern intact.",
    ),
    "markers": CapabilityDescriptor(
        key="markers",
        label="Arrowheads and markers",
        description="Marker-start, marker-mid, and marker-end decorations.",
        default_behavior="Mapped to the closest editable draw.io arrows when possible.",
        editability_note="Simple custom markers can be emitted as small editable endpoint shapes.",
        fidelity_note="Very custom marker artwork may still be approximated rather than matched exactly.",
    ),
    "images": CapabilityDescriptor(
        key="images",
        label="Images",
        description="Embedded or local raster/SVG image assets.",
        default_behavior="Embedded as draw.io image cells.",
        editability_note="Images remain movable and resizable, but not vector-editable.",
        fidelity_note="Some skew-heavy transforms are approximated because draw.io images do not support true shear.",
    ),
    "references": CapabilityDescriptor(
        key="references",
        label="Reused SVG content",
        description="`<use>`, `<symbol>`, and nested `<svg>` fragments.",
        default_behavior="Expanded into editable draw.io content.",
        editability_note="Expanded content stays editable instead of remaining an opaque reference.",
        fidelity_note="Structure may be flattened compared to the original SVG reuse graph.",
    ),
}


def capability_keys() -> tuple[str, ...]:
    """Return the stable set of public capability keys."""
    return tuple(sorted(_CAPABILITIES))


def capability_descriptor(capability_key: str) -> CapabilityDescriptor | None:
    """Return one registered capability descriptor."""
    return _CAPABILITIES.get(capability_key)


def all_capabilities() -> list[CapabilityDescriptor]:
    """Return the registered capability descriptors in label order."""
    return sorted(_CAPABILITIES.values(), key=lambda descriptor: descriptor.label.lower())


def rendering_preflight_lines(options: RenderingOptions) -> list[str]:
    """Summarize the current rendering policies in plain English for the CLI and desktop app."""
    lines: list[str] = []

    if options.gradient_policy == "prefer-native":
        lines.append("Complex gradients stay editable when possible, even if they must be simplified.")
    elif options.gradient_policy == "prefer-fallback":
        lines.append("Complex gradients prefer embedded SVG fallback for closer visual fidelity.")
    else:
        lines.append("Complex gradients use native approximation when it looks good enough, else SVG fallback.")

    if options.filter_policy == "prefer-native":
        lines.append("Unsupported SVG filters are dropped to keep nearby shapes editable.")
    elif options.filter_policy == "force-fallback":
        lines.append("Any filtered content prefers embedded SVG fallback to preserve the look.")
    else:
        lines.append("Supported shadows stay native; unsupported filters fall back to embedded SVG.")

    if options.text_metrics_policy == "heuristic":
        lines.append("Text sizing uses the deterministic built-in heuristic on every machine.")
    elif options.text_metrics_policy == "system":
        lines.append("Text sizing prefers real system font measurements for the closest visual match.")
    else:
        lines.append("Text sizing uses system font metrics when available, else the built-in heuristic.")

    lines.append("Clip paths, masks, pattern fills, and some advanced filters may still use embedded SVG fallback.")
    return lines
