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
