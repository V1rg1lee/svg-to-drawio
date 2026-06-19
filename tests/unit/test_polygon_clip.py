"""Tests for the Sutherland-Hodgman polygon clipping helpers."""

from __future__ import annotations

import unittest

from svg_to_drawio.polygon_clip import _intersect, clip_polygon_strip


class PolygonClipTests(unittest.TestCase):
    def test_intersect_falls_back_to_the_midpoint_for_a_near_zero_denominator(self) -> None:
        # `a * dx + b * dy == 0` here. `_clip_halfplane` only calls `_intersect` when the two
        # endpoints disagree on which side of the line they're on, which can't happen for a
        # truly parallel segment in exact arithmetic - but independent floating-point rounding
        # of each endpoint's evaluation can still make this denominator round to (near) zero.
        # Exercise `_intersect` directly since that exact rounding isn't reliably reproducible
        # end-to-end; the fix is the same either way (no ZeroDivisionError, a sane fallback point).
        point = _intersect((5.0, 0.0), (5.0, 10.0), 1.0, 0.0, -5.0)
        self.assertEqual(point, (5.0, 5.0))

    def test_clip_polygon_strip_clips_a_square_to_a_vertical_band(self) -> None:
        square = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
        clipped = clip_polygon_strip(square, 2.0, 8.0, vertical=True)
        xs = [point[0] for point in clipped]
        self.assertTrue(xs)
        self.assertTrue(all(2.0 - 1e-9 <= x <= 8.0 + 1e-9 for x in xs))
