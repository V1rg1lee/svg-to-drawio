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
        user_cells = self._user_cells(root)
        self.assertFalse(any(cell.get("value") == "Hello path" for cell in user_cells))
        glyph_cells = [cell for cell in user_cells if cell.get("value") in set("Hello path")]
        self.assertGreaterEqual(len(glyph_cells), 9)
        self.assertTrue(any("rotation=" in (cell.get("style") or "") for cell in glyph_cells))
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

    def test_letter_spacing_is_reported_as_an_approximation(self) -> None:
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
        glyph_cells = [cell for cell in self._user_cells(root) if cell.get("value") in set("TRACKING")]
        self.assertGreaterEqual(len(glyph_cells), 8)
        self.assertIn("letter-spacing-approximated", {issue.code for issue in report.issues})
        rows = {row.feature_key: row for row in report.compatibility_matrix}
        self.assertIn("text", rows)
        self.assertEqual(rows["text"].status, "approximate")

    def test_text_length_is_reported_as_an_approximation(self) -> None:
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg" width="260" height="100">
          <text x="20" y="50" font-size="20" textLength="160" fill="#0f766e">
            STRETCH
          </text>
        </svg>
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            svg_path = path.join(tmpdir, "text-length.svg")
            with open(svg_path, "w", encoding="utf-8") as handle:
                handle.write(svg)

            converter = Converter()
            xml = converter.convert_to_string(svg_path)
            report = converter.get_report()

        root = ET.fromstring(xml)
        glyph_cells = [cell for cell in self._user_cells(root) if cell.get("value") in set("STRETCH")]
        self.assertGreaterEqual(len(glyph_cells), 7)
        self.assertIn("text-length-approximated", {issue.code for issue in report.issues})
        rows = {row.feature_key: row for row in report.compatibility_matrix}
        self.assertEqual(rows["text"].status, "approximate")

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

    def test_object_bounding_box_clip_path_can_stay_editable_through_geometry_rewrite(self) -> None:
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg" width="180" height="120">
          <defs>
            <clipPath id="cut" clipPathUnits="objectBoundingBox">
              <circle cx="0.5" cy="0.5" r="0.4" />
            </clipPath>
          </defs>
          <rect x="20" y="20" width="120" height="60" fill="#7c3aed" clip-path="url(#cut)" />
        </svg>
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            svg_path = path.join(tmpdir, "clip-object-bbox.svg")
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

    def test_object_bounding_box_mask_can_stay_editable_through_geometry_rewrite(self) -> None:
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg" width="180" height="120">
          <defs>
            <mask id="soft-cut" maskContentUnits="objectBoundingBox">
              <circle cx="0.5" cy="0.5" r="0.4" fill="#ffffff" />
            </mask>
          </defs>
          <rect x="20" y="20" width="120" height="60" fill="#0ea5e9" mask="url(#soft-cut)" />
        </svg>
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            svg_path = path.join(tmpdir, "mask-object-bbox.svg")
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

    def test_polygon_target_can_stay_editable_with_a_simple_clip_rewrite(self) -> None:
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg" width="180" height="120">
          <defs>
            <clipPath id="cut">
              <polygon points="30,20 140,20 160,90 60,100" />
            </clipPath>
          </defs>
          <polygon
            points="20,10 165,15 170,105 15,100"
            fill="#ef4444"
            clip-path="url(#cut)"
          />
        </svg>
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            svg_path = path.join(tmpdir, "polygon-clip.svg")
            with open(svg_path, "w", encoding="utf-8") as handle:
                handle.write(svg)

            converter = Converter()
            xml = converter.convert_to_string(svg_path)
            report = converter.get_report()

        root = ET.fromstring(xml)
        cells = self._user_cells(root)
        self.assertEqual(len(cells), 1)
        self.assertIn("shape=stencil", cells[0].get("style", ""))
        self.assertEqual(report.fallback_count, 0)
        self.assertIn("clip-path-simplified-native", {issue.code for issue in report.issues})
        rows = {row.feature_key: row for row in report.compatibility_matrix}
        self.assertEqual(rows["clipping"].status, "approximate")

    def test_simple_pattern_expansion_is_reported_as_an_approximation(self) -> None:
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg" width="140" height="90">
          <defs>
            <pattern id="grid" width="12" height="12" patternUnits="userSpaceOnUse">
              <rect width="12" height="12" fill="#f8fafc" />
              <line x1="0" y1="0" x2="12" y2="0" stroke="#2563eb" stroke-width="1.5" />
              <line x1="0" y1="0" x2="0" y2="12" stroke="#2563eb" stroke-width="1.5" />
            </pattern>
          </defs>
          <rect x="10" y="10" width="84" height="48" fill="url(#grid)" stroke="#1e3a8a" stroke-width="2" />
        </svg>
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            svg_path = path.join(tmpdir, "pattern-native.svg")
            with open(svg_path, "w", encoding="utf-8") as handle:
                handle.write(svg)

            converter = Converter()
            converter.convert_to_string(svg_path)
            report = converter.get_report()

        rows = {row.feature_key: row for row in report.compatibility_matrix}
        self.assertIn("patterns", rows)
        self.assertEqual(rows["patterns"].status, "approximate")
        self.assertIn("editable", rows["patterns"].message.lower())

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
