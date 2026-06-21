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

    def test_malformed_viewbox_falls_back_to_identity_instead_of_crashing(self) -> None:
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg" width="50" height="50" viewBox="0 0 abc 50">
          <rect x="0" y="0" width="50" height="50" fill="red" />
        </svg>
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            root, _ = self._convert_in_dir(tmpdir, svg)
            geometry = self._user_cells(root)[0].find("mxGeometry")
            self.assertIsNotNone(geometry)
            self.assertAlmostEqual(float(geometry.get("width")), 50.0, places=1)
            self.assertAlmostEqual(float(geometry.get("height")), 50.0, places=1)

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

    def test_mermaid_triangle_marker_becomes_filled_arrow_and_preserves_tip_overhang(self) -> None:
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg" width="120" height="60">
          <defs>
            <marker
              id="flowchart-v2-pointEnd"
              viewBox="0 0 10 10"
              refX="5"
              refY="5"
              markerUnits="userSpaceOnUse"
              markerWidth="8"
              markerHeight="8"
              orient="auto"
            >
              <path d="M 0 0 L 10 5 L 0 10 z" />
            </marker>
          </defs>
          <path
            d="M 10 30 L 90 30"
            fill="none"
            stroke="#333333"
            marker-end="url(#flowchart-v2-pointEnd)"
          />
        </svg>
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            root, _ = self._convert_in_dir(tmpdir, svg)
            edge = next(cell for cell in self._user_cells(root) if cell.get("edge") == "1")
            styles = self._style_map(edge)
            target = edge.find("./mxGeometry/mxPoint[@as='targetPoint']")
            self.assertIsNotNone(target)
            assert target is not None

            self.assertEqual(styles["endArrow"], "block")
            self.assertEqual(styles["endFill"], "1")
            self.assertAlmostEqual(float(target.get("x", "0")), 94.0, places=2)
            self.assertAlmostEqual(float(target.get("y", "0")), 30.0, places=2)

    def test_simple_custom_markers_emit_endpoint_shapes(self) -> None:
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg" width="120" height="80">
          <defs>
            <marker id="custom-start">
              <polygon points="0,4 8,0 8,8" />
            </marker>
            <marker id="custom-end">
              <rect x="0" y="0" width="8" height="8" />
            </marker>
          </defs>
          <line
            x1="10"
            y1="20"
            x2="90"
            y2="20"
            stroke="#000000"
            stroke-width="2"
            marker-start="url(#custom-start)"
            marker-end="url(#custom-end)"
          />
        </svg>
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            root, _ = self._convert_in_dir(tmpdir, svg)
            cells = self._user_cells(root)
            self.assertEqual(len(cells), 3)

            edge = next(cell for cell in cells if cell.get("edge") == "1")
            endpoint_shapes = [cell for cell in cells if cell.get("vertex") == "1"]
            self.assertEqual(self._style_map(edge).get("startArrow"), "none")
            self.assertEqual(self._style_map(edge).get("endArrow"), "none")
            self.assertEqual(len(endpoint_shapes), 2)
            styles = [self._style_map(cell) for cell in endpoint_shapes]
            self.assertTrue(any(style.get("shape") == "triangle" for style in styles))
            self.assertTrue(any(style.get("rounded") == "0" for style in styles))

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

    def test_mermaid_node_accumulates_nested_group_translations(self) -> None:
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg" width="180" height="100">
          <style>
            .label-container { fill: #eeeeee; stroke: #333333; }
            .text-inner-tspan { fill: #dc2626; font-weight: bold; }
          </style>
          <g transform="translate(48.5, 16)">
            <rect class="basic label-container" x="-47.5" y="-23" width="95" height="46" />
            <g class="label" transform="translate(0, -8)">
              <text x="0" y="0">
                <tspan class="text-outer-tspan"><tspan class="text-inner-tspan">Start</tspan></tspan>
              </text>
            </g>
          </g>
        </svg>
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            root, _ = self._convert_in_dir(tmpdir, svg)
            cells = self._user_cells(root)
            rect = next(cell for cell in cells if self._style_map(cell).get("fillColor") == "#eeeeee")
            text = next(cell for cell in cells if cell.get("value") == "Start")
            rect_geometry = rect.find("mxGeometry")
            self.assertIsNotNone(rect_geometry)
            assert rect_geometry is not None

            rect_x, rect_y = self._absolute_cell_position(root, rect)
            text_x, text_y = self._absolute_cell_position(root, text)
            self.assertAlmostEqual(rect_x, 1.0, places=2)
            self.assertAlmostEqual(rect_y, -7.0, places=2)
            self.assertAlmostEqual(float(rect_geometry.get("width", "0")), 95.0, places=2)
            self.assertAlmostEqual(float(rect_geometry.get("height", "0")), 46.0, places=2)
            self.assertAlmostEqual(text_x, 48.5, places=2)
            self.assertLess(text_y, 8.0)
            self.assertGreater(text_y, -10.0)
