"""Regression tests for checked-in SVG fixtures."""

from __future__ import annotations

import tempfile
from os import path

from svg_to_drawio import convert_file

from tests.helpers import FIXTURES_DIR, SvgTestCase


class FixtureRegressionTests(SvgTestCase):
    """Compare generated output against versioned fixture baselines."""

    def test_all_features_fixture_matches_checked_in_drawio_output(self) -> None:
        svg_path = path.join(FIXTURES_DIR, "test_all_features.svg")
        expected_path = path.join(FIXTURES_DIR, "test_all_features.drawio")

        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = path.join(tmpdir, "test_all_features.drawio")
            convert_file(svg_path, out_path=out_path)

            with open(expected_path, encoding="utf-8") as handle:
                expected = handle.read()
            with open(out_path, encoding="utf-8") as handle:
                actual = handle.read()

        self.assertEqual(actual, expected)
