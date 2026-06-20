"""Unit tests for the SVG path tokenizer and command parser (`path_parser.py`)."""

from __future__ import annotations

import unittest
import warnings

from svg_to_drawio.path_parser import path_commands, path_points, sample_open_path, tokenize_path


class TokenizePathTests(unittest.TestCase):
    """Validate the raw token stream produced by `tokenize_path`."""

    def test_none_and_empty_input_produce_no_tokens(self) -> None:
        self.assertEqual(tokenize_path(None), [])
        self.assertEqual(tokenize_path(""), [])

    def test_commands_and_numbers_are_split_without_separators(self) -> None:
        self.assertEqual(tokenize_path("M0,0L10,10"), ["M", "0", "0", "L", "10", "10"])

    def test_concatenated_decimals_are_split_into_separate_numbers(self) -> None:
        # "1.5.5" is valid shorthand for the two numbers 1.5 and .5 sharing one decimal point.
        self.assertEqual(tokenize_path("M1.5.5"), ["M", "1.5", ".5"])

    def test_signed_and_scientific_notation_numbers_are_recognized(self) -> None:
        self.assertEqual(tokenize_path("M-1.5e-3,+2E+2"), ["M", "-1.5e-3", "+2E+2"])


class PathCommandsTests(unittest.TestCase):
    """Validate absolute-resolved command parsing for each SVG path command letter."""

    def test_relative_moveto_lineto_are_resolved_to_absolute_coordinates(self) -> None:
        commands = path_commands("M10,10 l5,5 L20,20")
        self.assertEqual([kind for kind, _ in commands], ["move", "line", "line"])
        self.assertEqual(commands[0][1], ((10.0, 10.0),))
        self.assertEqual(commands[1][1], ((15.0, 15.0),))
        self.assertEqual(commands[2][1], ((20.0, 20.0),))

    def test_horizontal_and_vertical_lineto_only_move_one_axis(self) -> None:
        commands = path_commands("M0,0 H10 V10 h-5 v-5")
        points = [pt for _, (pt,) in commands]
        self.assertEqual(points, [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (5.0, 10.0), (5.0, 5.0)])

    def test_smooth_cubic_reflects_the_previous_control_point(self) -> None:
        # After "C 0 10 10 10 10 0", the reflected control point for "S" is (10, -10).
        commands = path_commands("M0,0 C0,10 10,10 10,0 S20,10 20,0")
        self.assertEqual([kind for kind, _ in commands], ["move", "curve", "curve"])
        first_control_1 = commands[2][1][0]
        self.assertAlmostEqual(first_control_1[0], 10.0, places=6)
        self.assertAlmostEqual(first_control_1[1], -10.0, places=6)

    def test_smooth_cubic_without_a_preceding_cubic_uses_the_current_point(self) -> None:
        commands = path_commands("M5,5 S15,15 20,5")
        control_1 = commands[1][1][0]
        self.assertEqual(control_1, (5.0, 5.0))

    def test_smooth_quadratic_reflects_the_previous_quadratic_control_point(self) -> None:
        commands = path_commands("M0,0 Q10,10 20,0 T40,0")
        self.assertEqual([kind for kind, _ in commands], ["move", "curve", "curve"])
        self.assertAlmostEqual(commands[2][1][-1][0], 40.0, places=6)
        self.assertAlmostEqual(commands[2][1][-1][1], 0.0, places=6)

    def test_closepath_returns_to_the_current_subpath_start(self) -> None:
        commands = path_commands("M0,0 L10,0 L10,10 Z")
        self.assertEqual([kind for kind, _ in commands], ["move", "line", "line", "close"])

    def test_multiple_subpaths_each_close_to_their_own_start(self) -> None:
        commands = path_commands("M0,0 L10,0 Z M5,5 L15,5 Z")
        kinds = [kind for kind, _ in commands]
        self.assertEqual(kinds, ["move", "line", "close", "move", "line", "close"])
        self.assertEqual(commands[-1][0], "close")

    def test_point_transform_is_applied_to_every_emitted_coordinate(self) -> None:
        commands = path_commands("M0,0 L10,0", point_transform=lambda x, y: (x * 2, y + 1))
        self.assertEqual(commands[0][1], ((0.0, 1.0),))
        self.assertEqual(commands[1][1], ((20.0, 1.0),))

    def test_malformed_token_is_skipped_and_emits_a_runtime_warning(self) -> None:
        with self.assertWarnsRegex(RuntimeWarning, "malformed or truncated"):
            commands = path_commands("M0,0 L10")
        # "L10" is truncated (missing its y-coordinate) and dropped, but the preceding
        # move is still emitted rather than the whole path being discarded.
        self.assertEqual([kind for kind, _ in commands], ["move"])

    def test_well_formed_path_does_not_emit_a_warning(self) -> None:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            path_commands("M0,0 L10,10 Z")
        self.assertEqual(caught, [])


class PathPointsAndSamplingTests(unittest.TestCase):
    """Validate the lightweight point-sampling helpers built on top of `_iter_svg_commands`."""

    def test_path_points_yields_endpoints_and_cubic_control_points(self) -> None:
        points = list(path_points("M0,0 L10,0 C10,10 20,10 20,0"))
        self.assertEqual(points[0], (0.0, 0.0))
        self.assertEqual(points[1], (10.0, 0.0))
        self.assertEqual(points[-1], (20.0, 0.0))

    def test_sample_open_path_includes_a_midpoint_for_each_curve(self) -> None:
        points = list(sample_open_path("M0,0 C0,10 10,10 10,0"))
        self.assertEqual(points[0], (0.0, 0.0))
        self.assertEqual(points[-1], (10.0, 0.0))
        # A curve contributes one extra sampled midpoint beyond its start/end.
        self.assertEqual(len(points), 3)


if __name__ == "__main__":
    unittest.main()
