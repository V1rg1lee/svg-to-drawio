"""Public capability helpers backed by the shared registry."""

from __future__ import annotations

from .capability_registry import (
    CapabilityDescriptor,
    all_capability_descriptors,
    capability_descriptor,
    capability_keys,
)
from .rendering_options import RenderingOptions


def all_capabilities() -> list[CapabilityDescriptor]:
    """Return the registered public capability descriptors in label order."""
    return all_capability_descriptors()


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
        lines.append(
            "Unsupported filters are dropped when needed, and some shadow, glow, "
            "or offset cases may be simplified natively."
        )
    elif options.filter_policy == "force-fallback":
        lines.append("Any filtered content prefers embedded SVG fallback to preserve the look.")
    else:
        lines.append(
            "Supported shadows stay native, some glow or offset cases may be approximated, "
            "and harder filters can fall back."
        )

    if options.text_metrics_policy == "heuristic":
        lines.append("Text sizing uses the deterministic built-in heuristic on every machine.")
    elif options.text_metrics_policy == "system":
        lines.append("Text sizing prefers real Qt, Pillow, or Tk font measurements for the closest visual match.")
    else:
        lines.append("Text sizing uses Qt, Pillow, or Tk font metrics when available, else the built-in heuristic.")

    lines.append(
        "Simple clips, masks, and some dot/stripe/grid patterns can stay editable; more complex ones may fall back."
    )
    return lines


__all__ = [
    "CapabilityDescriptor",
    "all_capabilities",
    "capability_descriptor",
    "capability_keys",
    "rendering_preflight_lines",
]
