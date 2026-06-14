"""Bounding-box helpers for parsed SVG path commands."""

from __future__ import annotations

import math
from collections.abc import Iterator, Sequence

from .path_types import PathCommand, Point2D


def _bezier_extremes_t(v0: float, v1: float, v2: float, v3: float) -> Iterator[float]:
    """Yield `t` values in `(0, 1)` where a cubic Bezier derivative reaches zero."""
    a = v1 - v0
    b = v2 - v1
    c = v3 - v2
    qa = a - 2 * b + c
    qb = 2 * (b - a)
    qc = a
    if abs(qa) < 1e-10:
        if abs(qb) > 1e-10:
            t = -qc / qb
            if 0.0 < t < 1.0:
                yield t
    else:
        disc = qb * qb - 4 * qa * qc
        if disc >= 0:
            sq = math.sqrt(disc)
            for sign in (1, -1):
                t = (-qb + sign * sq) / (2 * qa)
                if 0.0 < t < 1.0:
                    yield t


def _bezier_eval(v0: float, v1: float, v2: float, v3: float, t: float) -> float:
    """Evaluate a cubic Bezier component at parameter `t`."""
    return (1 - t) ** 3 * v0 + 3 * (1 - t) ** 2 * t * v1 + 3 * (1 - t) * t**2 * v2 + t**3 * v3


def _bezier_tight_pts(
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    x3: float,
    y3: float,
) -> Iterator[Point2D]:
    """Yield endpoints and visual extrema for a cubic Bezier."""
    yield x0, y0
    yield x3, y3
    ts: set[float] = set()
    for t in _bezier_extremes_t(x0, x1, x2, x3):
        ts.add(t)
    for t in _bezier_extremes_t(y0, y1, y2, y3):
        ts.add(t)
    for t in ts:
        yield _bezier_eval(x0, x1, x2, x3, t), _bezier_eval(y0, y1, y2, y3, t)


def commands_bbox(commands: Sequence[PathCommand]) -> tuple[float, float, float, float] | None:
    """Return a tight bounding box for a parsed path command list."""
    xs: list[float] = []
    ys: list[float] = []
    cur_x, cur_y = 0.0, 0.0
    for kind, points in commands:
        if kind == "move":
            cur_x, cur_y = points[0]
            xs.append(cur_x)
            ys.append(cur_y)
        elif kind == "line":
            cur_x, cur_y = points[0]
            xs.append(cur_x)
            ys.append(cur_y)
        elif kind == "curve":
            (x1, y1), (x2, y2), (x3, y3) = points
            for px, py in _bezier_tight_pts(cur_x, cur_y, x1, y1, x2, y2, x3, y3):
                xs.append(px)
                ys.append(py)
            cur_x, cur_y = x3, y3
    if not xs:
        return None
    bx = min(xs)
    by = min(ys)
    bw = max(xs) - bx
    bh = max(ys) - by
    if bw <= 0:
        bw = 1.0
    if bh <= 0:
        bh = 1.0
    return bx, by, bw, bh
