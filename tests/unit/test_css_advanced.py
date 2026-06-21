"""Unit tests for advanced CSS selector and font-size handling."""

from __future__ import annotations

import tempfile
import xml.etree.ElementTree as ET

from svg_to_drawio.css import CssRule, ancestor_info, apply_css, index_css_rules

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

    def test_mermaid_root_id_and_multi_level_descendant_selectors_are_applied(self) -> None:
        svg = """
        <svg id="my-svg" xmlns="http://www.w3.org/2000/svg" width="180" height="120">
          <style>
            #my-svg { font-family: Georgia; font-size: 16px; fill: #333333; }
            #my-svg .node rect { fill: #ECECFF; stroke: #9370DB; stroke-width: 1px; }
            #my-svg .edgePaths .flowchart-link { stroke: #333333; }
            #my-svg .node .label text { text-anchor: middle; }
          </style>
          <g class="root">
            <g class="edgePaths">
              <line class="flowchart-link" x1="20" y1="20" x2="80" y2="20" />
            </g>
            <g class="node" transform="translate(90, 60)">
              <rect x="-40" y="-20" width="80" height="40" />
              <g class="label">
                <rect />
                <text x="0" y="0">Start</text>
              </g>
            </g>
          </g>
        </svg>
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            root, _ = self._convert_in_dir(tmpdir, svg)
            cells = self._user_cells(root)
            node = next(cell for cell in cells if self._style_map(cell).get("fillColor") == "#ECECFF")
            edge = next(cell for cell in cells if cell.get("edge") == "1")
            text = next(cell for cell in cells if cell.get("value") == "Start")

            node_styles = self._style_map(node)
            edge_styles = self._style_map(edge)
            text_styles = self._style_map(text)
            self.assertEqual(node_styles["strokeColor"], "#9370DB")
            self.assertEqual(edge_styles["strokeColor"], "#333333")
            self.assertEqual(text_styles["fontSize"], "16.0")
            self.assertEqual(text_styles["fontFamily"], "Georgia")
            self.assertEqual(text_styles["align"], "center")

            empty_vertices = [
                cell
                for cell in cells
                if cell.get("vertex") == "1" and not cell.get("value") and cell.get("style") != "group;"
            ]
            self.assertEqual(empty_vertices, [node])

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

    def test_rule_index_produces_the_same_cascade_result_as_the_unindexed_scan(self) -> None:
        # A deliberately mixed bucket set: universal, tag, class, id, and a child-combinator
        # rule whose subject is the rightmost simple selector. `circle` is a deliberately
        # irrelevant rule that the index should exclude as a candidate for a <rect>.
        rules = [
            CssRule(selector="*", props={"opacity": "0.5"}, specificity=(0, 0, 0), order=0),
            CssRule(selector="rect", props={"fill": "blue"}, specificity=(0, 0, 1), order=1),
            CssRule(selector=".special", props={"fill": "red"}, specificity=(0, 1, 0), order=2),
            CssRule(selector="#exact", props={"stroke": "black"}, specificity=(1, 0, 0), order=3),
            CssRule(selector="g.theme > rect", props={"fill": "green"}, specificity=(0, 2, 1), order=4),
            CssRule(selector="circle", props={"fill": "yellow"}, specificity=(0, 0, 1), order=5),
        ]
        rule_index = index_css_rules(rules)
        elem = ET.fromstring('<rect id="exact" class="special" />')
        ancestors = [ancestor_info(ET.fromstring('<g class="theme" />'))]

        without_index = apply_css(elem, rules, "rect", ancestors=ancestors)
        with_index = apply_css(elem, rules, "rect", ancestors=ancestors, rule_index=rule_index)

        self.assertEqual(with_index, without_index)
        self.assertEqual(with_index["fill"], "green")
        self.assertEqual(with_index["stroke"], "black")
        self.assertEqual(with_index["opacity"], "0.5")

    def test_root_pseudo_class_variable_is_resolved_but_other_pseudo_classes_are_ignored(self) -> None:
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
          <style>
            :root { --accent: #336699; }
            rect:first-child { fill: red; }
            rect { fill: var(--accent); }
          </style>
          <rect id="a" x="0" y="0" width="10" height="10" />
          <rect id="b" x="20" y="0" width="10" height="10" />
        </svg>
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            root, _ = self._convert_in_dir(tmpdir, svg)
            cells = {cell.get("id"): self._style_map(cell) for cell in self._user_cells(root)}
            fills = {styles["fillColor"] for styles in cells.values()}
            # The unsupported `rect:first-child` rule never matches (rather than
            # mismatching), so both rects fall through to the plain `rect` rule and
            # resolve the `:root`-scoped CSS variable instead of turning red.
            self.assertEqual(fills, {"#336699"})
