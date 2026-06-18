"""User-facing compatibility summaries shared by the engine, CLI, and desktop app."""

from __future__ import annotations

from dataclasses import dataclass

from .capability_registry import (
    CompatibilityStatus,
    FeatureDefinition,
    feature_definition,
    issue_observation_payload,
    merge_status,
    normalize_status,
    status_label,
)


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
            status=normalize_status(str(payload.get("status", "native"))),
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


def observation_from_issue(
    code: str,
    message: str,
    *,
    element_tag: str | None = None,
) -> FeatureObservation | None:
    """Return a user-facing feature observation for one diagnostic issue code."""
    payload = issue_observation_payload(code, message, element_tag=element_tag)
    if payload is None:
        return None
    feature_key, status, detail = payload
    return FeatureObservation(feature_key=feature_key, status=status, detail=detail)


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
    if backend == "qt":
        return FeatureObservation(
            feature_key="text",
            status="native",
            detail="Text box sizes were measured with Qt text shaping and font metrics.",
        )
    if backend == "pillow":
        return FeatureObservation(
            feature_key="text",
            status="native",
            detail="Text box sizes were measured with Pillow using a real font file.",
        )
    if backend == "tk":
        return FeatureObservation(
            feature_key="text",
            status="native",
            detail="Text box sizes were measured with Tk system font metrics.",
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


def note_filter_usage(
    *,
    native: bool,
    approximated: bool = False,
    detail: str | None = None,
) -> FeatureObservation:
    """Return the user-facing observation for one encountered filter."""
    if approximated:
        return FeatureObservation(
            feature_key="filters",
            status="approximate",
            detail=detail or "SVG filters were simplified to the closest native draw.io shadow or glow.",
        )
    if native:
        return FeatureObservation(
            feature_key="filters",
            status="native",
            detail=detail or "Supported shadows were mapped to native draw.io styling.",
        )
    return FeatureObservation(
        feature_key="filters",
        status="fallback",
        detail=detail or "Filter effects were preserved through embedded SVG fallback.",
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


__all__ = [
    "CompatibilityOverview",
    "CompatibilityRow",
    "CompatibilityStatus",
    "FeatureDefinition",
    "FeatureObservation",
    "build_compatibility_overview",
    "build_compatibility_rows",
    "feature_definition",
    "merge_status",
    "note_feature",
    "note_filter_usage",
    "note_gradient_usage",
    "note_image_usage",
    "note_marker_usage",
    "note_reference_usage",
    "note_shape_usage",
    "note_text_backend",
    "observation_from_asset",
    "observation_from_issue",
    "status_label",
]
