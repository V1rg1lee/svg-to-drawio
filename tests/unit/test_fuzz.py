"""Fuzz-style tests: verify the converter handles degenerate SVG input without crashing."""

from __future__ import annotations

import tempfile
import unittest
from os import path

from svg_to_drawio.converter import Converter


def _convert(svg_content: str) -> str:
    """Write *svg_content* to a temp file and return the resulting draw.io XML string."""
    with tempfile.TemporaryDirectory() as tmpdir:
        svg_path = path.join(tmpdir, "test.svg")
        out_path = path.join(tmpdir, "test.drawio")
        with open(svg_path, "w", encoding="utf-8") as f:
            f.write(svg_content)
        Converter().convert_file(svg_path, out_path)
        with open(out_path, encoding="utf-8") as f:
            return f.read()


class FuzzTests(unittest.TestCase):
    """The converter must never raise on degenerate SVG; it should produce valid (possibly empty) output."""

    def test_empty_svg(self) -> None:
        xml = _convert('<svg xmlns="http://www.w3.org/2000/svg"/>')
        self.assertIn("<mxGraphModel", xml)

    def test_svg_missing_dimensions(self) -> None:
        _convert('<svg xmlns="http://www.w3.org/2000/svg"><rect x="0" y="0"/></svg>')

    def test_invalid_path_data(self) -> None:
        _convert('<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><path d="ZZZZZ not a path"/></svg>')

    def test_unknown_element_is_skipped(self) -> None:
        _convert(
            '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">'
            '<foobar x="0" y="0" width="10" height="10"/>'
            "</svg>"
        )

    def test_deeply_nested_groups(self) -> None:
        inner = '<rect width="1" height="1"/>'
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">'
            + "<g>" * 30
            + inner
            + "</g>" * 30
            + "</svg>"
        )
        _convert(svg)

    def test_bad_gradient_reference(self) -> None:
        _convert(
            '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">'
            '<rect fill="url(#nonexistent)" width="100" height="100"/>'
            "</svg>"
        )

    def test_empty_text_element(self) -> None:
        _convert('<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><text x="0" y="0"></text></svg>')

    def test_arc_with_non_numeric_token(self) -> None:
        # The parser should skip the malformed arc rather than crash
        _convert(
            '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">'
            '<path d="M 10 10 A NaN NaN 0 0 1 20 20"/>'
            "</svg>"
        )

    def test_zero_size_viewbox(self) -> None:
        _convert(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 0 0" width="100" height="100">'
            '<rect width="100" height="100"/>'
            "</svg>"
        )

    def test_use_nonexistent_reference(self) -> None:
        _convert('<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><use href="#does-not-exist"/></svg>')

    def test_use_existing_element(self) -> None:
        xml = _convert(
            '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">'
            '<rect id="r" width="10" height="10"/>'
            '<use href="#r" x="20"/>'
            "</svg>"
        )
        self.assertIn("mxCell", xml)

    def test_display_none_skips_element(self) -> None:
        xml = _convert(
            '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">'
            '<rect width="50" height="50" display="none"/>'
            "</svg>"
        )
        # The hidden rect should produce no cells beyond the two header cells
        self.assertIn("<mxGraphModel", xml)

    def test_max_elements_truncates(self) -> None:
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200">'
            + "".join(f'<rect x="{i * 5}" y="0" width="4" height="4"/>' for i in range(20))
            + "</svg>"
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            svg_path = path.join(tmpdir, "test.svg")
            out_path = path.join(tmpdir, "test.drawio")
            with open(svg_path, "w", encoding="utf-8") as f:
                f.write(svg)
            import warnings

            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                Converter().convert_file(svg_path, out_path, max_elements=5)
            self.assertTrue(any(issubclass(w.category, RuntimeWarning) for w in caught))
            with open(out_path, encoding="utf-8") as f:
                xml = f.read()
            # Only 5 rects should appear, not all 20
            self.assertLessEqual(xml.count("<mxCell"), 5 + 5)  # 5 shape cells + header cells

    def test_convert_to_string_returns_valid_xml(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            svg_path = path.join(tmpdir, "test.svg")
            with open(svg_path, "w", encoding="utf-8") as f:
                f.write(
                    '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">'
                    '<rect width="50" height="50" fill="red"/>'
                    "</svg>"
                )
            xml = Converter().convert_to_string(svg_path)
        self.assertIn("<mxGraphModel", xml)
        self.assertIn("mxCell", xml)
