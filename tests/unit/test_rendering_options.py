"""Tests for advanced rendering policies shared across the engine surfaces."""

from __future__ import annotations

import dataclasses
import tempfile
import xml.etree.ElementTree as ET
from os import path
from unittest.mock import patch

from svg_to_drawio.converter import Converter
from svg_to_drawio.rendering_options import RenderingOptions
from svg_to_drawio.text_metrics import _heuristic_metrics, measure_text

from tests.helpers import SvgTestCase


class RenderingOptionsTests(SvgTestCase):
    """Exercise the editability-vs-fidelity rendering policies."""

    def test_to_dict_covers_every_field_so_the_conversion_cache_key_cannot_go_stale(self) -> None:
        # ConversionService derives its persistent-cache invalidation key from
        # RenderingOptions.to_dict() (see conversion_service.py::_options_signature). If a
        # future field were added to this dataclass without updating to_dict(), the cache
        # would keep serving stale results for runs that only differ by that new field.
        field_names = {f.name for f in dataclasses.fields(RenderingOptions)}
        self.assertEqual(field_names, set(RenderingOptions().to_dict().keys()))

    def test_prefer_fallback_forces_multi_stop_gradient_into_svg_image(self) -> None:
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg" width="160" height="100">
          <defs>
            <linearGradient id="multi" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stop-color="#e53935" />
              <stop offset="35%" stop-color="#fb8c00" />
              <stop offset="70%" stop-color="#fdd835" />
              <stop offset="100%" stop-color="#1e88e5" />
            </linearGradient>
          </defs>
          <rect x="10" y="15" width="120" height="50" rx="12" fill="url(#multi)" stroke="#263238" stroke-width="2" />
        </svg>
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            svg_path = path.join(tmpdir, "prefer-fallback.svg")
            with open(svg_path, "w", encoding="utf-8") as handle:
                handle.write(svg)

            converter = Converter()
            xml = converter.convert_to_string(
                svg_path,
                rendering_options=RenderingOptions(gradient_policy="prefer-fallback"),
            )
            report = converter.get_report()

        root = ET.fromstring(xml)
        cells = self._user_cells(root)
        self.assertTrue(any(self._style_map(cell).get("shape") == "image" for cell in cells))
        self.assertEqual(report.fallback_count, 1)
        self.assertIn("multi-stop-gradient-fallback", {issue.code for issue in report.issues})

    def test_prefer_native_reduces_complex_multi_stop_gradient_without_svg_fallback(self) -> None:
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg" width="180" height="120">
          <defs>
            <radialGradient id="multi">
              <stop offset="0%" stop-color="#e53935" />
              <stop offset="35%" stop-color="#fb8c00" />
              <stop offset="70%" stop-color="#fdd835" />
              <stop offset="100%" stop-color="#1e88e5" />
            </radialGradient>
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
            svg_path = path.join(tmpdir, "prefer-native.svg")
            with open(svg_path, "w", encoding="utf-8") as handle:
                handle.write(svg)

            converter = Converter()
            xml = converter.convert_to_string(
                svg_path,
                rendering_options=RenderingOptions(gradient_policy="prefer-native"),
            )
            report = converter.get_report()

        root = ET.fromstring(xml)
        cells = self._user_cells(root)
        self.assertFalse(any(self._style_map(cell).get("shape") == "image" for cell in cells))
        self.assertTrue(any("gradientColor" in self._style_map(cell) for cell in cells))
        self.assertEqual(report.fallback_count, 0)
        self.assertIn("multi-stop-gradient-reduced", {issue.code for issue in report.issues})

    def test_prefer_native_filter_keeps_native_shape_and_reports_filter_drop(self) -> None:
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg" width="120" height="80">
          <defs>
            <filter id="blur">
              <feGaussianBlur stdDeviation="8" />
            </filter>
          </defs>
          <rect x="10" y="10" width="80" height="50" fill="#00bcd4" filter="url(#blur)" />
        </svg>
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            svg_path = path.join(tmpdir, "filter-native.svg")
            with open(svg_path, "w", encoding="utf-8") as handle:
                handle.write(svg)

            converter = Converter()
            xml = converter.convert_to_string(
                svg_path,
                rendering_options=RenderingOptions(filter_policy="prefer-native"),
            )
            report = converter.get_report()

        root = ET.fromstring(xml)
        cells = self._user_cells(root)
        self.assertFalse(any(self._style_map(cell).get("shape") == "image" for cell in cells))
        self.assertEqual(report.fallback_count, 0)
        self.assertIn("filter-ignored-for-editability", {issue.code for issue in report.issues})

    def test_subtree_bounds_estimation_is_cached_for_repeated_policy_notes_on_one_element(self) -> None:
        # A single element with both an ignored filter and a reduced gradient triggers two
        # separate policy-note annotations in _record_policy_notes, each of which previously
        # re-ran a full flatten-mode emit-and-discard pass just to estimate the same bbox.
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg" width="180" height="120">
          <defs>
            <filter id="blur"><feGaussianBlur stdDeviation="8" /></filter>
            <radialGradient id="multi">
              <stop offset="0%" stop-color="#e53935" />
              <stop offset="35%" stop-color="#fb8c00" />
              <stop offset="70%" stop-color="#fdd835" />
              <stop offset="100%" stop-color="#1e88e5" />
            </radialGradient>
          </defs>
          <path
            d="M 20 70 C 30 20 85 10 110 40 C 135 15 165 35 155 72 C 145 102 90 110 60 95 C 35 88 16 88 20 70 Z"
            fill="url(#multi)"
            filter="url(#blur)"
            stroke="#263238"
            stroke-width="2"
          />
        </svg>
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            svg_path = path.join(tmpdir, "double-policy-note.svg")
            with open(svg_path, "w", encoding="utf-8") as handle:
                handle.write(svg)

            converter = Converter()
            with patch.object(
                Converter, "_compute_subtree_bounds", wraps=converter._compute_subtree_bounds, autospec=False
            ) as compute_spy:
                converter.convert_to_string(
                    svg_path,
                    rendering_options=RenderingOptions(filter_policy="prefer-native", gradient_policy="prefer-native"),
                )
            report = converter.get_report()

        issue_codes = {issue.code for issue in report.issues}
        self.assertIn("filter-ignored-for-editability", issue_codes)
        self.assertIn("multi-stop-gradient-reduced", issue_codes)
        self.assertEqual(compute_spy.call_count, 1)

    def test_light_blur_filter_uses_svg_fallback_in_auto_mode(self) -> None:
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg" width="120" height="80">
          <defs>
            <filter id="blur">
              <feGaussianBlur stdDeviation="3" />
            </filter>
          </defs>
          <rect x="10" y="10" width="80" height="50" fill="#00bcd4" filter="url(#blur)" />
        </svg>
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            svg_path = path.join(tmpdir, "filter-auto.svg")
            with open(svg_path, "w", encoding="utf-8") as handle:
                handle.write(svg)

            converter = Converter()
            xml = converter.convert_to_string(svg_path, rendering_options=RenderingOptions())
            report = converter.get_report()

        root = ET.fromstring(xml)
        cells = self._user_cells(root)
        self.assertTrue(any(self._style_map(cell).get("shape") == "image" for cell in cells))
        self.assertEqual(report.fallback_count, 1)
        self.assertIn("filter-fallback", {issue.code for issue in report.issues})

    def test_force_fallback_filter_wraps_supported_shadow_in_embedded_svg(self) -> None:
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg" width="120" height="80">
          <defs>
            <filter id="shadow">
              <feDropShadow dx="3" dy="4" flood-color="#123456" flood-opacity="0.25" />
            </filter>
          </defs>
          <rect x="10" y="10" width="80" height="50" fill="#00bcd4" filter="url(#shadow)" />
        </svg>
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            svg_path = path.join(tmpdir, "filter-fallback.svg")
            with open(svg_path, "w", encoding="utf-8") as handle:
                handle.write(svg)

            converter = Converter()
            xml = converter.convert_to_string(
                svg_path,
                rendering_options=RenderingOptions(filter_policy="force-fallback"),
            )
            report = converter.get_report()

        root = ET.fromstring(xml)
        cells = self._user_cells(root)
        self.assertTrue(any(self._style_map(cell).get("shape") == "image" for cell in cells))
        self.assertEqual(report.fallback_count, 1)
        self.assertIn("filter-fallback", {issue.code for issue in report.issues})

    def test_heuristic_text_metrics_policy_skips_system_backend(self) -> None:
        expected = _heuristic_metrics("Hello", 12, bold=False, italic=False)
        with patch("svg_to_drawio.text_metrics._get_tk_root", side_effect=AssertionError("unexpected Tk lookup")):
            self.assertEqual(measure_text("Hello", 12, "Helvetica", policy="heuristic"), expected)
