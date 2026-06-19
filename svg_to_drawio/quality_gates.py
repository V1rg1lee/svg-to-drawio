"""Shared compatibility quality gates used by the CLI and automation callers."""

from __future__ import annotations

from dataclasses import dataclass

from .capabilities import capability_keys
from .diagnostics import ConversionReport


@dataclass(frozen=True)
class QualityGateOptions:
    """User-configurable compatibility thresholds for automated runs."""

    fail_on_warning: bool = False
    fail_on_fallback: bool = False
    min_score: int | None = None
    require_native: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.min_score is None:
            return
        if not isinstance(self.min_score, int) or isinstance(self.min_score, bool):
            raise ValueError(f"min_score must be an int, got {type(self.min_score).__name__}.")
        if not 0 <= self.min_score <= 100:
            raise ValueError(f"min_score must be between 0 and 100, got {self.min_score}.")


@dataclass(frozen=True)
class QualityGateViolation:
    """One compatibility rule that a conversion report did not satisfy."""

    source_path: str
    message: str


def validate_required_capabilities(values: list[str]) -> tuple[str, ...]:
    """Validate capability keys provided by the user."""
    allowed = set(capability_keys())
    invalid = [value for value in values if value not in allowed]
    if invalid:
        expected = ", ".join(sorted(allowed))
        invalid_text = ", ".join(sorted(invalid))
        raise ValueError(f"Invalid capability key(s): {invalid_text}. Expected one of: {expected}.")
    return tuple(values)


def evaluate_quality_gates(
    reports: list[ConversionReport],
    options: QualityGateOptions,
) -> list[QualityGateViolation]:
    """Evaluate a batch of conversion reports against the configured quality thresholds."""
    violations: list[QualityGateViolation] = []

    for report in reports:
        source = report.source_path or "<unknown>"
        if options.fail_on_warning and report.warning_count:
            violations.append(
                QualityGateViolation(
                    source_path=source,
                    message=f"{source}: quality gate failed because {report.warning_count} warning(s) were reported.",
                )
            )
        if options.fail_on_fallback and report.fallback_count:
            violations.append(
                QualityGateViolation(
                    source_path=source,
                    message=(
                        f"{source}: quality gate failed because {report.fallback_count} "
                        "SVG fallback fragment(s) were used."
                    ),
                )
            )
        if options.min_score is not None and report.compatibility_score < options.min_score:
            violations.append(
                QualityGateViolation(
                    source_path=source,
                    message=(
                        f"{source}: quality gate failed because the compatibility score was "
                        f"{report.compatibility_score}, below the required {options.min_score}."
                    ),
                )
            )

        if not options.require_native:
            continue
        rows = {row.feature_key: row for row in report.compatibility_matrix}
        for feature_key in options.require_native:
            row = rows.get(feature_key)
            if row is None or row.status == "native":
                continue
            violations.append(
                QualityGateViolation(
                    source_path=source,
                    message=(
                        f"{source}: quality gate failed because {feature_key!r} was {row.status_label.lower()} "
                        "instead of fully native."
                    ),
                )
            )

    return violations
