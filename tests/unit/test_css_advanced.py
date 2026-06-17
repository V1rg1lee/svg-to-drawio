"""Unit tests for advanced CSS selector and font-size handling."""

from __future__ import annotations

import tempfile

from tests.helpers import SvgTestCase


class AdvancedCssTests(SvgTestCase):
    """Validate more complex CSS cascade scenarios."""

    def test_descendant_child_and_attribute_selectors_are_applied(self) -> None:
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg" width="120" height="120">
          <style>
            g.theme rect { stroke: #111111; }
            g.theme > rect { fill: #abcdef; }
            rect[data-kind="special"] { stroke-width: 4; }
          </style>
          <g class="theme">
            <rect data-kind="special" x="0" y="0" width="10" height="10" />
            <g>
              <rect x="20" y="0" width="10" height="10" />
            </g>
          </g>
        </svg>
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            root, _ = self._convert_in_dir(tmpdir, svg)
            cells = [cell for cell in self._user_cells(root) if "fillColor=" in cell.get("style", "")]
            left, right = sorted(cells, key=lambda cell: float(cell.find("mxGeometry").get("x")))

            left_styles = self._style_map(left)
            right_styles = self._style_map(right)

            self.assertEqual(left_styles["fillColor"], "#abcdef")
            self.assertEqual(left_styles["strokeColor"], "#111111")
            self.assertEqual(left_styles["strokeWidth"], "4.0")

            self.assertEqual(right_styles["fillColor"], "none")
            self.assertEqual(right_styles["strokeColor"], "#111111")
            self.assertEqual(right_styles["strokeWidth"], "1.0")

    def test_font_size_relative_units_are_resolved_from_css(self) -> None:
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg" width="200" height="200">
          <style>
            g.parent { font-size: 20px; }
            text.percent { font-size: 150%; }
            text.em { font-size: 2em; }
            text.rem { font-size: 1.5rem; }
          </style>
          <g class="parent">
            <text class="percent" x="10" y="20">P</text>
            <text class="em" x="10" y="50">E</text>
            <text class="rem" x="10" y="90">R</text>
          </g>
        </svg>
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            root, _ = self._convert_in_dir(tmpdir, svg)
            cells = {
                cell.get("value"): self._style_map(cell)
                for cell in self._user_cells(root)
                if cell.get("value") in {"P", "E", "R"}
            }
            self.assertEqual(cells["P"]["fontSize"], "30.0")
            self.assertEqual(cells["E"]["fontSize"], "40.0")
            self.assertEqual(cells["R"]["fontSize"], "24.0")

    def test_css_variables_scoped_to_class_rule_are_resolved(self) -> None:
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
          <style>
            .brand { --brand-color: #aabbcc; fill: var(--brand-color); }
            .alt   { --brand-color: #112233; stroke: var(--brand-color); }
          </style>
          <rect class="brand" x="0" y="0" width="10" height="10" />
          <rect class="alt" x="20" y="0" width="10" height="10" />
        </svg>
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            root, _ = self._convert_in_dir(tmpdir, svg)
            cells = {
                (int(float(cell.find("mxGeometry").get("x")))): self._style_map(cell)
                for cell in self._user_cells(root)
                if "fillColor=" in cell.get("style", "") or "strokeColor=" in cell.get("style", "")
            }
            self.assertEqual(cells[0]["fillColor"], "#aabbcc")
            self.assertEqual(cells[20]["strokeColor"], "#112233")

    def test_css_variable_defined_on_id_rule_is_resolved(self) -> None:
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
          <style>
            #box { --accent: #fedcba; fill: var(--accent); }
          </style>
          <rect id="box" x="0" y="0" width="10" height="10" />
        </svg>
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            root, _ = self._convert_in_dir(tmpdir, svg)
            cell = next(c for c in self._user_cells(root) if "fillColor=" in c.get("style", ""))
            self.assertEqual(self._style_map(cell)["fillColor"], "#fedcba")
