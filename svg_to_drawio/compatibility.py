"""User-facing compatibility summaries shared by the engine, CLI, and desktop app."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, cast

CompatibilityStatus = Literal["native", "approximate", "fallback", "ignored"]

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


@dataclass(frozen=True)
class FeatureDefinition:
    """Human-readable description of one compatibility feature family."""

    key: str
    label: str
    description: str
    native_message: str
    approximate_message: str
    fallback_message: str
    ignored_message: str

    def message_for(self, status: CompatibilityStatus) -> str:
        """Return the end-user explanation for one feature status."""
        return {
            "native": self.native_message,
            "approximate": self.approximate_message,
            "fallback": self.fallback_message,
            "ignored": self.ignored_message,
        }[status]


@dataclass(frozen=True)
class FeatureObservation:
    """One low-level feature observation recorded during conversion."""

    feature_key: str
    status: CompatibilityStatus
    detail: str
    count: int = 1

    def identity(self) -> tuple[str, CompatibilityStatus, str]:
        """Return a stable identity used for deduplicating repeated observations."""
        return self.feature_key, self.status, self.detail

    def to_dict(self) -> dict[str, str | int]:
        """Serialize the observation into a JSON-friendly dictionary."""
        return {
            "feature_key": self.feature_key,
            "status": self.status,
            "detail": self.detail,
            "count": self.count,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> FeatureObservation:
        """Rehydrate a serialized feature observation."""
        count = payload.get("count", 1)
        if isinstance(count, bool):
            normalized_count = int(count)
        elif isinstance(count, int):
            normalized_count = count
        elif isinstance(count, float):
            normalized_count = int(count)
        elif isinstance(count, str):
            try:
                normalized_count = int(count)
            except ValueError:
                normalized_count = 1
        else:
            normalized_count = 1
        return cls(
            feature_key=str(payload.get("feature_key", "")),
            status=_normalize_status(str(payload.get("status", "native"))),
            detail=str(payload.get("detail", "")),
            count=max(1, normalized_count),
        )


@dataclass(frozen=True)
class CompatibilityRow:
    """Aggregated, user-facing view of one feature family."""

    feature_key: str
    label: str
    description: str
    status: CompatibilityStatus
    status_label: str
    message: str
    count: int
    details: list[str]

    def to_dict(self) -> dict[str, object]:
        """Serialize the aggregated row into a JSON-friendly dictionary."""
        return {
            "feature_key": self.feature_key,
            "label": self.label,
            "description": self.description,
            "status": self.status,
            "status_label": self.status_label,
            "message": self.message,
            "count": self.count,
            "details": list(self.details),
        }


@dataclass(frozen=True)
class CompatibilityOverview:
    """High-level beginner-friendly summary of a conversion report."""

    level: str
    headline: str
    summary: str

    def to_dict(self) -> dict[str, str]:
        """Serialize the overview into a JSON-friendly dictionary."""
        return {
            "level": self.level,
            "headline": self.headline,
            "summary": self.summary,
        }


_DEFAULT_FEATURE = FeatureDefinition(
    key="other",
    label="Other SVG features",
    description="Miscellaneous SVG features noticed during conversion.",
    native_message="This content stayed editable in draw.io.",
    approximate_message="This content stayed editable, but the engine simplified it a little.",
    fallback_message="This content was preserved as embedded SVG for visual fidelity.",
    ignored_message="This content could not be fully carried over.",
)

_FEATURES: dict[str, FeatureDefinition] = {
    "shapes": FeatureDefinition(
        key="shapes",
        label="Shapes and paths",
        description="Rectangles, circles, ellipses, polygons, lines, and general paths.",
        native_message="These shapes stayed as editable draw.io vectors.",
        approximate_message="These shapes stayed editable, but a few geometry details were simplified.",
        fallback_message="Some shapes were preserved as embedded SVG instead of editable vectors.",
        ignored_message="Some shapes could not be carried over correctly.",
    ),
    "text": FeatureDefinition(
        key="text",
        label="Text labels",
        description="SVG text, tspans, and text positioning.",
        native_message="Text stayed editable as draw.io text labels.",
        approximate_message="Text stayed editable, but some text layout details were approximated.",
        fallback_message="Some text was preserved as embedded SVG instead of editable text.",
        ignored_message="Some text layout features could not be carried over.",
    ),
    "gradients": FeatureDefinition(
        key="gradients",
        label="Gradients",
        description="Linear, radial, and multi-stop gradients.",
        native_message="Gradients stayed editable using draw.io gradient styles.",
        approximate_message="Gradients stayed editable, but complex gradients were simplified.",
        fallback_message="Some gradients were preserved as embedded SVG for visual fidelity.",
        ignored_message="Some gradient information could not be carried over.",
    ),
    "filters": FeatureDefinition(
        key="filters",
        label="Filters and shadows",
        description="SVG filter effects such as shadows and blur.",
        native_message="Supported filters stayed editable with native draw.io styling.",
        approximate_message="Some filter effects were dropped to keep nearby shapes editable.",
        fallback_message="Some filter effects were preserved as embedded SVG.",
        ignored_message="Some filter effects could not be carried over.",
    ),
    "clipping": FeatureDefinition(
        key="clipping",
        label="Clip paths and masks",
        description="SVG clip paths and masking effects.",
        native_message="Clip and mask effects stayed editable.",
        approximate_message="Clip or mask effects stayed editable, but were simplified.",
        fallback_message="Clip or mask effects were preserved as embedded SVG.",
        ignored_message="Clip or mask effects could not be carried over.",
    ),
    "patterns": FeatureDefinition(
        key="patterns",
        label="Pattern fills",
        description="Repeated SVG fills defined through `<pattern>`.",
        native_message="Pattern fills stayed editable.",
        approximate_message="Pattern fills stayed editable, but were simplified.",
        fallback_message="Pattern fills were preserved as embedded SVG.",
        ignored_message="Pattern fills could not be carried over.",
    ),
    "markers": FeatureDefinition(
        key="markers",
        label="Arrowheads and markers",
        description="SVG marker-start, marker-mid, and marker-end shapes.",
        native_message="Markers stayed editable as draw.io arrows.",
        approximate_message="Markers stayed editable, but were matched to the closest draw.io arrows.",
        fallback_message="Markers were preserved visually through embedded SVG.",
        ignored_message="Some markers could not be carried over.",
    ),
    "images": FeatureDefinition(
        key="images",
        label="Images",
        description="Embedded, local, or linked SVG image content.",
        native_message="Images were kept as draw.io image cells.",
        approximate_message="Images were kept, but some transform or loading details were simplified.",
        fallback_message="Images were wrapped through SVG fallback for visual fidelity.",
        ignored_message="Some images could not be loaded or embedded safely.",
    ),
    "references": FeatureDefinition(
        key="references",
        label="Reused SVG content",
        description="Nested SVGs, symbols, and internal `<use>` references.",
        native_message="Reused SVG content stayed editable after expansion.",
        approximate_message="Reused SVG content stayed editable, but some structure was simplified.",
        fallback_message="Some reused SVG content was preserved as embedded SVG.",
        ignored_message="Some reused SVG content could not be carried over.",
    ),
    "unsupported": FeatureDefinition(
        key="unsupported",
        label="Unsupported SVG features",
        description="Features that are outside the current native engine coverage.",
        native_message="All encountered features were supported.",
        approximate_message="Some unsupported features were approximated.",
        fallback_message="Some unsupported features were preserved as embedded SVG.",
        ignored_message="Some unsupported features were skipped or only partially preserved.",
    ),
    "limits": FeatureDefinition(
        key="limits",
        label="Large-file limits",
        description="Truncation or safety limits applied during conversion.",
        native_message="No conversion limits were triggered.",
        approximate_message="The file stayed editable with a few safety simplifications.",
        fallback_message="Some large fragments were preserved through fallback rendering.",
        ignored_message="The file hit a conversion limit, so some content was not emitted.",
    ),
}

_ISSUE_MAP: dict[str, tuple[str, CompatibilityStatus, str | None]] = {
    "clip-path-simplified-native": (
        "clipping",
        "approximate",
        "Simple clip paths were rewritten into editable replacement shapes.",
    ),
    "mask-simplified-native": (
        "clipping",
        "approximate",
        "Simple masks were rewritten into editable replacement shapes.",
    ),
    "clip-path-fallback": ("clipping", "fallback", "Clip paths were preserved as embedded SVG."),
    "mask-fallback": ("clipping", "fallback", "Masks were preserved as embedded SVG."),
    "pattern-fallback": ("patterns", "fallback", "Pattern fills were preserved as embedded SVG."),
    "filter-fallback": ("filters", "fallback", "Filter effects were preserved as embedded SVG."),
    "filter-ignored-for-editability": (
        "filters",
        "approximate",
        "Unsupported filters were dropped to keep nearby shapes editable.",
    ),
    "multi-stop-gradient-fallback": (
        "gradients",
        "fallback",
        "Complex gradients were preserved as embedded SVG.",
    ),
    "multi-stop-gradient-reduced": (
        "gradients",
        "approximate",
        "Complex gradients were simplified to stay editable.",
    ),
    "marker-approximated": (
        "markers",
        "approximate",
        "SVG markers were matched to the closest draw.io arrows.",
    ),
    "text-backend-heuristic": (
        "text",
        "approximate",
        "Text box sizes were estimated with the built-in heuristic.",
    ),
    "text-backend-system": (
        "text",
        "native",
        "Text box sizes were measured with a real system font backend.",
    ),
    "text-path-approximated": (
        "text",
        "approximate",
        "Text on a path was flattened into regular editable text.",
    ),
    "dominant-baseline-approximated": (
        "text",
        "approximate",
        "Dominant-baseline alignment was approximated.",
    ),
    "letter-spacing-ignored": (
        "text",
        "ignored",
        "Letter spacing is not preserved natively in draw.io text.",
    ),
    "image-shear-approximated": (
        "images",
        "approximate",
        "Sheared images were placed using their transformed bounding box.",
    ),
    "image-remote-linked": (
        "images",
        "approximate",
        "Remote images stay linked instead of being embedded locally.",
    ),
    "max-elements-truncated": (
        "limits",
        "ignored",
        "The element limit was reached, so the output was truncated.",
    ),
    "fallback-bounds-missing": (
        "limits",
        "ignored",
        "One SVG fallback fragment could not be positioned safely.",
    ),
}


def _normalize_status(value: str) -> CompatibilityStatus:
    """Clamp a raw status string into one of the supported compatibility statuses."""
    if value in _STATUS_ORDER:
        return cast(CompatibilityStatus, value)
    return "native"


def feature_definition(feature_key: str) -> FeatureDefinition:
    """Return the registered user-facing definition for one feature family."""
    return _FEATURES.get(feature_key, _DEFAULT_FEATURE)


def status_label(status: CompatibilityStatus) -> str:
    """Return the short user-facing label for one compatibility status."""
    return _STATUS_LABELS[status]


def merge_status(left: CompatibilityStatus, right: CompatibilityStatus) -> CompatibilityStatus:
    """Return the visually riskier of two compatibility statuses."""
    return left if _STATUS_ORDER[left] >= _STATUS_ORDER[right] else right


def observation_from_issue(
    code: str,
    message: str,
    *,
    element_tag: str | None = None,
) -> FeatureObservation | None:
    """Return a user-facing feature observation for one diagnostic issue code."""
    mapped = _ISSUE_MAP.get(code)
    if mapped is not None:
        feature_key, status, detail = mapped
        return FeatureObservation(feature_key=feature_key, status=status, detail=detail or message)
    if code == "ignored-unsupported-element":
        detail = f"The SVG uses <{element_tag}> which is not supported natively." if element_tag else message
        return FeatureObservation(feature_key="unsupported", status="ignored", detail=detail)
    if code in {"conversion-failed", "analysis-failed"}:
        return FeatureObservation(feature_key="unsupported", status="ignored", detail=message)
    return None


def observation_from_asset(
    *,
    status: str,
    message: str | None = None,
    mime_type: str | None = None,
) -> FeatureObservation | None:
    """Return a user-facing feature observation for one tracked asset record."""
    if status == "embedded":
        return FeatureObservation(
            feature_key="images",
            status="native",
            detail="Images were embedded into the output document.",
        )
    if status == "remote":
        detail = message or "Remote images stay linked instead of being embedded locally."
        return FeatureObservation(feature_key="images", status="approximate", detail=detail)
    if status in {"missing", "rejected", "invalid"}:
        detail = message or "An image could not be embedded safely."
        return FeatureObservation(feature_key="images", status="ignored", detail=detail)
    return None


def note_feature(
    feature_key: str,
    status: CompatibilityStatus,
    detail: str,
) -> FeatureObservation:
    """Build one explicit feature observation from engine-side code."""
    return FeatureObservation(feature_key=feature_key, status=status, detail=detail)


def note_text_backend(backend: str) -> FeatureObservation:
    """Return the user-facing observation for the active text measurement backend."""
    if backend == "heuristic":
        return FeatureObservation(
            feature_key="text",
            status="approximate",
            detail="Text box sizes were estimated with the built-in heuristic.",
        )
    return FeatureObservation(
        feature_key="text",
        status="native",
        detail="Text box sizes were measured with a real font backend.",
    )


def note_gradient_usage(*, approximated: bool) -> FeatureObservation:
    """Return the user-facing observation for one encountered gradient."""
    if approximated:
        return FeatureObservation(
            feature_key="gradients",
            status="approximate",
            detail="Complex gradients stayed editable through native approximation.",
        )
    return FeatureObservation(
        feature_key="gradients",
        status="native",
        detail="Gradients stayed editable with native draw.io gradient styles.",
    )


def note_filter_usage(*, native: bool) -> FeatureObservation:
    """Return the user-facing observation for one encountered filter."""
    if native:
        return FeatureObservation(
            feature_key="filters",
            status="native",
            detail="Supported shadows were mapped to native draw.io styling.",
        )
    return FeatureObservation(
        feature_key="filters",
        status="fallback",
        detail="Filter effects were preserved through embedded SVG fallback.",
    )


def note_marker_usage() -> FeatureObservation:
    """Return the user-facing observation for marker approximation."""
    return FeatureObservation(
        feature_key="markers",
        status="approximate",
        detail="SVG arrowheads were matched to the closest draw.io arrows.",
    )


def note_shape_usage(*, approximated: bool) -> FeatureObservation:
    """Return the user-facing observation for one encountered vector shape."""
    if approximated:
        return FeatureObservation(
            feature_key="shapes",
            status="approximate",
            detail="Some shapes were converted through baked geometry or stencil approximation.",
        )
    return FeatureObservation(
        feature_key="shapes",
        status="native",
        detail="Basic shapes and paths stayed as editable draw.io vectors.",
    )


def note_reference_usage() -> FeatureObservation:
    """Return the user-facing observation for nested SVG/use/symbol expansion."""
    return FeatureObservation(
        feature_key="references",
        status="native",
        detail="Reused SVG content was expanded into editable draw.io content.",
    )


def note_image_usage(*, approximated: bool) -> FeatureObservation:
    """Return the user-facing observation for SVG image handling."""
    if approximated:
        return FeatureObservation(
            feature_key="images",
            status="approximate",
            detail="Some image transforms were approximated to fit draw.io image cells.",
        )
    return FeatureObservation(
        feature_key="images",
        status="native",
        detail="Images were kept as draw.io image cells.",
    )


def build_compatibility_rows(
    observations: list[FeatureObservation],
    *,
    max_details: int = 3,
) -> list[CompatibilityRow]:
    """Aggregate raw observations into stable user-facing compatibility rows."""
    grouped: dict[str, list[FeatureObservation]] = {}
    for observation in observations:
        grouped.setdefault(observation.feature_key, []).append(observation)

    rows: list[CompatibilityRow] = []
    for feature_key in sorted(grouped, key=lambda key: feature_definition(key).label.lower()):
        definition = feature_definition(feature_key)
        feature_observations = grouped[feature_key]
        status: CompatibilityStatus = "native"
        total = 0
        details: list[str] = []
        for observation in feature_observations:
            status = merge_status(status, observation.status)
            total += max(1, observation.count)
            if observation.detail and observation.detail not in details and len(details) < max_details:
                details.append(observation.detail)
        rows.append(
            CompatibilityRow(
                feature_key=feature_key,
                label=definition.label,
                description=definition.description,
                status=status,
                status_label=status_label(status),
                message=definition.message_for(status),
                count=total,
                details=details,
            )
        )
    return rows


def build_compatibility_overview(rows: list[CompatibilityRow]) -> CompatibilityOverview:
    """Return a short beginner-friendly overview for a compatibility matrix."""
    if not rows:
        return CompatibilityOverview(
            level="no-data",
            headline="No compatibility data yet.",
            summary="Run a conversion first to see how the SVG was handled.",
        )

    worst_status: CompatibilityStatus = "native"
    for row in rows:
        worst_status = merge_status(worst_status, row.status)

    editable_count = sum(1 for row in rows if row.status == "native")
    approximate_count = sum(1 for row in rows if row.status == "approximate")
    fallback_count = sum(1 for row in rows if row.status == "fallback")
    ignored_count = sum(1 for row in rows if row.status == "ignored")

    if worst_status == "ignored":
        return CompatibilityOverview(
            level="limited",
            headline="Some SVG features could not be fully carried over.",
            summary=(
                f"{editable_count} feature area(s) stayed editable, "
                f"{approximate_count} were simplified, {fallback_count} used embedded SVG, "
                f"and {ignored_count} could not be fully preserved."
            ),
        )
    if worst_status == "fallback":
        return CompatibilityOverview(
            level="mixed",
            headline="Most content converted, but some parts were preserved as embedded SVG.",
            summary=(
                f"{editable_count} feature area(s) stayed fully editable, "
                f"{approximate_count} were simplified, and {fallback_count} used SVG fallback."
            ),
        )
    if worst_status == "approximate":
        return CompatibilityOverview(
            level="mostly-editable",
            headline="Everything stayed editable, with a few visual approximations.",
            summary=(
                f"{editable_count} feature area(s) stayed fully native and "
                f"{approximate_count} needed small simplifications."
            ),
        )
    return CompatibilityOverview(
        level="fully-editable",
        headline="Everything in this SVG stayed editable in draw.io.",
        summary=f"All {editable_count} detected feature area(s) converted natively.",
    )
