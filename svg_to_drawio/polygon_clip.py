"""Sutherland–Hodgman polygon clipping for gradient band approximation."""

from __future__ import annotations

from .path_types import PathCommand, Point2D

_BEZIER_SAMPLES = 16  # sample points per cubic Bézier segment when building the polygon


def _bezier(p0: Point2D, p1: Point2D, p2: Point2D, p3: Point2D, t: float) -> Point2D:
    mt = 1.0 - t
    return (
        mt**3 * p0[0] + 3.0 * mt**2 * t * p1[0] + 3.0 * mt * t**2 * p2[0] + t**3 * p3[0],
        mt**3 * p0[1] + 3.0 * mt**2 * t * p1[1] + 3.0 * mt * t**2 * p2[1] + t**3 * p3[1],
    )


def commands_to_polygon(commands: list[PathCommand]) -> list[Point2D]:
    """Flatten path commands to a dense polygon by sampling Bézier curves.

    Handles multi-subpath paths by returning the longest sub-path, which
    corresponds to the main outline for compound shapes.
    """
    subpaths: list[list[Point2D]] = []
    cur: Point2D = (0.0, 0.0)
    current: list[Point2D] = []

    for kind, pts in commands:
        if kind == "move":
            if current:
                subpaths.append(current)
            current = [pts[0]]
            cur = pts[0]
        elif kind == "line":
            current.append(pts[0])
            cur = pts[0]
        elif kind == "curve":
            cp1, cp2, p3 = pts
            for i in range(1, _BEZIER_SAMPLES + 1):
                current.append(_bezier(cur, cp1, cp2, p3, i / _BEZIER_SAMPLES))
            cur = p3
        elif kind == "close":
            if current and current[-1] != current[0]:
                current.append(current[0])
            subpaths.append(current)
            current = []

    if current:
        subpaths.append(current)

    return max(subpaths, key=len) if subpaths else []


def _inside(px: float, py: float, a: float, b: float, c: float) -> bool:
    return a * px + b * py + c >= 0.0


def _intersect(p1: Point2D, p2: Point2D, a: float, b: float, c: float) -> Point2D:
    """Intersection of segment p1→p2 with the boundary line ax+by+c = 0."""
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    t = -(a * p1[0] + b * p1[1] + c) / (a * dx + b * dy)
    return (p1[0] + t * dx, p1[1] + t * dy)


def _clip_halfplane(polygon: list[Point2D], a: float, b: float, c: float) -> list[Point2D]:
    """Sutherland–Hodgman clip of a polygon to the half-plane ax+by+c ≥ 0."""
    if not polygon:
        return []
    result: list[Point2D] = []
    n = len(polygon)
    for i in range(n):
        cur = polygon[i]
        nxt = polygon[(i + 1) % n]
        cur_in = _inside(cur[0], cur[1], a, b, c)
        nxt_in = _inside(nxt[0], nxt[1], a, b, c)
        if cur_in:
            result.append(cur)
        if cur_in != nxt_in:
            result.append(_intersect(cur, nxt, a, b, c))
    return result


def clip_polygon_strip(
    polygon: list[Point2D],
    lo: float,
    hi: float,
    *,
    vertical: bool,
) -> list[Point2D]:
    """Clip a polygon to a vertical (x in [lo, hi]) or horizontal (y in [lo, hi]) strip."""
    if vertical:
        clipped = _clip_halfplane(polygon, 1.0, 0.0, -lo)  # x >= lo
        return _clip_halfplane(clipped, -1.0, 0.0, hi)  # x <= hi
    else:
        clipped = _clip_halfplane(polygon, 0.0, 1.0, -lo)  # y >= lo
        return _clip_halfplane(clipped, 0.0, -1.0, hi)  # y <= hi
