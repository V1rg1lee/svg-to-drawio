"""Rich conversion result objects shared by the public API and internal services."""

from __future__ import annotations

from dataclasses import dataclass

from .diagnostics import ConversionReport


@dataclass(frozen=True)
class ConversionResult:
    """Complete result of one SVG conversion run."""

    xml: str
    report: ConversionReport
    source_path: str | None = None
    output_path: str | None = None

    @property
    def compatibility_score(self) -> int:
        """Expose the underlying report score directly on the conversion result."""
        return self.report.compatibility_score

    @property
    def warning_count(self) -> int:
        """Expose the warning count directly on the conversion result."""
        return self.report.warning_count

    @property
    def fallback_count(self) -> int:
        """Expose the fallback count directly on the conversion result."""
        return self.report.fallback_count

    def to_dict(self) -> dict[str, object]:
        """Serialize the result into a JSON-friendly dictionary."""
        return {
            "source_path": self.source_path,
            "output_path": self.output_path,
            "xml": self.xml,
            "report": self.report.to_dict(),
        }
