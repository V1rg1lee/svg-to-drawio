"""Central capability registry shared by compatibility summaries and UI help."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, cast

from . import issue_codes as codes

CompatibilityStatus = Literal["native", "approximate", "fallback", "ignored"]


@dataclass(frozen=True)
class CapabilityDescriptor:
    """User-facing description of one SVG feature family."""

    key: str
    label: str
    description: str
    default_behavior: str
    editability_note: str
    fidelity_note: str


@dataclass(frozen=True)
class FeatureDefinition:
    """Beginner-friendly compatibility text for one SVG feature family."""

    key: str
    label: str
    description: str
    native_message: str
    approximate_message: str
    fallback_message: str
    ignored_message: str

    def message_for(self, status: CompatibilityStatus) -> str:
        """Return the explanation associated with one compatibility status."""
        return {
            "native": self.native_message,
            "approximate": self.approximate_message,
            "fallback": self.fallback_message,
            "ignored": self.ignored_message,
        }[status]


@dataclass(frozen=True)
class CapabilityProfile:
    """One shared registry entry covering help text and compatibility messaging."""

    key: str
    capability: CapabilityDescriptor
    feature: FeatureDefinition


_STATUS_ORDER: dict[CompatibilityStatus, int] = {
    "native": 0,
    "approximate": 1,
    "fallback": 2,
    "ignored": 3,
}

_STATUS_LABELS: dict[CompatibilityStatus, str] = {
    "native": "Editable",
    "approximate": "Editable with simplification",
    "fallback": "Embedded SVG fallback",
    "ignored": "Not fully carried over",
}


def _profile(
    key: str,
    *,
    label: str,
    description: str,
    default_behavior: str,
    editability_note: str,
    fidelity_note: str,
    native_message: str,
    approximate_message: str,
    fallback_message: str,
    ignored_message: str,
) -> CapabilityProfile:
    """Build one registry entry without repeating the key/label boilerplate."""
    return CapabilityProfile(
        key=key,
        capability=CapabilityDescriptor(
            key=key,
            label=label,
            description=description,
            default_behavior=default_behavior,
            editability_note=editability_note,
            fidelity_note=fidelity_note,
        ),
        feature=FeatureDefinition(
            key=key,
            label=label,
            description=description,
            native_message=native_message,
            approximate_message=approximate_message,
            fallback_message=fallback_message,
            ignored_message=ignored_message,
        ),
    )


_PROFILES: dict[str, CapabilityProfile] = {
    "shapes": _profile(
        "shapes",
        label="Shapes and paths",
        description="Basic vectors such as rectangles, circles, polygons, and general paths.",
        default_behavior="Converted to native editable draw.io shapes whenever possible.",
        editability_note="Simple geometry stays editable; some transformed shapes may use stencil approximation.",
        fidelity_note="Very complex transformed geometry may still be baked into a stencil.",
        native_message="These shapes stayed as editable draw.io vectors.",
        approximate_message="These shapes stayed editable, but a few geometry details were simplified.",
        fallback_message="Some shapes were preserved as embedded SVG instead of editable vectors.",
        ignored_message="Some shapes could not be carried over correctly.",
    ),
    "text": _profile(
        "text",
        label="Text labels",
        description="SVG text, nested tspans, foreignObject labels, anchors, text measurements, and textPath layout.",
        default_behavior="Converted to editable draw.io text with automatic text measurement.",
        editability_note="Text stays editable even when some layout details must be approximated.",
        fidelity_note=(
            "Qt, Pillow, or Tk font metrics improve sizing, while heuristic mode favors deterministic output."
        ),
        native_message="Text stayed editable as draw.io text labels.",
        approximate_message="Text stayed editable, but some text layout details were approximated.",
        fallback_message="Some text was preserved as embedded SVG instead of editable text.",
        ignored_message="Some text layout features could not be carried over.",
    ),
    "gradients": _profile(
        "gradients",
        label="Gradients",
        description="Linear, radial, and multi-stop gradients.",
        default_behavior=(
            "Auto mode keeps native gradients when the engine can approximate them well, "
            "otherwise it falls back to embedded SVG."
        ),
        editability_note="Prefer-native keeps more output editable, but complex gradients may be simplified.",
        fidelity_note=(
            "Prefer-fallback preserves the original look through embedded SVG when native gradients are not enough."
        ),
        native_message="Gradients stayed editable using draw.io gradient styles.",
        approximate_message="Gradients stayed editable, but complex gradients were simplified.",
        fallback_message="Some gradients were preserved as embedded SVG for visual fidelity.",
        ignored_message="Some gradient information could not be carried over.",
    ),
    "filters": _profile(
        "filters",
        label="Filters and shadows",
        description="SVG filter effects such as shadows, blur, glow, and offsets.",
        default_behavior=(
            "Native draw.io shadow styling is used when possible; unsupported filters can still fall back."
        ),
        editability_note=(
            "Prefer-native drops unsupported filters or approximates light effects to keep shapes editable."
        ),
        fidelity_note="Force-fallback preserves filtered content visually, but those fragments are less editable.",
        native_message="Supported filters stayed editable with native draw.io styling.",
        approximate_message=(
            "Some filter effects stayed editable, but were simplified to the closest native shadow/glow."
        ),
        fallback_message="Some filter effects were preserved as embedded SVG.",
        ignored_message="Some filter effects could not be carried over.",
    ),
    "clipping": _profile(
        "clipping",
        label="Clip paths and masks",
        description="SVG clip paths and masking effects.",
        default_behavior="Simple cases may stay editable; more advanced clips and masks fall back to embedded SVG.",
        editability_note=(
            "Simple circular, elliptical, rectangular, or polygonal clips can be rewritten into editable shapes."
        ),
        fidelity_note="Complex clip and mask effects are preserved visually through embedded SVG fallback.",
        native_message="Clip and mask effects stayed editable.",
        approximate_message="Clip or mask effects stayed editable, but were simplified.",
        fallback_message="Clip or mask effects were preserved as embedded SVG.",
        ignored_message="Clip or mask effects could not be carried over.",
    ),
    "patterns": _profile(
        "patterns",
        label="Pattern fills",
        description="Repeated fills defined with `<pattern>`.",
        default_behavior=(
            "Simple dot, stripe, and grid patterns may stay editable; more complex patterns fall back to embedded SVG."
        ),
        editability_note="Simple repeating motifs can be expanded into editable draw.io geometry.",
        fidelity_note="SVG fallback keeps intricate pattern artwork visually intact.",
        native_message="Pattern fills stayed editable.",
        approximate_message="Pattern fills stayed editable, but were expanded into repeated native geometry.",
        fallback_message="Pattern fills were preserved as embedded SVG.",
        ignored_message="Pattern fills could not be carried over.",
    ),
    "markers": _profile(
        "markers",
        label="Arrowheads and markers",
        description="Marker-start, marker-mid, and marker-end decorations.",
        default_behavior="Mapped to the closest editable draw.io arrows when possible.",
        editability_note="Simple custom markers can be emitted as small editable endpoint shapes.",
        fidelity_note="Very custom marker artwork may still be approximated rather than matched exactly.",
        native_message="Markers stayed editable as draw.io arrows.",
        approximate_message="Markers stayed editable, but were matched to the closest draw.io arrows.",
        fallback_message="Markers were preserved visually through embedded SVG.",
        ignored_message="Some markers could not be carried over.",
    ),
    "images": _profile(
        "images",
        label="Images",
        description="Embedded, local, or linked raster/SVG image content.",
        default_behavior="Embedded as draw.io image cells.",
        editability_note="Images remain movable and resizable, but not vector-editable.",
        fidelity_note="Some skew-heavy transforms are approximated because draw.io images do not support true shear.",
        native_message="Images were kept as draw.io image cells.",
        approximate_message="Images were kept, but some transform or loading details were simplified.",
        fallback_message="Images were wrapped through SVG fallback for visual fidelity.",
        ignored_message="Some images could not be loaded or embedded safely.",
    ),
    "references": _profile(
        "references",
        label="Reused SVG content",
        description="Nested SVGs, symbols, and internal `<use>` references.",
        default_behavior="Expanded into editable draw.io content.",
        editability_note="Expanded content stays editable instead of remaining an opaque reference.",
        fidelity_note="Structure may be flattened compared to the original SVG reuse graph.",
        native_message="Reused SVG content stayed editable after expansion.",
        approximate_message="Reused SVG content stayed editable, but some structure was simplified.",
        fallback_message="Some reused SVG content was preserved as embedded SVG.",
        ignored_message="Some reused SVG content could not be carried over.",
    ),
    "unsupported": _profile(
        "unsupported",
        label="Unsupported SVG features",
        description="Features that are outside the current native engine coverage.",
        default_behavior=(
            "Unsupported features are either approximated, preserved through fallback, or skipped when necessary."
        ),
        editability_note="Approximation keeps more of the document editable, but some SVG semantics may be flattened.",
        fidelity_note="Fallback preserves the original look better when draw.io has no direct equivalent.",
        native_message="All encountered features were supported.",
        approximate_message="Some unsupported features were approximated.",
        fallback_message="Some unsupported features were preserved as embedded SVG.",
        ignored_message="Some unsupported features were skipped or only partially preserved.",
    ),
    "limits": _profile(
        "limits",
        label="Large-file limits",
        description="Truncation or safety limits applied during conversion.",
        default_behavior=(
            "Safety limits protect the conversion from exploding output size or invalid fallback placement."
        ),
        editability_note="When limits are not hit, output stays as editable as the engine allows.",
        fidelity_note="If a limit is hit, the engine favors a safe partial result over a broken document.",
        native_message="No conversion limits were triggered.",
        approximate_message="The file stayed editable with a few safety simplifications.",
        fallback_message="Some large fragments were preserved through fallback rendering.",
        ignored_message="The file hit a conversion limit, so some content was not emitted.",
    ),
}

_DEFAULT_PROFILE = _profile(
    "other",
    label="Other SVG features",
    description="Miscellaneous SVG features noticed during conversion.",
    default_behavior="Handled case by case by the engine.",
    editability_note="Some features stay editable while others may need approximation.",
    fidelity_note="Fallback may be used when draw.io has no direct representation.",
    native_message="This content stayed editable in draw.io.",
    approximate_message="This content stayed editable, but the engine simplified it a little.",
    fallback_message="This content was preserved as embedded SVG for visual fidelity.",
    ignored_message="This content could not be fully carried over.",
)

_PUBLIC_CAPABILITY_KEYS: tuple[str, ...] = (
    "shapes",
    "text",
    "gradients",
    "filters",
    "clipping",
    "patterns",
    "markers",
    "images",
    "references",
)

_ISSUE_MAP: dict[str, tuple[str, CompatibilityStatus, str | None]] = {
    codes.CLIP_PATH_SIMPLIFIED_NATIVE: (
        "clipping",
        "approximate",
        "Simple clip paths were rewritten into editable replacement shapes.",
    ),
    codes.MASK_SIMPLIFIED_NATIVE: (
        "clipping",
        "approximate",
        "Simple masks were rewritten into editable replacement shapes.",
    ),
    codes.PATTERN_SIMPLIFIED_NATIVE: (
        "patterns",
        "approximate",
        "Simple repeating patterns were expanded into editable draw.io geometry.",
    ),
    codes.CLIP_PATH_FALLBACK: ("clipping", "fallback", "Clip paths were preserved as embedded SVG."),
    codes.MASK_FALLBACK: ("clipping", "fallback", "Masks were preserved as embedded SVG."),
    codes.PATTERN_FALLBACK: ("patterns", "fallback", "Pattern fills were preserved as embedded SVG."),
    codes.FILTER_FALLBACK: ("filters", "fallback", "Filter effects were preserved as embedded SVG."),
    codes.FILTER_IGNORED_FOR_EDITABILITY: (
        "filters",
        "approximate",
        "Unsupported filters were dropped to keep nearby shapes editable.",
    ),
    codes.FILTER_SIMPLIFIED_NATIVE: (
        "filters",
        "approximate",
        None,
    ),
    codes.MULTI_STOP_GRADIENT_FALLBACK: (
        "gradients",
        "fallback",
        "Complex gradients were preserved as embedded SVG.",
    ),
    codes.MULTI_STOP_GRADIENT_REDUCED: (
        "gradients",
        "approximate",
        "Complex gradients were simplified to stay editable.",
    ),
    codes.TEXT_BACKEND_HEURISTIC: (
        "text",
        "approximate",
        "Text box sizes were estimated with the built-in heuristic.",
    ),
    codes.TEXT_BACKEND_SYSTEM: (
        "text",
        "native",
        "Text box sizes were measured with a real system font backend.",
    ),
    codes.TEXT_PATH_APPROXIMATED: (
        "text",
        "approximate",
        "Text on a path was approximated with rotated editable glyphs.",
    ),
    codes.DOMINANT_BASELINE_APPROXIMATED: (
        "text",
        "approximate",
        "Dominant-baseline alignment was approximated.",
    ),
    codes.LETTER_SPACING_IGNORED: (
        "text",
        "ignored",
        "Letter spacing is not preserved natively in draw.io text.",
    ),
    codes.LETTER_SPACING_APPROXIMATED: (
        "text",
        "approximate",
        "Letter spacing was approximated with editable positioned glyphs.",
    ),
    codes.TEXT_LENGTH_APPROXIMATED: (
        "text",
        "approximate",
        "Text length constraints were approximated with editable positioned glyphs.",
    ),
    codes.FOREIGN_OBJECT_TEXT_APPROXIMATED: (
        "text",
        "approximate",
        "HTML text inside foreignObject was flattened to editable draw.io text.",
    ),
    codes.IMAGE_SHEAR_APPROXIMATED: (
        "images",
        "approximate",
        "Sheared images were placed using their transformed bounding box.",
    ),
    codes.IMAGE_REMOTE_LINKED: (
        "images",
        "approximate",
        "Remote images stay linked instead of being embedded locally.",
    ),
    codes.MAX_ELEMENTS_TRUNCATED: (
        "limits",
        "ignored",
        "The element limit was reached, so the output was truncated.",
    ),
    codes.FALLBACK_BOUNDS_MISSING: (
        "limits",
        "ignored",
        "One SVG fallback fragment could not be positioned safely.",
    ),
    codes.USE_CYCLE_DETECTED: (
        "references",
        "ignored",
        "A circular <use> reference was detected and skipped.",
    ),
}


def capability_keys() -> tuple[str, ...]:
    """Return the stable set of public capability keys accepted by user-facing APIs."""
    return tuple(sorted(_PUBLIC_CAPABILITY_KEYS))


def capability_descriptor(capability_key: str) -> CapabilityDescriptor | None:
    """Return one registered capability descriptor."""
    profile = _PROFILES.get(capability_key)
    if profile is None and capability_key == _DEFAULT_PROFILE.key:
        return _DEFAULT_PROFILE.capability
    return profile.capability if profile is not None else None


def all_capability_descriptors() -> list[CapabilityDescriptor]:
    """Return public capability descriptors in label order."""
    descriptors = [_PROFILES[key].capability for key in _PUBLIC_CAPABILITY_KEYS]
    return sorted(descriptors, key=lambda descriptor: descriptor.label.lower())


def feature_definition(feature_key: str) -> FeatureDefinition:
    """Return the registered feature definition for one compatibility family."""
    profile = _PROFILES.get(feature_key)
    return profile.feature if profile is not None else _DEFAULT_PROFILE.feature


def status_label(status: CompatibilityStatus) -> str:
    """Return the short user-facing label for one compatibility status."""
    return _STATUS_LABELS[status]


def merge_status(left: CompatibilityStatus, right: CompatibilityStatus) -> CompatibilityStatus:
    """Return the visually riskier of two compatibility statuses."""
    return left if _STATUS_ORDER[left] >= _STATUS_ORDER[right] else right


def normalize_status(value: str) -> CompatibilityStatus:
    """Clamp a raw status string into one of the supported compatibility statuses."""
    if value in _STATUS_ORDER:
        return cast(CompatibilityStatus, value)
    return "native"


def issue_observation_payload(
    code: str,
    message: str,
    *,
    element_tag: str | None = None,
) -> tuple[str, CompatibilityStatus, str] | None:
    """Return the feature/status/detail tuple implied by one diagnostic issue."""
    mapped = _ISSUE_MAP.get(code)
    if mapped is not None:
        feature_key, status, detail = mapped
        return feature_key, status, detail or message
    if code == codes.IGNORED_UNSUPPORTED_ELEMENT:
        detail = f"The SVG uses <{element_tag}> which is not supported natively." if element_tag else message
        return "unsupported", "ignored", detail
    if code in {codes.CONVERSION_FAILED, codes.ANALYSIS_FAILED}:
        return "unsupported", "ignored", message
    return None
