"""Helpers for approximating SVG ``<textPath>`` content with editable glyph cells."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

from .path_types import Point2D
from .path_utils import path_commands
from .utils import parse_float, parse_length


@dataclass(frozen=True)
class PathPosition:
    """One point sampled along a path, plus the local tangent angle."""

    x: float
    y: float
    angle_degrees: float


def normal_vector(angle_degrees: float) -> Point2D:
    """Return the local positive-y normal for a tangent angle in degrees."""
    angle_radians = math.radians(angle_degrees)
    return (-math.sin(angle_radians), math.cos(angle_radians))


def _cubic_point(
    p0: Point2D,
    p1: Point2D,
    p2: Point2D,
    p3: Point2D,
    t: float,
) -> Point2D:
    """Return one point on a cubic Bezier curve for parameter ``t``."""
    inv_t = 1.0 - t
    return (
        inv_t**3 * p0[0] + 3.0 * inv_t**2 * t * p1[0] + 3.0 * inv_t * t**2 * p2[0] + t**3 * p3[0],
        inv_t**3 * p0[1] + 3.0 * inv_t**2 * t * p1[1] + 3.0 * inv_t * t**2 * p2[1] + t**3 * p3[1],
    )


def sample_path_polyline(
    path_data: str | None,
    *,
    point_transform: Callable[[float, float], Point2D] | None = None,
    curve_steps: int = 20,
) -> list[Point2D]:
    """Approximate one SVG path as a polyline suitable for textPath layout."""
    commands = path_commands(path_data, point_transform=point_transform)
    points: list[Point2D] = []
    current: Point2D | None = None
    subpath_start: Point2D | None = None

    for command, command_points in commands:
        if command == "move":
            current = command_points[0]
            subpath_start = current
            if not points or points[-1] != current:
                points.append(current)
            continue

        if command == "line":
            current = command_points[0]
            if not points or points[-1] != current:
                points.append(current)
            continue

        if command == "curve":
            if current is None:
                current = command_points[2]
                subpath_start = current
                if not points or points[-1] != current:
                    points.append(current)
                continue

            control_1, control_2, target = command_points
            for step in range(1, max(curve_steps, 1) + 1):
                curve_point = _cubic_point(current, control_1, control_2, target, step / max(curve_steps, 1))
                if not points or points[-1] != curve_point:
                    points.append(curve_point)
            current = target
            continue

        if command == "close" and current is not None and subpath_start is not None and current != subpath_start:
            points.append(subpath_start)
            current = subpath_start

    return points


def polyline_length(points: list[Point2D]) -> float:
    """Return the total Euclidean length of one sampled path polyline."""
    total = 0.0
    for start, end in zip(points, points[1:], strict=False):
        total += math.hypot(end[0] - start[0], end[1] - start[1])
    return total


def point_and_angle_at_distance(points: list[Point2D], distance: float) -> PathPosition | None:
    """Return the interpolated point and tangent angle at one path distance.

    Distances outside the sampled polyline are extrapolated along the first or last
    non-degenerate segment so negative `startOffset` values and overshoots still
    produce sensible editable text placement.
    """
    if not points:
        return None
    if len(points) == 1:
        return PathPosition(points[0][0], points[0][1], 0.0)

    first_non_zero_segment: tuple[Point2D, Point2D] | None = None
    last_non_zero_segment: tuple[Point2D, Point2D] | None = None

    for start, end in zip(points, points[1:], strict=False):
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        segment_length = math.hypot(dx, dy)
        if segment_length <= 1e-9:
            continue

        if first_non_zero_segment is None:
            first_non_zero_segment = (start, end)
        last_non_zero_segment = (start, end)
        if distance < 0.0:
            break

    if distance < 0.0 and first_non_zero_segment is not None:
        start, end = first_non_zero_segment
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        segment_length = math.hypot(dx, dy)
        ratio = distance / segment_length
        return PathPosition(
            start[0] + dx * ratio,
            start[1] + dy * ratio,
            math.degrees(math.atan2(dy, dx)),
        )

    remaining = distance
    for start, end in zip(points, points[1:], strict=False):
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        segment_length = math.hypot(dx, dy)
        if segment_length <= 1e-9:
            continue

        last_non_zero_segment = (start, end)
        if remaining <= segment_length:
            ratio = remaining / segment_length
            return PathPosition(
                start[0] + dx * ratio,
                start[1] + dy * ratio,
                math.degrees(math.atan2(dy, dx)),
            )
        remaining -= segment_length

    if last_non_zero_segment is None:
        return PathPosition(points[-1][0], points[-1][1], 0.0)

    start, end = last_non_zero_segment
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    segment_length = math.hypot(dx, dy)
    if segment_length <= 1e-9:
        return PathPosition(end[0], end[1], 0.0)

    ratio = remaining / segment_length
    return PathPosition(
        end[0] + dx * ratio,
        end[1] + dy * ratio,
        math.degrees(math.atan2(dy, dx)),
    )


def parse_start_offset(value: str | None, total_length: float) -> float:
    """Parse an SVG ``startOffset`` in either absolute units or percent.

    The returned distance intentionally preserves negative values and overshoots so
    callers can decide whether to clamp or extrapolate the layout.
    """
    text = (value or "").strip()
    if not text:
        return 0.0
    if text.endswith("%"):
        return total_length * parse_float(text[:-1], 0.0) / 100.0
    return parse_length(text, 0.0)
