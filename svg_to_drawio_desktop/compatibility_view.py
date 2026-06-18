"""Formatting helpers for the desktop compatibility panel."""

from __future__ import annotations

import html
from dataclasses import dataclass
from os import path

from svg_to_drawio.capabilities import capability_descriptor
from svg_to_drawio.compatibility import CompatibilityRow, observation_from_issue
from svg_to_drawio.diagnostics import ConversionReport


@dataclass(frozen=True)
class FeatureImpactEntry:
    """One grouped issue entry shown in the compatibility details dialog."""

    file_label: str
    element_label: str
    message: str
    count: int = 1


def render_compatibility_html(rows: list[CompatibilityRow], *, palette: dict[str, str]) -> str:
    """Render the compatibility matrix as compact rich text for the results page."""
    if not rows:
        return '<div style="line-height:1.45;">No compatibility details were recorded for this run.</div>'

    status_colors = {
        "native": palette["success_label"],
        "approximate": palette["warning_label"],
        "fallback": palette["log_info"],
        "ignored": palette["error_label"],
    }
    sorted_rows = sorted(
        rows,
        key=lambda row: (
            {"ignored": 3, "fallback": 2, "approximate": 1, "native": 0}.get(row.status, 0),
            row.label,
        ),
        reverse=True,
    )

    blocks: list[str] = []
    for row in sorted_rows:
        status_color = status_colors.get(row.status, palette["text"])
        detail_html = ""
        if row.details:
            detail_html = (
                f'<div style="margin-top:4px; color:{palette["text_muted"]};">{html.escape(row.details[0])}</div>'
            )
        blocks.append(
            '<div style="margin-bottom:10px; padding-bottom:10px; '
            f'border-bottom:1px solid {palette["card_border"]};">'
            f'<div><a href="capability:{html.escape(row.feature_key)}" '
            f'style="font-weight:700; color:{palette["text"]}; text-decoration:none;">{html.escape(row.label)}</a> '
            f'<span style="color:{status_color}; font-weight:700;">{html.escape(row.status_label)}</span></div>'
            f'<div style="margin-top:2px; color:{palette["text"]};">{html.escape(row.message)} '
            f'<span style="color:{palette["text_muted"]};">({row.count})</span></div>'
            f"{detail_html}"
            "</div>"
        )
    return "".join(blocks)


def build_feature_dialog_text(row: CompatibilityRow, reports: list[ConversionReport]) -> str:
    """Return the plain-English detail text for one clicked compatibility row."""
    descriptor = capability_descriptor(row.feature_key)
    lines: list[str] = [row.label, row.message]
    if descriptor is not None:
        lines.append("")
        lines.append(descriptor.description)
        lines.append(f"Default engine behavior: {descriptor.default_behavior}")
        lines.append(f"Editability tradeoff: {descriptor.editability_note}")
        lines.append(f"Visual fidelity tradeoff: {descriptor.fidelity_note}")
    if row.details:
        lines.append("")
        lines.append("Observed details:")
        lines.extend(f"- {detail}" for detail in row.details)

    impacts = collect_feature_impacts(row.feature_key, reports)
    if impacts:
        file_count = len({entry.file_label for entry in impacts})
        occurrence_count = sum(entry.count for entry in impacts)
        lines.append("")
        lines.append(f"Affected occurrences: {occurrence_count} across {file_count} file(s).")
        lines.append("Affected elements:")
        for impact in impacts[:15]:
            count_suffix = f" x{impact.count}" if impact.count > 1 else ""
            lines.append(f"- {impact.file_label} {impact.element_label}{count_suffix}: {impact.message}")

    return "\n".join(lines)


def collect_feature_impacts(feature_key: str, reports: list[ConversionReport]) -> list[FeatureImpactEntry]:
    """Collect issue-backed element occurrences for one compatibility feature."""
    grouped: dict[tuple[str, str, str], int] = {}
    for report in reports:
        file_label = path.basename(report.source_path) or report.source_path or "<memory>"
        for issue in report.issues:
            observation = observation_from_issue(issue.code, issue.message, element_tag=issue.element_tag)
            if observation is None or observation.feature_key != feature_key:
                continue
            tag = issue.element_tag or "element"
            identifier = f"{tag}#{issue.element_id}" if issue.element_id else tag
            key = (file_label, identifier, issue.message)
            grouped[key] = grouped.get(key, 0) + 1

    impacts = [
        FeatureImpactEntry(file_label=file_label, element_label=f"[{identifier}]", message=message, count=count)
        for (file_label, identifier, message), count in grouped.items()
    ]
    return sorted(impacts, key=lambda item: (-item.count, item.file_label, item.element_label, item.message))
