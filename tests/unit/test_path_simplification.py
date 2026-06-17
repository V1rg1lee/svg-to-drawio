"""Unit tests for the Ramer-Douglas-Peucker path simplification module."""

from __future__ import annotations

import unittest

from svg_to_drawio.path_simplification import simplify_path_commands


def _move(x: float, y: float) -> tuple:
    return ("move", ((x, y),))


def _line(x: float, y: float) -> tuple:
    return ("line", ((x, y),))


def _curve(x1: float, y1: float, x2: float, y2: float, x3: float, y3: float) -> tuple:
    return ("curve", ((x1, y1), (x2, y2), (x3, y3)))


def _close() -> tuple:
    return ("close", ())


class PathSimplificationTests(unittest.TestCase):
    """Validate the RDP simplification of SVG path command sequences."""

    def test_empty_commands_returns_empty(self) -> None:
        self.assertEqual(simplify_path_commands([], 1.0), [])

    def test_zero_tolerance_is_identity(self) -> None:
        cmds = [_move(0, 0), _line(10, 0), _line(20, 0), _line(30, 5)]
        self.assertEqual(simplify_path_commands(cmds, 0.0), cmds)

    def test_collinear_middle_points_removed(self) -> None:
        # Points (0,0)→(10,0)→(20,0)→(30,0) are perfectly collinear.
        cmds = [_move(0, 0), _line(10, 0), _line(20, 0), _line(30, 0)]
        result = simplify_path_commands(cmds, 0.5)
        kinds = [k for k, _ in result]
        self.assertEqual(kinds, ["move", "line"])
        self.assertEqual(result[-1][1][0], (30.0, 0.0))

    def test_significant_deviation_preserved(self) -> None:
        # The middle point has 10-unit perpendicular deviation → must be kept.
        cmds = [_move(0, 0), _line(50, 10), _line(100, 0)]
        result = simplify_path_commands(cmds, 0.5)
        self.assertEqual(len(result), 3)  # move + 2 lines kept

    def test_curves_pass_through_unchanged(self) -> None:
        cmds = [_move(0, 0), _curve(10, 5, 20, 5, 30, 0), _line(40, 0), _line(50, 0)]
        result = simplify_path_commands(cmds, 0.5)
        # curve is preserved; the two collinear lines after it are merged to one
        kinds = [k for k, _ in result]
        self.assertIn("curve", kinds)
        self.assertEqual(result[1], _curve(10, 5, 20, 5, 30, 0))

    def test_close_command_preserved(self) -> None:
        cmds = [_move(0, 0), _line(10, 0), _line(20, 0), _close()]
        result = simplify_path_commands(cmds, 0.5)
        self.assertEqual(result[-1][0], "close")

    def test_two_points_never_simplified(self) -> None:
        # A run of exactly two points (start + one line) cannot be simplified further.
        cmds = [_move(0, 0), _line(100, 100)]
        result = simplify_path_commands(cmds, 5.0)
        self.assertEqual(result, cmds)

    def test_staircase_simplification(self) -> None:
        # Alternating horizontal + vertical 1px steps along y=x diagonal.
        # Each individual step deviates from the diagonal, but RDP groups them
        # and the outer envelope stays straight → reduces many points.
        n = 20
        cmds: list[tuple] = [_move(0, 0)]
        for i in range(n):
            cmds.append(_line(i + 1, i))
            cmds.append(_line(i + 1, i + 1))
        result = simplify_path_commands(cmds, 0.5)
        # Fewer total commands than the original
        self.assertLess(len(result), len(cmds))

    def test_move_resets_line_run(self) -> None:
        # Two separate subpaths; collinear simplification should NOT bridge them.
        cmds = [
            _move(0, 0),
            _line(10, 0),
            _line(20, 0),
            _move(100, 0),
            _line(110, 0),
            _line(120, 0),
        ]
        result = simplify_path_commands(cmds, 0.5)
        # Both subpaths simplified to move+line; second move must still be present.
        moves = [k for k, _ in result if k == "move"]
        self.assertEqual(len(moves), 2)
