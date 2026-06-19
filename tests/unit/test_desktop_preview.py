"""Regression tests for desktop preview preparation and selector helpers."""

from __future__ import annotations

import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from svg_to_drawio_desktop.preview_selection import (
    preview_combo_index_to_report_index,
    preview_report_index_to_combo_index,
)

try:
    from svg_to_drawio_desktop.preview import _prepare_preview_svg
except ModuleNotFoundError:
    _prepare_preview_svg = None

from tests.helpers import SvgTestCase


@unittest.skipIf(_prepare_preview_svg is None, "PySide6 desktop preview dependencies are not installed")
class DesktopPreviewTests(SvgTestCase):
    """Ensure the Qt preview receives self-contained image references."""

    def test_prepare_preview_svg_embeds_local_svg_and_png_assets(self) -> None:
        fixture = Path("tests/fixtures/test_all_features.svg").resolve()

        preview_path, temp_dir = _prepare_preview_svg(str(fixture))
        self.assertIsNotNone(temp_dir)
        try:
            preview_text = Path(preview_path).read_text(encoding="utf-8")
            root = ET.fromstring(preview_text)
        finally:
            if temp_dir is not None:
                temp_dir.cleanup()

        self.assertIn("data:image/png;base64,", preview_text)
        self.assertNotIn('href="image_asset.svg"', preview_text)
        self.assertNotIn('href="image_asset.png"', preview_text)

        for element in root.iter():
            for value in element.attrib.values():
                self.assertNotIn("hsl(", value)
                self.assertNotIn("hsla(", value)
                self.assertNotIn("var(", value)

        ns = {"svg": "http://www.w3.org/2000/svg"}
        var_box = root.find(".//svg:rect[@x='20'][@y='3840']", ns)
        self.assertIsNotNone(var_box)
        assert var_box is not None
        self.assertEqual(var_box.get("fill"), "#e65100")
        self.assertEqual(var_box.get("stroke"), "#bf360c")

        primary_box = root.find(".//svg:rect[@x='20'][@y='4330']", ns)
        self.assertIsNotNone(primary_box)
        assert primary_box is not None
        self.assertEqual(primary_box.get("fill"), "#e8eaf6")
        self.assertEqual(primary_box.get("stroke"), "#3949ab")

        warm_box = root.find(".//svg:rect[@x='20'][@y='6148']", ns)
        self.assertIsNotNone(warm_box)
        assert warm_box is not None
        self.assertEqual(warm_box.get("fill"), "#e65100")

        inline_var_box = root.find(".//svg:rect[@x='440'][@y='6148']", ns)
        self.assertIsNotNone(inline_var_box)
        assert inline_var_box is not None
        self.assertEqual(inline_var_box.get("fill"), "#6a1b9a")

        self.assertEqual(len(root.findall(".//svg:textPath", ns)), 0)
        self.assertEqual(sum(1 for element in root.iter() if "textLength" in element.attrib), 0)

        stretched_glyphs = [
            text
            for text in root.findall(".//svg:text", ns)
            if text.get("y") == "7682" and text.get("transform") is None and (text.text or "").strip()
        ]
        self.assertEqual(len(stretched_glyphs), len("STRETCHEDLABEL"))

        curved_glyphs = []
        raised_glyphs = []
        dropped_glyphs = []
        for text in root.findall(".//svg:text", ns):
            content = (text.text or "").strip()
            transform = text.get("transform")
            try:
                y_value = float(text.get("y", "0"))
            except ValueError:
                continue
            if transform and 7800.0 <= y_value <= 7855.0:
                curved_glyphs.append(text)
            if transform and y_value < 8002.0 and content:
                raised_glyphs.append(text)
            if transform and y_value > 8002.0 and content:
                dropped_glyphs.append(text)

        self.assertGreaterEqual(len(curved_glyphs), 11)
        self.assertTrue(any(text.get("fill") == "#dc2626" for text in curved_glyphs))
        self.assertTrue(any(text.get("fill") == "#2563eb" for text in curved_glyphs))
        self.assertGreaterEqual(len(raised_glyphs), len("raised"))
        self.assertGreaterEqual(len(dropped_glyphs), len("dropped"))


class PreviewSelectorHelperTests(SvgTestCase):
    """Keep the preview selector's index mapping stable for batch navigation."""

    def test_preview_selector_index_mapping_is_bidirectional(self) -> None:
        self.assertEqual(preview_report_index_to_combo_index(None), 0)
        self.assertEqual(preview_report_index_to_combo_index(0), 1)
        self.assertEqual(preview_report_index_to_combo_index(3), 4)

        self.assertIsNone(preview_combo_index_to_report_index(0))
        self.assertIsNone(preview_combo_index_to_report_index(-5))
        self.assertEqual(preview_combo_index_to_report_index(1), 0)
        self.assertEqual(preview_combo_index_to_report_index(4), 3)
