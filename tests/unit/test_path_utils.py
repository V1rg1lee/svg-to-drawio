"""Unit tests for low-level SVG path helpers."""

from __future__ import annotations

import unittest

from svg_to_drawio.path_utils import commands_bbox, path_commands, sample_open_path


class PathUtilsTests(unittest.TestCase):
    """Validate path parsing, curve conversion, and bbox calculations."""

    def test_arc_commands_are_converted_to_curves(self) -> None:
        commands = path_commands("M 0 0 A 10 10 0 0 1 20 0")
        self.assertEqual(commands[0][0], "move")
        self.assertTrue(any(kind == "curve" for kind, _ in commands))
        self.assertEqual(commands[-1][0], "curve")
        self.assertAlmostEqual(commands[-1][1][-1][0], 20.0, places=4)
        self.assertAlmostEqual(commands[-1][1][-1][1], 0.0, places=4)

    def test_curve_bounding_box_uses_visual_extrema_not_control_points(self) -> None:
        commands = path_commands("M 0 0 C 0 10 10 10 10 0")
        bbox = commands_bbox(commands)
        self.assertIsNotNone(bbox)
        x, y, w, h = bbox
        self.assertAlmostEqual(x, 0.0, places=4)
        self.assertAlmostEqual(y, 0.0, places=4)
        self.assertAlmostEqual(w, 10.0, places=4)
        self.assertAlmostEqual(h, 7.5, places=4)

    def test_quadratic_and_smooth_quadratic_commands_become_curves(self) -> None:
        commands = path_commands("M 0 0 Q 10 10 20 0 T 40 0")
        self.assertEqual([kind for kind, _ in commands], ["move", "curve", "curve"])
        self.assertAlmostEqual(commands[1][1][-1][0], 20.0, places=4)
        self.assertAlmostEqual(commands[1][1][-1][1], 0.0, places=4)
        self.assertAlmostEqual(commands[2][1][-1][0], 40.0, places=4)
        self.assertAlmostEqual(commands[2][1][-1][1], 0.0, places=4)

    def test_sample_open_path_returns_on_curve_arc_points(self) -> None:
        points = list(sample_open_path("M 0 0 A 10 10 0 0 1 20 0"))
        self.assertGreaterEqual(len(points), 3)
        self.assertAlmostEqual(points[0][0], 0.0, places=10)
        self.assertAlmostEqual(points[0][1], 0.0, places=10)
        self.assertAlmostEqual(points[-1][0], 20.0, places=10)
        self.assertAlmostEqual(points[-1][1], 0.0, places=10)
        self.assertTrue(any(py < 0 for _, py in points[1:-1]))
