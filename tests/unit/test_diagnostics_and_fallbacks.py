"""Tests for structured diagnostics and embedded SVG fallbacks."""

from __future__ import annotations

import re
import tempfile
import xml.etree.ElementTree as ET
from os import path
from urllib.parse import unquote

from svg_to_drawio.converter import Converter

from tests.helpers import SvgTestCase


class DiagnosticsAndFallbackTests(SvgTestCase):
    """Exercise embedded fallbacks and structured conversion reports."""

    def test_clip_path_uses_embedded_svg_fallback_and_records_a_report_issue(self) -> None:
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
            xml = converter.convert_to_string(svg_path)
            report = converter.get_report()

        root = ET.fromstring(xml)
        cells = self._user_cells(root)
        self.assertEqual(len(cells), 1)
        styles = self._style_map(cells[0])
        self.assertEqual(styles["shape"], "image")
        self.assertEqual(report.fallback_count, 1)
        self.assertIn("clip-path-fallback", {issue.code for issue in report.issues})
        self.assertTrue(any(asset.status == "embedded-svg-fallback" for asset in report.assets))

    def test_mask_uses_embedded_svg_fallback_and_records_a_report_issue(self) -> None:
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg" width="120" height="80">
          <defs>
            <mask
              id="fade"
              maskUnits="userSpaceOnUse"
              maskContentUnits="userSpaceOnUse"
              x="10"
              y="10"
              width="80"
              height="50"
              style="mask-type:alpha"
            >
              <rect x="10" y="10" width="80" height="50" fill="#ffffff" fill-opacity="1" />
              <circle cx="40" cy="40" r="18" fill="#ffffff" fill-opacity="0" />
            </mask>
          </defs>
          <rect x="10" y="10" width="80" height="50" fill="#00bcd4" mask="url(#fade)" />
        </svg>
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            svg_path = path.join(tmpdir, "mask.svg")
            with open(svg_path, "w", encoding="utf-8") as handle:
                handle.write(svg)

            converter = Converter()
            xml = converter.convert_to_string(svg_path)
            report = converter.get_report()

        root = ET.fromstring(xml)
        cells = self._user_cells(root)
        self.assertEqual(len(cells), 1)
        styles = self._style_map(cells[0])
        self.assertEqual(styles["shape"], "image")
        self.assertEqual(report.fallback_count, 1)
        self.assertIn("mask-fallback", {issue.code for issue in report.issues})
        self.assertTrue(any(asset.status == "embedded-svg-fallback" for asset in report.assets))

    def test_pattern_fill_uses_embedded_svg_fallback_and_records_a_report_issue(self) -> None:
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg" width="120" height="80">
          <defs>
            <pattern id="stripes" width="12" height="12" patternUnits="userSpaceOnUse">
              <rect width="12" height="12" fill="#fff8e1" />
              <path d="M -2 12 L 12 -2 M 4 14 L 14 4" stroke="#fb8c00" stroke-width="3" />
            </pattern>
          </defs>
          <rect x="10" y="10" width="80" height="50" fill="url(#stripes)" stroke="#6d4c41" stroke-width="2" />
        </svg>
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            svg_path = path.join(tmpdir, "pattern.svg")
            with open(svg_path, "w", encoding="utf-8") as handle:
                handle.write(svg)

            converter = Converter()
            xml = converter.convert_to_string(svg_path)
            report = converter.get_report()

        root = ET.fromstring(xml)
        cells = self._user_cells(root)
        self.assertEqual(len(cells), 1)
        styles = self._style_map(cells[0])
        self.assertEqual(styles["shape"], "image")
        self.assertEqual(report.fallback_count, 1)
        self.assertIn("pattern-fallback", {issue.code for issue in report.issues})
        self.assertTrue(any(asset.status == "embedded-svg-fallback" for asset in report.assets))

    def test_multi_stop_gradient_on_complex_path_is_approximated_natively(self) -> None:
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg" width="180" height="120">
          <defs>
            <linearGradient id="multi" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stop-color="#e53935" />
              <stop offset="35%" stop-color="#fb8c00" />
              <stop offset="70%" stop-color="#fdd835" />
              <stop offset="100%" stop-color="#1e88e5" />
            </linearGradient>
          </defs>
          <path
            d="M 20 70 C 30 20 85 10 110 40 C 135 15 165 35 155 72 C 145 102 90 110 60 95 C 35 88 16 88 20 70 Z"
            fill="url(#multi)"
            stroke="#263238"
            stroke-width="2"
          />
        </svg>
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            svg_path = path.join(tmpdir, "complex-gradient.svg")
            with open(svg_path, "w", encoding="utf-8") as handle:
                handle.write(svg)

            converter = Converter()
            xml = converter.convert_to_string(svg_path)
            report = converter.get_report()

        root = ET.fromstring(xml)
        cells = self._user_cells(root)
        # Multi-stop linear gradient on paths is now native: no SVG image fallback
        self.assertFalse(any(self._style_map(cell).get("shape") == "image" for cell in cells))
        self.assertEqual(report.fallback_count, 0)
        self.assertNotIn("multi-stop-gradient-fallback", {issue.code for issue in report.issues})
        # 4 stops → group with 3 gradient bands + 1 stroke overlay
        group = next(cell for cell in cells if cell.get("style") == "group;")
        children = [cell for cell in cells if cell.get("parent") == group.get("id")]
        self.assertGreaterEqual(len(children), 3)
        band_cells = [cell for cell in children if "gradientColor" in self._style_map(cell)]
        self.assertGreaterEqual(len(band_cells), 3)

    def test_svg_fallback_only_embeds_referenced_defs(self) -> None:
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
          <defs>
            <linearGradient id="needed-grad">
              <stop offset="0%" stop-color="#ff0000" />
              <stop offset="100%" stop-color="#0000ff" />
            </linearGradient>
            <linearGradient id="unneeded-grad">
              <stop offset="0%" stop-color="#00ff00" />
              <stop offset="100%" stop-color="#ffffff" />
            </linearGradient>
            <clipPath id="the-clip">
              <rect x="5" y="5" width="40" height="40" />
            </clipPath>
          </defs>
          <rect x="0" y="0" width="50" height="50"
                fill="url(#needed-grad)"
                clip-path="url(#the-clip)" />
        </svg>
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            svg_path = path.join(tmpdir, "slice.svg")
            with open(svg_path, "w", encoding="utf-8") as f:
                f.write(svg)
            converter = Converter()
            xml = converter.convert_to_string(svg_path)

        root = ET.fromstring(xml)
        cells = self._user_cells(root)
        image_cell = next(c for c in cells if self._style_map(c).get("shape") == "image")
        style = image_cell.get("style", "")
        match = re.search(r"data:image/svg\+xml,([^;\"]+)", style)
        self.assertIsNotNone(match)
        assert match is not None
        fallback_svg = unquote(match.group(1))
        self.assertIn("the-clip", fallback_svg)
        self.assertIn("needed-grad", fallback_svg)
        self.assertNotIn("unneeded-grad", fallback_svg)
