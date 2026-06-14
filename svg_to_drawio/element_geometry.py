"""Geometry helpers for converting transformed SVG elements into draw.io bounds."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from .transforms import Matrix, apply_pt, scale_x, scale_y

Point2D = tuple[float, float]


@dataclass(frozen=True)
class BoundsBox:
    """Axis-aligned bounds for an emitted draw.io cell, with optional rotation metadata."""

    x: float
    y: float
    width: float
    height: float
    rotation: float | None = None

    def rotation_if_visible(self, threshold: float = 0.01) -> float | None:
        """Return the stored rotation only when it is large enough to matter visually."""
        if self.rotation is None or abs(self.rotation) <= threshold:
            return None
        return self.rotation

    def has_distinct_axes(self, tolerance: float = 0.02) -> bool:
        """Return whether the box width and height differ beyond a small tolerance."""
        return abs(self.width - self.height) > tolerance


def rotation_deg(matrix: Matrix) -> float:
    """Return the clockwise rotation encoded by an affine matrix."""
    return math.degrees(math.atan2(matrix[1], matrix[0]))


def has_shear(matrix: Matrix) -> bool:
    """Return whether an affine matrix contains a shear component."""
    return abs(matrix[0] * matrix[2] + matrix[1] * matrix[3]) > 1e-6


def line_endpoints(matrix: Matrix, x1: float, y1: float, x2: float, y2: float) -> tuple[Point2D, Point2D]:
    """Transform both endpoints of an SVG line."""
    return apply_pt(matrix, x1, y1), apply_pt(matrix, x2, y2)


def rect_corners(matrix: Matrix, x: float, y: float, width: float, height: float) -> tuple[Point2D, ...]:
    """Return the transformed corners of an axis-aligned SVG rectangle."""
    return (
        apply_pt(matrix, x, y),
        apply_pt(matrix, x + width, y),
        apply_pt(matrix, x + width, y + height),
        apply_pt(matrix, x, y + height),
    )


def bounds_from_points(points: Sequence[Point2D], rotation: float | None = None) -> BoundsBox:
    """Return an axis-aligned bounding box for a sequence of points."""
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    x = min(xs)
    y = min(ys)
    width = max(xs) - x or 1.0
    height = max(ys) - y or 1.0
    return BoundsBox(x=x, y=y, width=width, height=height, rotation=rotation)


def ellipse_bounds(matrix: Matrix, cx: float, cy: float, rx: float, ry: float) -> BoundsBox:
    """Return the transformed bounds of an SVG ellipse when no shear is present."""
    tx, ty = apply_pt(matrix, cx, cy)
    radius_x = rx * scale_x(matrix)
    radius_y = ry * scale_y(matrix)
    return BoundsBox(
        x=tx - radius_x,
        y=ty - radius_y,
        width=radius_x * 2,
        height=radius_y * 2,
        rotation=rotation_deg(matrix),
    )


def rect_bounds(matrix: Matrix, x: float, y: float, width: float, height: float) -> BoundsBox:
    """Return the transformed bounds of an SVG rectangle when no shear is present."""
    tx, ty = apply_pt(matrix, x + width / 2, y + height / 2)
    scaled_width = width * scale_x(matrix)
    scaled_height = height * scale_y(matrix)
    return BoundsBox(
        x=tx - scaled_width / 2,
        y=ty - scaled_height / 2,
        width=scaled_width,
        height=scaled_height,
        rotation=rotation_deg(matrix),
    )


def image_bounds(matrix: Matrix, x: float, y: float, width: float, height: float) -> BoundsBox:
    """Return the transformed bounds of an SVG image, including shear fallbacks."""
    if has_shear(matrix):
        return bounds_from_points(rect_corners(matrix, x, y, width, height))
    return rect_bounds(matrix, x, y, width, height)
