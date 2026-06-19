"""GUI-independent helpers for preview-file selection state."""

from __future__ import annotations


def preview_report_index_to_combo_index(selected_report_index: int | None) -> int:
    """Map an optional report index to the visible combo-box index."""
    return 0 if selected_report_index is None else selected_report_index + 1


def preview_combo_index_to_report_index(combo_index: int) -> int | None:
    """Map one combo-box index back to the selected report index, if any."""
    return None if combo_index <= 0 else combo_index - 1
