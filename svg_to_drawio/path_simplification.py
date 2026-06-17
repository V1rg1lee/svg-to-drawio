"""Ramer-Douglas-Peucker path simplification for draw.io stencil paths."""

from __future__ import annotations

import math

from .path_types import PathCommand, Point2D


def _perp_dist(point: Point2D, start: Point2D, end: Point2D) -> float:
    """Perpendicular distance from *point* to the segment *start*→*end*."""
    x0, y0 = point
    x1, y1 = start
    x2, y2 = end
    dx, dy = x2 - x1, y2 - y1
    sq = dx * dx + dy * dy
    if sq == 0.0:
        return math.hypot(x0 - x1, y0 - y1)
    t = max(0.0, min(1.0, ((x0 - x1) * dx + (y0 - y1) * dy) / sq))
    return math.hypot(x0 - (x1 + t * dx), y0 - (y1 + t * dy))


def _rdp(points: list[Point2D], tolerance: float) -> list[Point2D]:
    """Recursively simplify *points* using the Ramer-Douglas-Peucker algorithm."""
    if len(points) <= 2:
        return list(points)
    max_dist = 0.0
    max_idx = 0
    for i in range(1, len(points) - 1):
        d = _perp_dist(points[i], points[0], points[-1])
        if d > max_dist:
            max_dist = d
            max_idx = i
    if max_dist <= tolerance:
        return [points[0], points[-1]]
    left = _rdp(points[: max_idx + 1], tolerance)
    right = _rdp(points[max_idx:], tolerance)
    return left[:-1] + right


def simplify_path_commands(commands: list[PathCommand], tolerance: float) -> list[PathCommand]:
    """Reduce consecutive ``line`` commands using Ramer-Douglas-Peucker.

    ``curve``, ``move``, and ``close`` commands are emitted unchanged.
    The algorithm groups consecutive line segments and removes intermediate
    points that deviate from the straight chord by less than *tolerance*
    (in the same coordinate space as the command coordinates).
    """
    if tolerance <= 0.0 or not commands:
        return commands

    result: list[PathCommand] = []
    cur: Point2D = (0.0, 0.0)
    line_run: list[Point2D] = []

    def flush_run() -> None:
        if not line_run:
            return
        simplified = _rdp(line_run, tolerance) if len(line_run) >= 3 else line_run
        for pt in simplified[1:]:
            result.append(("line", (pt,)))
        line_run.clear()

    for kind, pts in commands:
        if kind == "move":
            flush_run()
            result.append((kind, pts))
            cur = pts[0]
        elif kind == "line":
            if not line_run:
                line_run.append(cur)
            line_run.append(pts[0])
            cur = pts[0]
        elif kind == "curve":
            flush_run()
            result.append((kind, pts))
            cur = pts[2]  # end-point of the cubic Bézier
        else:  # "close" (no points) and any future commands
            flush_run()
            result.append((kind, pts))

    flush_run()
    return result
