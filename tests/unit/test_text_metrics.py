"""Tests for the text measurement backend selection."""

from __future__ import annotations

from unittest.mock import patch

from svg_to_drawio.text_metrics import measure_text_detailed

from tests.helpers import SvgTestCase


class TextMetricsTests(SvgTestCase):
    """Exercise the real-font backend selection chain."""

    def test_system_policy_prefers_qt_measurement_when_available(self) -> None:
        measure_text_detailed.cache_clear()
        with (
            patch("svg_to_drawio.text_metrics._measure_with_qt", return_value=(42.0, 18.0)) as qt_measure,
            patch("svg_to_drawio.text_metrics._measure_with_pillow", return_value=None) as pillow_measure,
            patch("svg_to_drawio.text_metrics._get_tk_root", side_effect=AssertionError("unexpected Tk lookup")),
        ):
            width, height, backend = measure_text_detailed("Hello", 12, "Helvetica", policy="system")

        self.assertEqual((width, height, backend), (42.0, 18.0, "qt"))
        qt_measure.assert_called_once()
        pillow_measure.assert_not_called()

    def test_zero_font_size_is_clamped_before_backend_measurement(self) -> None:
        """Prevent system backends from receiving an invalid zero-point font size."""

        measure_text_detailed.cache_clear()
        with (
            patch("svg_to_drawio.text_metrics._measure_with_qt", return_value=(10.0, 12.0, "qt")) as qt_measure,
            patch("svg_to_drawio.text_metrics._measure_with_pillow", return_value=None),
            patch("svg_to_drawio.text_metrics._get_tk_root", side_effect=AssertionError("unexpected Tk lookup")),
        ):
            width, height, backend = measure_text_detailed("", 0, "Helvetica", policy="system")

        self.assertEqual((width, height, backend), (10.0, 12.0, "qt"))
        qt_measure.assert_called_once_with(" ", 1.0, "Helvetica", bold=False, italic=False)
