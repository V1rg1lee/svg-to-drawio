"""Unit tests for style resolution, text handling, and gradients."""

from __future__ import annotations

import tempfile
import xml.etree.ElementTree as ET

from tests.helpers import SvgTestCase


class StyleAndTextTests(SvgTestCase):
    """Validate the main style-resolution and text-emission paths."""

    def test_css_cascade_preserves_order_and_specificity(self) -> None:
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
          <style>.a { stroke: blue; }</style>
          <style>.a { fill: green; } #shape { fill: red; } .b { fill: blue; }</style>
          <rect id="shape" class="a b" x="0" y="0" width="10" height="10" />
        </svg>
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            root, _ = self._convert_in_dir(tmpdir, svg)
            cell = self._user_cells(root)[0]
            style = cell.get("style", "")
            self.assertIn("fillColor=red;", style)
            self.assertIn("strokeColor=blue;", style)

    def test_hidden_elements_are_skipped(self) -> None:
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
          <style>.gone { display: none; }</style>
          <rect class="gone" x="0" y="0" width="10" height="10" />
          <circle cx="20" cy="20" r="5" visibility="hidden" />
        </svg>
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            root, _ = self._convert_in_dir(tmpdir, svg)
            self.assertEqual(self._user_cells(root), [])

    def test_css_variables_and_current_color_are_resolved(self) -> None:
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
          <style>
            :root { --brand-fill: #123abc; }
            rect.theme { fill: var(--brand-fill); stroke: currentColor; }
          </style>
          <g style="color:#112233">
            <rect class="theme" x="0" y="0" width="10" height="10" />
          </g>
        </svg>
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            root, _ = self._convert_in_dir(tmpdir, svg)
            cell = next(cell for cell in self._user_cells(root) if "fillColor=" in cell.get("style", ""))
            styles = self._style_map(cell)
            self.assertEqual(styles["fillColor"], "#123abc")
            self.assertEqual(styles["strokeColor"], "#112233")

    def test_opacity_and_alpha_channels_are_combined(self) -> None:
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
          <rect
            x="0" y="0" width="10" height="10"
            fill="rgba(255,0,0,0.5)"
            stroke="hsla(120,100%,50%,25%)"
            opacity="0.8"
            fill-opacity="0.5"
            stroke-opacity="0.5"
          />
        </svg>
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            root, _ = self._convert_in_dir(tmpdir, svg)
            styles = self._style_map(self._user_cells(root)[0])
            self.assertEqual(styles["fillColor"], "#ff0000")
            self.assertEqual(styles["strokeColor"], "#00ff00")
            self.assertEqual(styles["opacity"], "80")
            self.assertEqual(styles["fillOpacity"], "25")
            self.assertEqual(styles["strokeOpacity"], "12")

    def test_stroke_dasharray_linecap_and_linejoin_are_mapped(self) -> None:
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
          <polyline
            points="0,0 10,10 20,0"
            fill="none"
            stroke="#000"
            stroke-dasharray="5,2"
            stroke-linecap="round"
            stroke-linejoin="bevel"
          />
        </svg>
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            root, _ = self._convert_in_dir(tmpdir, svg)
            styles = self._style_map(self._user_cells(root)[0])
            self.assertEqual(styles["dashed"], "1")
            self.assertEqual(styles["dashPattern"], "5 2")
            self.assertEqual(styles["lineCap"], "round")
            self.assertEqual(styles["lineJoin"], "bevel")

    def test_text_style_baseline_shift_and_tspan_cells_are_emitted(self) -> None:
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
          <text
            x="50"
            y="20"
            font-size="10"
            text-anchor="middle"
            font-weight="bold"
            font-style="italic"
            text-decoration="underline line-through"
            baseline-shift="super"
          >A<tspan fill="red" font-size="20" dx="5">B</tspan></text>
        </svg>
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            root, _ = self._convert_in_dir(tmpdir, svg)
            cells = self._user_cells(root)
            self.assertEqual(len(cells), 2)

            first = next(cell for cell in cells if cell.get("value") == "A")
            second = next(cell for cell in cells if cell.get("value") == "B")

            first_styles = self._style_map(first)
            second_styles = self._style_map(second)
            self.assertEqual(first_styles["align"], "center")
            self.assertEqual(first_styles["fontStyle"], "15")
            self.assertEqual(first_styles["fontSize"], "10.0")
            self.assertAlmostEqual(float(first.find("mxGeometry").get("y")), 8.0, places=2)

            self.assertEqual(second_styles["fontColor"], "red")
            self.assertEqual(second_styles["fontSize"], "20.0")
            self.assertGreater(
                float(second.find("mxGeometry").get("x")),
                float(first.find("mxGeometry").get("x")),
            )

    def test_linear_and_radial_gradients_are_mapped(self) -> None:
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
          <defs>
            <linearGradient id="lg" x1="0" y1="0" x2="1" y2="0" gradientTransform="rotate(90)">
              <stop offset="0" stop-color="#ff0000" />
              <stop offset="1" stop-color="#0000ff" />
            </linearGradient>
            <radialGradient id="rg">
              <stop offset="0" stop-color="#00ff00" />
              <stop offset="1" stop-color="#000000" />
            </radialGradient>
          </defs>
          <rect x="0" y="0" width="10" height="10" fill="url(#lg)" />
          <circle cx="30" cy="30" r="5" fill="url(#rg)" />
        </svg>
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            root, _ = self._convert_in_dir(tmpdir, svg)
            rect_cell, circle_cell = self._user_cells(root)
            rect_styles = self._style_map(rect_cell)
            circle_styles = self._style_map(circle_cell)

            self.assertEqual(rect_styles["fillColor"], "#ff0000")
            self.assertEqual(rect_styles["fillStyle"], "1")
            self.assertEqual(rect_styles["gradientColor"], "#0000ff")
            self.assertEqual(rect_styles["gradientDirection"], "south")

            self.assertEqual(circle_styles["fillColor"], "#00ff00")
            self.assertEqual(circle_styles["gradientColor"], "#000000")
            self.assertEqual(circle_styles["gradientDirection"], "radial")

    def test_fill_rule_evenodd_is_encoded_in_stencil(self) -> None:
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
          <path
            d="M 0 0 H 20 V 20 H 0 Z M 5 5 H 15 V 15 H 5 Z"
            fill="#ff0000"
            stroke="#000000"
            fill-rule="evenodd"
          />
        </svg>
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            root, _ = self._convert_in_dir(tmpdir, svg)
            stencil_xml = self._decode_stencil_xml(self._user_cells(root)[0])
            self.assertIn('fillrule="evenodd"', stencil_xml)

    def test_title_tooltips_and_drop_shadows_are_mapped(self) -> None:
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
          <defs>
            <filter id="shadow">
              <feDropShadow dx="3" dy="4" flood-color="#123456" flood-opacity="0.25" />
            </filter>
          </defs>
          <rect x="0" y="0" width="10" height="10" filter="url(#shadow)">
            <title>Tooltip text</title>
          </rect>
        </svg>
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            root, _ = self._convert_in_dir(tmpdir, svg)
            styles = self._style_map(self._user_cells(root)[0])
            self.assertEqual(styles["tooltip"], "Tooltip text")
            self.assertEqual(styles["shadow"], "1")
            self.assertEqual(styles["shadowColor"], "#123456")
            self.assertEqual(styles["shadowOpacity"], "25")
            self.assertEqual(styles["shadowOffsetX"], "3")
            self.assertEqual(styles["shadowOffsetY"], "4")

    def test_link_with_query_string_produces_valid_drawio_xml(self) -> None:
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg" width="100" height="20">
          <a href="https://example.com/?a=1&amp;b=2">
            <text x="10" y="15">x</text>
          </a>
        </svg>
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            root, out_path = self._convert_in_dir(tmpdir, svg)
            self.assertEqual(root.tag, "mxfile")
            style = self._user_cells(root)[0].get("style", "")
            self.assertIn("link=https://example.com/?a=1&b=2;", style)
            ET.parse(out_path)
