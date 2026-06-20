"""Unit tests for `Converter`-level behavior not already covered by integration tests."""

from __future__ import annotations

import tempfile
import unittest
from os import path

from svg_to_drawio.converter import Converter
from svg_to_drawio.rendering_options import RenderingOptions

from tests.helpers import SvgTestCase


class NextIdTests(unittest.TestCase):
    """Validate the monotonically increasing cell id generator."""

    def test_next_id_increments_and_reset_restarts_the_sequence(self) -> None:
        converter = Converter()
        self.assertEqual(converter.next_id(), "2")
        self.assertEqual(converter.next_id(), "3")
        converter.reset()
        self.assertEqual(converter.next_id(), "2")


class ConverterStateIsolationTests(unittest.TestCase):
    """A single `Converter` instance must not leak state between independent runs."""

    def test_reusing_one_converter_instance_does_not_leak_cells_or_issues_across_runs(self) -> None:
        converter = Converter()
        first = converter.convert_svg_string_result(
            '<svg xmlns="http://www.w3.org/2000/svg" width="50" height="50"><rect width="10" height="10"/></svg>'
        )
        second = converter.convert_svg_string_result('<svg xmlns="http://www.w3.org/2000/svg" width="50" height="50"/>')
        self.assertIn("mxCell", first.xml)
        self.assertNotIn(first.xml, second.xml)
        self.assertEqual(second.report.emitted_cells, 0)
        self.assertEqual(second.report.issues, [])


class GroupFlattenTests(SvgTestCase):
    """Validate that flatten mode dissolves `<g>` containers instead of nesting cells."""

    def test_flatten_mode_emits_children_without_a_wrapping_group_cell(self) -> None:
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
          <g>
            <rect x="0" y="0" width="10" height="10"/>
            <rect x="20" y="0" width="10" height="10"/>
          </g>
        </svg>
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            svg_path = path.join(tmpdir, "diagram.svg")
            out_path = path.join(tmpdir, "diagram.drawio")
            with open(svg_path, "w", encoding="utf-8") as handle:
                handle.write(svg)
            Converter().convert_file(svg_path, out_path, flatten=True)
            with open(out_path, encoding="utf-8") as handle:
                xml = handle.read()
        self.assertNotIn("group;", xml)
        self.assertEqual(xml.count("<mxCell"), 2 + 2)  # two rects + the two boilerplate root cells


class InkscapeLayerTests(SvgTestCase):
    """Validate that Inkscape-style layer groups become draw.io layer cells."""

    def test_inkscape_layer_group_becomes_a_named_layer_cell(self) -> None:
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape"
             width="100" height="100">
          <g inkscape:groupmode="layer" inkscape:label="Background">
            <rect x="0" y="0" width="10" height="10"/>
          </g>
        </svg>
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            root, _ = self._convert_in_dir(tmpdir, svg)
            layer_cells = [cell for cell in root.findall(".//mxCell") if cell.get("value") == "Background"]
            self.assertEqual(len(layer_cells), 1)
            self.assertEqual(layer_cells[0].get("parent"), "1")


class LinkPropagationTests(SvgTestCase):
    """Validate that an `<a href>` link target reaches every nested drawable child."""

    def test_link_url_propagates_to_all_descendant_shapes(self) -> None:
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
          <a href="https://example.com">
            <rect x="0" y="0" width="10" height="10"/>
            <circle cx="50" cy="50" r="5"/>
          </a>
        </svg>
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            root, _ = self._convert_in_dir(tmpdir, svg)
            cells = self._user_cells(root)
            self.assertEqual(len(cells), 2)
            for cell in cells:
                self.assertIn("link=https://example.com;", cell.get("style", ""))


class AnalyzeOnlyTests(SvgTestCase):
    """Validate that analysis-only runs do not write output but still populate a report."""

    def test_analyze_file_does_not_write_a_drawio_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            svg_path = path.join(tmpdir, "diagram.svg")
            with open(svg_path, "w", encoding="utf-8") as handle:
                handle.write(
                    '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20">'
                    '<rect width="10" height="10"/></svg>'
                )
            report = Converter().analyze_file(svg_path)
            self.assertTrue(report.analyze_only)
            self.assertEqual(report.emitted_cells, 1)
            self.assertFalse(path.exists(path.splitext(svg_path)[0] + ".drawio"))


class RenderingOptionsDefaultTests(unittest.TestCase):
    """Validate that an unset rendering_options argument falls back to engine defaults."""

    def test_missing_rendering_options_defaults_instead_of_raising(self) -> None:
        result = Converter().convert_svg_string_result(
            '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"/>',
            rendering_options=None,
        )
        self.assertEqual(result.report.emitted_cells, 0)
        self.assertIsInstance(Converter().rendering_options, RenderingOptions)


if __name__ == "__main__":
    unittest.main()
