"""Tests for user-facing compatibility summaries and approximations."""

from __future__ import annotations

import base64
import tempfile
import xml.etree.ElementTree as ET
from os import path

from svg_to_drawio.converter import Converter

from tests.helpers import SvgTestCase


class CompatibilityTests(SvgTestCase):
    """Exercise the beginner-friendly compatibility matrix exposed by reports."""

    def test_clip_path_fallback_populates_user_facing_compatibility_rows(self) -> None:
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
        with tempfile.TemporaryDirectory() as tmpdir:
            svg_path = path.join(tmpdir, "clip.svg")
            with open(svg_path, "w", encoding="utf-8") as handle:
                handle.write(svg)

            converter = Converter()
            converter.convert_to_string(svg_path)
            report = converter.get_report()

        rows = {row.feature_key: row for row in report.compatibility_matrix}
        self.assertIn("clipping", rows)
        self.assertEqual(rows["clipping"].status, "fallback")
        self.assertEqual(report.compatibility_overview.level, "mixed")
        self.assertIn("embedded SVG", rows["clipping"].message)

    def test_text_path_is_flattened_into_editable_text_and_reported(self) -> None:
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg" width="180" height="80">
          <defs>
            <path id="curve" d="M 10 55 C 55 15 120 15 170 50" />
          </defs>
          <text x="12" y="48" font-size="18" fill="#1d4ed8">
            <textPath href="#curve">Hello path</textPath>
          </text>
        </svg>
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            svg_path = path.join(tmpdir, "textpath.svg")
            with open(svg_path, "w", encoding="utf-8") as handle:
                handle.write(svg)

            converter = Converter()
            xml = converter.convert_to_string(svg_path)
            report = converter.get_report()

        root = ET.fromstring(xml)
        text_cells = [cell for cell in self._user_cells(root) if cell.get("value") == "Hello path"]
        self.assertTrue(text_cells)
        self.assertIn("text-path-approximated", {issue.code for issue in report.issues})
        rows = {row.feature_key: row for row in report.compatibility_matrix}
        self.assertIn("text", rows)
        self.assertEqual(rows["text"].status, "approximate")
        self.assertIn("editable", rows["text"].message.lower())

    def test_dominant_baseline_is_reported_as_an_approximation(self) -> None:
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg" width="220" height="100">
          <line x1="10" y1="50" x2="210" y2="50" stroke="#cbd5e1" stroke-width="2" />
          <text x="20" y="50" font-size="20" dominant-baseline="middle" fill="#2563eb">
            Middle baseline
          </text>
        </svg>
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            svg_path = path.join(tmpdir, "baseline.svg")
            with open(svg_path, "w", encoding="utf-8") as handle:
                handle.write(svg)

            converter = Converter()
            xml = converter.convert_to_string(svg_path)
            report = converter.get_report()

        root = ET.fromstring(xml)
        text_cells = [cell for cell in self._user_cells(root) if cell.get("value") == "Middle baseline"]
        self.assertTrue(text_cells)
        self.assertIn("dominant-baseline-approximated", {issue.code for issue in report.issues})
        rows = {row.feature_key: row for row in report.compatibility_matrix}
        self.assertIn("text", rows)
        self.assertEqual(rows["text"].status, "approximate")

    def test_letter_spacing_is_reported_as_not_fully_preserved(self) -> None:
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg" width="220" height="100">
          <text x="20" y="50" font-size="20" letter-spacing="6" fill="#b45309">
            TRACKING
          </text>
        </svg>
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            svg_path = path.join(tmpdir, "tracking.svg")
            with open(svg_path, "w", encoding="utf-8") as handle:
                handle.write(svg)

            converter = Converter()
            xml = converter.convert_to_string(svg_path)
            report = converter.get_report()

        root = ET.fromstring(xml)
        text_cells = [cell for cell in self._user_cells(root) if cell.get("value") == "TRACKING"]
        self.assertTrue(text_cells)
        self.assertIn("letter-spacing-ignored", {issue.code for issue in report.issues})
        rows = {row.feature_key: row for row in report.compatibility_matrix}
        self.assertIn("text", rows)
        self.assertEqual(rows["text"].status, "ignored")

    def test_simple_clip_path_can_stay_editable_through_geometry_rewrite(self) -> None:
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg" width="120" height="80">
          <defs>
            <clipPath id="cut">
              <circle cx="40" cy="40" r="20" />
            </clipPath>
          </defs>
          <rect x="10" y="10" width="60" height="60" fill="#ff0000" clip-path="url(#cut)" />
        </svg>
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            svg_path = path.join(tmpdir, "clip-native.svg")
            with open(svg_path, "w", encoding="utf-8") as handle:
                handle.write(svg)

            converter = Converter()
            xml = converter.convert_to_string(svg_path)
            report = converter.get_report()

        root = ET.fromstring(xml)
        cells = self._user_cells(root)
        self.assertEqual(len(cells), 1)
        self.assertEqual(self._style_map(cells[0]).get("ellipse"), True)
        self.assertEqual(report.fallback_count, 0)
        self.assertIn("clip-path-simplified-native", {issue.code for issue in report.issues})
        rows = {row.feature_key: row for row in report.compatibility_matrix}
        self.assertEqual(rows["clipping"].status, "approximate")

    def test_simple_mask_can_stay_editable_through_geometry_rewrite(self) -> None:
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg" width="120" height="80">
          <defs>
            <mask id="soft-cut" maskUnits="userSpaceOnUse">
              <circle cx="40" cy="40" r="20" fill="#ffffff" />
            </mask>
          </defs>
          <rect x="10" y="10" width="60" height="60" fill="#00bcd4" mask="url(#soft-cut)" />
        </svg>
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            svg_path = path.join(tmpdir, "mask-native.svg")
            with open(svg_path, "w", encoding="utf-8") as handle:
                handle.write(svg)

            converter = Converter()
            xml = converter.convert_to_string(svg_path)
            report = converter.get_report()

        root = ET.fromstring(xml)
        cells = self._user_cells(root)
        self.assertEqual(len(cells), 1)
        self.assertEqual(self._style_map(cells[0]).get("ellipse"), True)
        self.assertEqual(report.fallback_count, 0)
        self.assertIn("mask-simplified-native", {issue.code for issue in report.issues})
        rows = {row.feature_key: row for row in report.compatibility_matrix}
        self.assertEqual(rows["clipping"].status, "approximate")

    def test_sheared_image_is_reported_as_an_approximation(self) -> None:
        png = base64.b64encode(
            bytes.fromhex(
                "89504E470D0A1A0A0000000D49484452000000010000000108060000001F15C489"
                "0000000D49444154789C6360F8CFC0000003010100C9FE92EF0000000049454E44AE426082"
            )
        ).decode("ascii")
        svg = f"""
        <svg xmlns="http://www.w3.org/2000/svg" width="120" height="90">
          <image
            x="10"
            y="10"
            width="50"
            height="32"
            transform="skewX(18)"
            href="data:image/png;base64,{png}"
          />
        </svg>
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            svg_path = path.join(tmpdir, "image.svg")
            with open(svg_path, "w", encoding="utf-8") as handle:
                handle.write(svg)

            converter = Converter()
            converter.convert_to_string(svg_path)
            report = converter.get_report()

        self.assertIn("image-shear-approximated", {issue.code for issue in report.issues})
        rows = {row.feature_key: row for row in report.compatibility_matrix}
        self.assertIn("images", rows)
        self.assertEqual(rows["images"].status, "approximate")
