"""Unit tests for structural SVG features and transform handling."""

from __future__ import annotations

import re
import tempfile

from tests.helpers import SvgTestCase


class StructureAndTransformTests(SvgTestCase):
    """Validate grouping, viewBox transforms, reuse, and path geometry behavior."""

    def test_viewbox_uses_physical_units(self) -> None:
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg" width="10cm" height="10cm" viewBox="0 0 100 100">
          <rect x="0" y="0" width="100" height="100" fill="red" />
        </svg>
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            root, _ = self._convert_in_dir(tmpdir, svg)
            geometry = self._user_cells(root)[0].find("mxGeometry")
            self.assertIsNotNone(geometry)
            self.assertAlmostEqual(float(geometry.get("width")), 377.95, places=1)
            self.assertAlmostEqual(float(geometry.get("height")), 377.95, places=1)

    def test_scaled_paths_scale_stroke_width(self) -> None:
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
          <path d="M 10 10 L 90 10" stroke="red" stroke-width="4" fill="none" transform="scale(2)" />
        </svg>
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            root, _ = self._convert_in_dir(tmpdir, svg)
            style = self._user_cells(root)[0].get("style", "")
            match = re.search(r"strokeWidth=([0-9.]+);", style)
            self.assertIsNotNone(match)
            self.assertAlmostEqual(float(match.group(1)), 8.0, places=2)

    def test_markers_on_open_paths_create_edges_and_midpoint_markers(self) -> None:
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
          <defs>
            <marker id="arrowStart" />
            <marker id="arrowEnd" />
            <marker id="dotMid" />
          </defs>
          <path
            d="M 0 0 C 10 0 20 10 30 10"
            fill="none"
            stroke="#000000"
            marker-start="url(#arrowStart)"
            marker-mid="url(#dotMid)"
            marker-end="url(#arrowEnd)"
          />
        </svg>
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            root, _ = self._convert_in_dir(tmpdir, svg)
            cells = self._user_cells(root)
            self.assertEqual(len(cells), 2)

            edge = next(cell for cell in cells if cell.get("edge") == "1")
            marker = next(
                cell for cell in cells if cell.get("vertex") == "1" and cell.get("style", "").startswith("ellipse;")
            )
            edge_styles = self._style_map(edge)

            self.assertEqual(edge_styles["startArrow"], "block")
            self.assertEqual(edge_styles["endArrow"], "block")
            self.assertEqual(edge_styles["curved"], "1")
            self.assertIsNotNone(edge.find("./mxGeometry/Array"))
            self.assertTrue(marker.get("style", "").startswith("ellipse;fillColor=#000000;"))

    def test_use_and_symbol_elements_are_resolved(self) -> None:
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
          <defs>
            <rect id="baseBox" x="0" y="0" width="10" height="12" fill="red" />
            <symbol id="badge" viewBox="0 0 10 10">
              <rect x="0" y="0" width="10" height="10" fill="blue" />
            </symbol>
          </defs>
          <use href="#baseBox" x="5" y="6" />
          <use href="#badge" x="20" y="30" width="20" height="20" />
        </svg>
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            root, _ = self._convert_in_dir(tmpdir, svg)
            cells = self._user_cells(root)
            self.assertEqual(len(cells), 2)

            first, second = sorted(cells, key=lambda cell: float(cell.find("mxGeometry").get("x")))
            first_geom = first.find("mxGeometry")
            second_geom = second.find("mxGeometry")
            first_styles = self._style_map(first)
            second_styles = self._style_map(second)

            self.assertAlmostEqual(float(first_geom.get("x")), 5.0, places=2)
            self.assertAlmostEqual(float(first_geom.get("y")), 6.0, places=2)
            self.assertAlmostEqual(float(first_geom.get("width")), 10.0, places=2)
            self.assertAlmostEqual(float(first_geom.get("height")), 12.0, places=2)
            self.assertEqual(first_styles["fillColor"], "red")

            self.assertAlmostEqual(float(second_geom.get("x")), 20.0, places=2)
            self.assertAlmostEqual(float(second_geom.get("y")), 30.0, places=2)
            self.assertAlmostEqual(float(second_geom.get("width")), 20.0, places=2)
            self.assertAlmostEqual(float(second_geom.get("height")), 20.0, places=2)
            self.assertEqual(second_styles["fillColor"], "blue")

    def test_nested_svg_preserve_aspect_ratio_none_scales_independently(self) -> None:
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
          <svg width="100" height="50" viewBox="0 0 10 10" preserveAspectRatio="none">
            <rect x="0" y="0" width="10" height="10" fill="red" />
          </svg>
        </svg>
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            root, _ = self._convert_in_dir(tmpdir, svg)
            geometry = self._user_cells(root)[0].find("mxGeometry")
            self.assertAlmostEqual(float(geometry.get("width")), 100.0, places=2)
            self.assertAlmostEqual(float(geometry.get("height")), 50.0, places=2)

    def test_group_cells_use_relative_child_coordinates(self) -> None:
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
          <g transform="translate(10,20)">
            <rect x="5" y="6" width="7" height="8" fill="red" />
          </g>
        </svg>
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            root, _ = self._convert_in_dir(tmpdir, svg)
            cells = self._user_cells(root)
            group = next(cell for cell in cells if cell.get("style") == "group;")
            child = next(cell for cell in cells if cell.get("parent") == group.get("id"))

            group_geom = group.find("mxGeometry")
            child_geom = child.find("mxGeometry")
            self.assertAlmostEqual(float(group_geom.get("x")), 15.0, places=2)
            self.assertAlmostEqual(float(group_geom.get("y")), 26.0, places=2)
            self.assertAlmostEqual(float(group_geom.get("width")), 7.0, places=2)
            self.assertAlmostEqual(float(group_geom.get("height")), 8.0, places=2)

            self.assertAlmostEqual(float(child_geom.get("x")), 0.0, places=2)
            self.assertAlmostEqual(float(child_geom.get("y")), 0.0, places=2)
            self.assertAlmostEqual(float(child_geom.get("width")), 7.0, places=2)
            self.assertAlmostEqual(float(child_geom.get("height")), 8.0, places=2)
