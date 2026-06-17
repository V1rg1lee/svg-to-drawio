"""Engine-level rendering policies that trade fidelity against editability."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, cast

GradientPolicy = Literal["auto", "prefer-native", "prefer-fallback"]
FilterPolicy = Literal["auto", "prefer-native", "force-fallback"]
TextMetricsPolicy = Literal["auto", "system", "heuristic"]
RenderingPresetKey = Literal["balanced", "editability", "fidelity"]

_GRADIENT_POLICIES: frozenset[str] = frozenset({"auto", "prefer-native", "prefer-fallback"})
_FILTER_POLICIES: frozenset[str] = frozenset({"auto", "prefer-native", "force-fallback"})
_TEXT_METRICS_POLICIES: frozenset[str] = frozenset({"auto", "system", "heuristic"})
_RENDERING_PRESETS: frozenset[str] = frozenset({"balanced", "editability", "fidelity"})


def _validate_choice(name: str, value: str, allowed: frozenset[str]) -> None:
    """Raise a helpful error when a rendering policy contains an invalid value."""
    if value not in allowed:
        allowed_text = ", ".join(sorted(allowed))
        raise ValueError(f"Invalid {name}: {value!r}. Expected one of: {allowed_text}.")


def normalize_filter_ref(filter_ref: str | None) -> str | None:
    """Return a normalized filter reference, collapsing empty and `none` values."""
    if not filter_ref:
        return None
    text = filter_ref.strip()
    if not text or text.lower() == "none":
        return None
    return text


def as_gradient_policy(value: str) -> GradientPolicy:
    """Validate and narrow a raw string into a typed gradient policy."""
    _validate_choice("gradient_policy", value, _GRADIENT_POLICIES)
    return cast(GradientPolicy, value)


def as_filter_policy(value: str) -> FilterPolicy:
    """Validate and narrow a raw string into a typed filter policy."""
    _validate_choice("filter_policy", value, _FILTER_POLICIES)
    return cast(FilterPolicy, value)


def as_text_metrics_policy(value: str) -> TextMetricsPolicy:
    """Validate and narrow a raw string into a typed text-metrics policy."""
    _validate_choice("text_metrics_policy", value, _TEXT_METRICS_POLICIES)
    return cast(TextMetricsPolicy, value)


@dataclass(frozen=True)
class RenderingOptions:
    """Fine-grained rendering choices shared by the CLI, API, and desktop app."""

    gradient_policy: GradientPolicy = "auto"
    filter_policy: FilterPolicy = "auto"
    text_metrics_policy: TextMetricsPolicy = "auto"

    def __post_init__(self) -> None:
        _validate_choice("gradient_policy", self.gradient_policy, _GRADIENT_POLICIES)
        _validate_choice("filter_policy", self.filter_policy, _FILTER_POLICIES)
        _validate_choice("text_metrics_policy", self.text_metrics_policy, _TEXT_METRICS_POLICIES)

    def to_dict(self) -> dict[str, str]:
        """Serialize the policy set into a JSON-friendly dictionary."""
        return {
            "gradient_policy": self.gradient_policy,
            "filter_policy": self.filter_policy,
            "text_metrics_policy": self.text_metrics_policy,
        }

    def should_force_filter_fallback(self, filter_ref: str | None) -> bool:
        """Return whether a filter should always be rendered through embedded SVG."""
        return self.filter_policy == "force-fallback" and normalize_filter_ref(filter_ref) is not None

    def should_prefer_native_filter(self) -> bool:
        """Return whether unsupported filters should be ignored to keep native output."""
        return self.filter_policy == "prefer-native"

    def should_force_gradient_fallback(self) -> bool:
        """Return whether multi-stop gradients should always prefer embedded SVG fallback."""
        return self.gradient_policy == "prefer-fallback"

    def should_prefer_native_gradient(self) -> bool:
        """Return whether multi-stop gradients should stay native whenever possible."""
        return self.gradient_policy == "prefer-native"


def rendering_preset_options(preset: str) -> RenderingOptions:
    """Return the rendering policy bundle associated with one user-facing preset."""
    _validate_choice("rendering_preset", preset, _RENDERING_PRESETS)
    if preset == "editability":
        return RenderingOptions(
            gradient_policy="prefer-native",
            filter_policy="prefer-native",
            text_metrics_policy="heuristic",
        )
    if preset == "fidelity":
        return RenderingOptions(
            gradient_policy="prefer-fallback",
            filter_policy="force-fallback",
            text_metrics_policy="system",
        )
    return RenderingOptions()


def rendering_preset_label(preset: str) -> str:
    """Return the public label for one rendering preset."""
    _validate_choice("rendering_preset", preset, _RENDERING_PRESETS)
    return {
        "balanced": "Balanced",
        "editability": "Best editability",
        "fidelity": "Best visual fidelity",
    }[preset]


def detect_rendering_preset(options: RenderingOptions) -> RenderingPresetKey | None:
    """Return the preset key matching the given options, or ``None`` for custom mixes."""
    for preset in ("balanced", "editability", "fidelity"):
        if rendering_preset_options(preset) == options:
            return cast(RenderingPresetKey, preset)
    return None
