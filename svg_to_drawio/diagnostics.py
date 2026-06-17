"""Structured diagnostics collected during one SVG conversion run."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from .compatibility import (
    CompatibilityOverview,
    CompatibilityRow,
    FeatureObservation,
    build_compatibility_overview,
    build_compatibility_rows,
    observation_from_asset,
    observation_from_issue,
)

REPORT_SCHEMA_VERSION = 1


def _payload_int(payload: dict[str, object], key: str, default: int = 0) -> int:
    """Read one integer-ish value from a loosely typed JSON payload."""
    value = payload.get(key, default)
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default


def _payload_list(payload: dict[str, object], key: str) -> list[object]:
    """Read one list value from a loosely typed JSON payload."""
    value = payload.get(key, [])
    return value if isinstance(value, list) else []


@dataclass(frozen=True)
class DiagnosticIssue:
    """One structured warning, fallback note, or failure detail."""

    code: str
    severity: str
    message: str
    element_tag: str | None = None
    element_id: str | None = None
    fallback_used: bool = False

    def identity(self) -> tuple[str, str | None, str | None, bool]:
        """Return a stable identity used for deduplicating repeated issues."""
        return self.code, self.element_tag, self.element_id, self.fallback_used

    def to_dict(self) -> dict[str, str | bool | None]:
        """Serialize the issue into a JSON-friendly dictionary."""
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "element_tag": self.element_tag,
            "element_id": self.element_id,
            "fallback_used": self.fallback_used,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> DiagnosticIssue:
        """Rehydrate a serialized issue."""
        return cls(
            code=str(payload.get("code", "")),
            severity=str(payload.get("severity", "warning")),
            message=str(payload.get("message", "")),
            element_tag=str(payload["element_tag"]) if payload.get("element_tag") is not None else None,
            element_id=str(payload["element_id"]) if payload.get("element_id") is not None else None,
            fallback_used=bool(payload.get("fallback_used", False)),
        )


@dataclass(frozen=True)
class AssetReference:
    """One external or embedded image asset referenced by the SVG."""

    href: str
    status: str
    resolved_path: str | None = None
    mime_type: str | None = None
    message: str | None = None

    def identity(self) -> tuple[str, str, str | None]:
        """Return a stable identity used for deduplicating asset records."""
        return self.href, self.status, self.resolved_path

    def to_dict(self) -> dict[str, str | None]:
        """Serialize the asset record into a JSON-friendly dictionary."""
        return {
            "href": self.href,
            "status": self.status,
            "resolved_path": self.resolved_path,
            "mime_type": self.mime_type,
            "message": self.message,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> AssetReference:
        """Rehydrate a serialized asset record."""
        return cls(
            href=str(payload.get("href", "")),
            status=str(payload.get("status", "unknown")),
            resolved_path=str(payload["resolved_path"]) if payload.get("resolved_path") is not None else None,
            mime_type=str(payload["mime_type"]) if payload.get("mime_type") is not None else None,
            message=str(payload["message"]) if payload.get("message") is not None else None,
        )


@dataclass
class ConversionReport:
    """Mutable diagnostic report for one input SVG file."""

    source_path: str = ""
    output_path: str | None = None
    generated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    analyze_only: bool = False
    cached: bool = False
    truncated: bool = False
    fallback_count: int = 0
    emitted_cells: int = 0
    issues: list[DiagnosticIssue] = field(default_factory=list)
    assets: list[AssetReference] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    feature_observations: list[FeatureObservation] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._issue_keys: set[tuple[str, str | None, str | None, bool]] = {issue.identity() for issue in self.issues}
        self._asset_keys: set[tuple[str, str, str | None]] = {asset.identity() for asset in self.assets}
        self._dependency_keys: set[str] = set(self.dependencies)
        self._feature_observation_keys: dict[tuple[str, str, str], int] = {
            observation.identity(): index for index, observation in enumerate(self.feature_observations)
        }

    def clone(self) -> ConversionReport:
        """Return a detached copy suitable for events or cache snapshots."""
        return ConversionReport.from_dict(self.to_dict())

    def add_issue(
        self,
        code: str,
        severity: str,
        message: str,
        *,
        element_tag: str | None = None,
        element_id: str | None = None,
        fallback_used: bool = False,
    ) -> None:
        """Append a deduplicated issue to the report."""
        issue = DiagnosticIssue(
            code=code,
            severity=severity,
            message=message,
            element_tag=element_tag,
            element_id=element_id,
            fallback_used=fallback_used,
        )
        issue_key = issue.identity()
        if issue_key in self._issue_keys:
            return
        self._issue_keys.add(issue_key)
        self.issues.append(issue)
        compatibility_observation = observation_from_issue(code, message, element_tag=element_tag)
        if compatibility_observation is not None:
            self.record_feature_observation(compatibility_observation)

    def add_asset(
        self,
        href: str,
        status: str,
        *,
        resolved_path: str | None = None,
        mime_type: str | None = None,
        message: str | None = None,
    ) -> None:
        """Append a deduplicated asset reference to the report."""
        asset = AssetReference(
            href=href,
            status=status,
            resolved_path=resolved_path,
            mime_type=mime_type,
            message=message,
        )
        asset_key = asset.identity()
        if asset_key in self._asset_keys:
            return
        self._asset_keys.add(asset_key)
        self.assets.append(asset)
        compatibility_observation = observation_from_asset(status=status, message=message, mime_type=mime_type)
        if compatibility_observation is not None:
            self.record_feature_observation(compatibility_observation)

    def add_dependency(self, dependency_path: str | None) -> None:
        """Track one file path that should invalidate the conversion cache when it changes."""
        if not dependency_path:
            return
        if dependency_path in self._dependency_keys:
            return
        self._dependency_keys.add(dependency_path)
        self.dependencies.append(dependency_path)

    def record_feature_observation(self, observation: FeatureObservation) -> None:
        """Append or increment a deduplicated user-facing feature observation."""
        observation_key = observation.identity()
        existing_index = self._feature_observation_keys.get(observation_key)
        if existing_index is not None:
            current = self.feature_observations[existing_index]
            self.feature_observations[existing_index] = FeatureObservation(
                feature_key=current.feature_key,
                status=current.status,
                detail=current.detail,
                count=current.count + max(1, observation.count),
            )
            return
        self._feature_observation_keys[observation_key] = len(self.feature_observations)
        self.feature_observations.append(observation)

    @property
    def warning_count(self) -> int:
        """Return the number of warning-level issues recorded for this file."""
        return sum(1 for issue in self.issues if issue.severity == "warning")

    @property
    def error_count(self) -> int:
        """Return the number of error-level issues recorded for this file."""
        return sum(1 for issue in self.issues if issue.severity == "error")

    @property
    def compatibility_score(self) -> int:
        """Return a coarse compatibility score suitable for summaries and reports."""
        score = 100
        score -= self.fallback_count * 12
        score -= self.warning_count * 6
        score -= self.error_count * 18
        score -= sum(8 for asset in self.assets if asset.status in {"missing", "rejected", "invalid"})
        if self.truncated:
            score -= 20
        return max(0, score)

    @property
    def compatibility_matrix(self) -> list[CompatibilityRow]:
        """Return a beginner-friendly compatibility matrix for the converted file."""
        return build_compatibility_rows(self.feature_observations)

    @property
    def compatibility_overview(self) -> CompatibilityOverview:
        """Return a short beginner-friendly compatibility summary."""
        return build_compatibility_overview(self.compatibility_matrix)

    def short_status(self) -> str:
        """Return a compact human-readable status line for logs and the CLI."""
        parts = [f"score {self.compatibility_score}/100"]
        if self.fallback_count:
            parts.append(f"{self.fallback_count} fallback(s)")
        if self.warning_count:
            parts.append(f"{self.warning_count} warning(s)")
        if self.error_count:
            parts.append(f"{self.error_count} error(s)")
        if self.cached:
            parts.append("cache hit")
        if self.truncated:
            parts.append("truncated")
        return ", ".join(parts)

    def to_dict(self) -> dict[str, object]:
        """Serialize the full report into a JSON-friendly dictionary."""
        return {
            "schema_version": REPORT_SCHEMA_VERSION,
            "source_path": self.source_path,
            "output_path": self.output_path,
            "generated_at": self.generated_at,
            "analyze_only": self.analyze_only,
            "cached": self.cached,
            "truncated": self.truncated,
            "fallback_count": self.fallback_count,
            "emitted_cells": self.emitted_cells,
            "compatibility_score": self.compatibility_score,
            "issues": [issue.to_dict() for issue in self.issues],
            "assets": [asset.to_dict() for asset in self.assets],
            "dependencies": list(self.dependencies),
            "feature_observations": [observation.to_dict() for observation in self.feature_observations],
            "compatibility_overview": self.compatibility_overview.to_dict(),
            "compatibility_matrix": [row.to_dict() for row in self.compatibility_matrix],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> ConversionReport:
        """Rehydrate a serialized conversion report."""
        return cls(
            source_path=str(payload.get("source_path", "")),
            output_path=str(payload["output_path"]) if payload.get("output_path") is not None else None,
            generated_at=str(payload.get("generated_at", datetime.now(UTC).isoformat())),
            analyze_only=bool(payload.get("analyze_only", False)),
            cached=bool(payload.get("cached", False)),
            truncated=bool(payload.get("truncated", False)),
            fallback_count=_payload_int(payload, "fallback_count"),
            emitted_cells=_payload_int(payload, "emitted_cells"),
            issues=[
                DiagnosticIssue.from_dict(item) for item in _payload_list(payload, "issues") if isinstance(item, dict)
            ],
            assets=[
                AssetReference.from_dict(item) for item in _payload_list(payload, "assets") if isinstance(item, dict)
            ],
            dependencies=[str(item) for item in _payload_list(payload, "dependencies") if item is not None],
            feature_observations=[
                FeatureObservation.from_dict(item)
                for item in _payload_list(payload, "feature_observations")
                if isinstance(item, dict)
            ],
        )
