"""Tests for the richer public API surface and automation quality gates."""

from __future__ import annotations

import tempfile
from os import path

from svg_to_drawio import (
    REPORT_SCHEMA_VERSION,
    QualityGateOptions,
    convert_file_result,
    convert_svg_bytes_result,
    convert_svg_string_result,
    convert_to_string_result,
    evaluate_quality_gates,
)

from tests.helpers import FIXTURES_DIR, SvgTestCase


class ApiAndQualityTests(SvgTestCase):
    """Validate the public in-memory API helpers and quality gate evaluation."""

    def test_convert_svg_string_result_returns_xml_and_report(self) -> None:
        result = convert_svg_string_result(
            '<svg xmlns="http://www.w3.org/2000/svg" width="40" height="20">'
            '<rect x="0" y="0" width="40" height="20" fill="#ef4444" /></svg>',
            title="memory-diagram",
        )
        self.assertIn("<mxfile>", result.xml)
        self.assertEqual(result.source_path, "memory:memory-diagram.svg")
        self.assertGreaterEqual(result.compatibility_score, 0)
        self.assertEqual(result.report.to_dict()["schema_version"], REPORT_SCHEMA_VERSION)

    def test_convert_svg_bytes_result_can_resolve_local_assets_from_base_dir(self) -> None:
        svg = (
            b'<svg xmlns="http://www.w3.org/2000/svg" width="40" height="20">'
            b'<image href="image_asset.svg" x="0" y="0" width="20" height="20" /></svg>'
        )
        result = convert_svg_bytes_result(svg, title="asset-test", base_dir=FIXTURES_DIR)
        self.assertIn("<mxfile>", result.xml)
        self.assertTrue(any(asset.status == "embedded" for asset in result.report.assets))

    def test_convert_file_result_returns_written_output_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            svg_path = path.join(tmpdir, "diagram.svg")
            with open(svg_path, "w", encoding="utf-8") as handle:
                handle.write(
                    '<svg xmlns="http://www.w3.org/2000/svg" width="40" height="20">'
                    '<rect x="0" y="0" width="40" height="20" fill="#ef4444" /></svg>'
                )

            result = convert_file_result(svg_path)

        self.assertTrue(result.output_path and result.output_path.endswith(".drawio"))
        self.assertIn("<mxfile>", result.xml)

    def test_convert_to_string_result_matches_convert_to_string(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            svg_path = path.join(tmpdir, "diagram.svg")
            with open(svg_path, "w", encoding="utf-8") as handle:
                handle.write(
                    '<svg xmlns="http://www.w3.org/2000/svg" width="40" height="20">'
                    '<rect x="0" y="0" width="40" height="20" fill="#ef4444" /></svg>'
                )

            result = convert_to_string_result(svg_path)

        self.assertIsNone(result.output_path)
        self.assertEqual(result.source_path, svg_path)
        self.assertIn("<mxfile>", result.xml)

    def test_conversion_result_exposes_report_counters_and_serializes(self) -> None:
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg" width="120" height="80">
          <defs>
            <clipPath id="cut">
              <circle cx="40" cy="40" r="20" />
            </clipPath>
          </defs>
          <rect
            x="10"
            y="10"
            width="60"
            height="60"
            fill="#ff0000"
            stroke="#222222"
            stroke-width="2"
            clip-path="url(#cut)"
          />
        </svg>
        """
        result = convert_svg_string_result(svg, title="counters-check")

        self.assertEqual(result.compatibility_score, result.report.compatibility_score)
        self.assertEqual(result.warning_count, result.report.warning_count)
        self.assertEqual(result.fallback_count, result.report.fallback_count)
        self.assertGreaterEqual(result.fallback_count, 1)

        payload = result.to_dict()
        self.assertEqual(payload["xml"], result.xml)
        self.assertEqual(payload["source_path"], result.source_path)
        self.assertEqual(payload["output_path"], result.output_path)
        self.assertEqual(payload["report"], result.report.to_dict())

    def test_quality_gates_detect_fallbacks_and_non_native_capabilities(self) -> None:
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg" width="120" height="80">
          <defs>
            <clipPath id="cut">
              <circle cx="40" cy="40" r="20" />
            </clipPath>
          </defs>
          <rect
            x="10"
            y="10"
            width="60"
            height="60"
            fill="#ff0000"
            stroke="#222222"
            stroke-width="2"
            clip-path="url(#cut)"
          />
        </svg>
        """
        result = convert_svg_string_result(svg, title="quality-check")
        violations = evaluate_quality_gates(
            [result.report],
            QualityGateOptions(fail_on_fallback=True, require_native=("clipping",)),
        )
        self.assertEqual(len(violations), 2)
