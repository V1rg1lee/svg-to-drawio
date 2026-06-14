"""SVG path tokenization and command parsing helpers."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator

from .path_arcs import arc_to_bezier
from .path_types import PathCommand, Point2D


def tokenize_path(path_data: str | None) -> list[str]:
    """Split an SVG path string into command and numeric tokens."""
    return re.findall(
        r"[MmLlHhVvCcSsQqTtAaZz]|[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?",
        path_data or "",
    )


_CMD_CHARS = frozenset("MmLlHhVvCcSsQqTtAaZz")


def _iter_svg_commands(path_data: str | None) -> Iterator[tuple]:
    """Parse SVG path data into absolute resolved commands.

    Yields tuples of:
      ('move', x, y)
      ('line', x, y)
      ('cubic', x1, y1, x2, y2, x3, y3)  -- S/s, Q/q, T/t all converted to cubic
      ('close', sx, sy)                    -- subpath-start coordinates included

    All coordinates are absolute. Arc commands are converted to cubics via
    `arc_to_bezier`. Malformed tokens are skipped via (IndexError, ValueError).
    """
    tokens = tokenize_path(path_data)
    i, cx, cy = 0, 0.0, 0.0
    sx, sy = 0.0, 0.0
    last_cubic_cp: tuple[float, float] | None = None  # reflected by S/s
    last_quad_cp: tuple[float, float] | None = None  # reflected by T/t

    while i < len(tokens):
        token = tokens[i]
        if token not in _CMD_CHARS:
            i += 1
            continue
        cmd, i = token, i + 1

        if cmd in "Zz":
            yield ("close", sx, sy)
            cx, cy = sx, sy
            last_cubic_cp = last_quad_cp = None
            continue

        while i < len(tokens) and tokens[i] not in _CMD_CHARS:
            try:
                if cmd in "Mm":
                    nx, ny = float(tokens[i]), float(tokens[i + 1])
                    if cmd == "m":
                        nx += cx
                        ny += cy
                    cx, cy = nx, ny
                    sx, sy = cx, cy
                    yield ("move", cx, cy)
                    cmd = "L" if cmd == "M" else "l"
                    last_cubic_cp = last_quad_cp = None
                    i += 2
                elif cmd in "Ll":
                    nx, ny = float(tokens[i]), float(tokens[i + 1])
                    if cmd == "l":
                        nx += cx
                        ny += cy
                    cx, cy = nx, ny
                    yield ("line", cx, cy)
                    last_cubic_cp = last_quad_cp = None
                    i += 2
                elif cmd in "Hh":
                    nx = float(tokens[i])
                    if cmd == "h":
                        nx += cx
                    cx = nx
                    yield ("line", cx, cy)
                    last_cubic_cp = last_quad_cp = None
                    i += 1
                elif cmd in "Vv":
                    ny = float(tokens[i])
                    if cmd == "v":
                        ny += cy
                    cy = ny
                    yield ("line", cx, cy)
                    last_cubic_cp = last_quad_cp = None
                    i += 1
                elif cmd in "Cc":
                    base_x = cx if cmd == "c" else 0.0
                    base_y = cy if cmd == "c" else 0.0
                    x1 = base_x + float(tokens[i])
                    y1 = base_y + float(tokens[i + 1])
                    x2 = base_x + float(tokens[i + 2])
                    y2 = base_y + float(tokens[i + 3])
                    x3 = base_x + float(tokens[i + 4])
                    y3 = base_y + float(tokens[i + 5])
                    yield ("cubic", x1, y1, x2, y2, x3, y3)
                    last_cubic_cp = (x2, y2)
                    last_quad_cp = None
                    cx, cy = x3, y3
                    i += 6
                elif cmd in "Ss":
                    base_x = cx if cmd == "s" else 0.0
                    base_y = cy if cmd == "s" else 0.0
                    rx1 = 2 * cx - last_cubic_cp[0] if last_cubic_cp is not None else cx
                    ry1 = 2 * cy - last_cubic_cp[1] if last_cubic_cp is not None else cy
                    x2 = base_x + float(tokens[i])
                    y2 = base_y + float(tokens[i + 1])
                    x3 = base_x + float(tokens[i + 2])
                    y3 = base_y + float(tokens[i + 3])
                    yield ("cubic", rx1, ry1, x2, y2, x3, y3)
                    last_cubic_cp = (x2, y2)
                    last_quad_cp = None
                    cx, cy = x3, y3
                    i += 4
                elif cmd in "Qq":
                    base_x = cx if cmd == "q" else 0.0
                    base_y = cy if cmd == "q" else 0.0
                    qx1 = base_x + float(tokens[i])
                    qy1 = base_y + float(tokens[i + 1])
                    x3 = base_x + float(tokens[i + 2])
                    y3 = base_y + float(tokens[i + 3])
                    yield (
                        "cubic",
                        cx + 2 / 3 * (qx1 - cx),
                        cy + 2 / 3 * (qy1 - cy),
                        x3 + 2 / 3 * (qx1 - x3),
                        y3 + 2 / 3 * (qy1 - y3),
                        x3,
                        y3,
                    )
                    last_quad_cp = (qx1, qy1)
                    last_cubic_cp = None
                    cx, cy = x3, y3
                    i += 4
                elif cmd in "Tt":
                    base_x = cx if cmd == "t" else 0.0
                    base_y = cy if cmd == "t" else 0.0
                    qx1 = 2 * cx - last_quad_cp[0] if last_quad_cp is not None else cx
                    qy1 = 2 * cy - last_quad_cp[1] if last_quad_cp is not None else cy
                    x3 = base_x + float(tokens[i])
                    y3 = base_y + float(tokens[i + 1])
                    yield (
                        "cubic",
                        cx + 2 / 3 * (qx1 - cx),
                        cy + 2 / 3 * (qy1 - cy),
                        x3 + 2 / 3 * (qx1 - x3),
                        y3 + 2 / 3 * (qy1 - y3),
                        x3,
                        y3,
                    )
                    last_quad_cp = (qx1, qy1)
                    last_cubic_cp = None
                    cx, cy = x3, y3
                    i += 2
                elif cmd in "Aa" and i + 6 < len(tokens):
                    rx_a = abs(float(tokens[i]))
                    ry_a = abs(float(tokens[i + 1]))
                    phi_a = float(tokens[i + 2])
                    large_arc = int(float(tokens[i + 3]))
                    sweep = int(float(tokens[i + 4]))
                    if cmd == "A":
                        nx, ny = float(tokens[i + 5]), float(tokens[i + 6])
                    else:
                        nx, ny = cx + float(tokens[i + 5]), cy + float(tokens[i + 6])
                    for curve in arc_to_bezier(cx, cy, rx_a, ry_a, phi_a, large_arc, sweep, nx, ny):
                        yield ("cubic", curve[0], curve[1], curve[2], curve[3], curve[4], curve[5])
                    last_cubic_cp = last_quad_cp = None
                    cx, cy = nx, ny
                    i += 7
                else:
                    i += 1
            except (IndexError, ValueError):
                i += 1


def path_points(path_data: str | None) -> Iterator[Point2D]:
    """Yield approximate key points from SVG path data for lightweight checks."""
    for cmd in _iter_svg_commands(path_data):
        if cmd[0] in ("move", "line"):
            yield cmd[1], cmd[2]
        elif cmd[0] == "cubic":
            yield cmd[1], cmd[2]
            yield cmd[3], cmd[4]
            yield cmd[5], cmd[6]


def sample_open_path(path_data: str | None) -> Iterator[Point2D]:
    """Yield on-curve points from an open path for draw.io edge waypoints."""

    def cubic_mid(
        x0: float,
        y0: float,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        x3: float,
        y3: float,
    ) -> Point2D:
        return (
            0.125 * x0 + 0.375 * x1 + 0.375 * x2 + 0.125 * x3,
            0.125 * y0 + 0.375 * y1 + 0.375 * y2 + 0.125 * y3,
        )

    cx, cy = 0.0, 0.0
    for cmd in _iter_svg_commands(path_data):
        if cmd[0] == "move":
            cx, cy = cmd[1], cmd[2]
            yield cx, cy
        elif cmd[0] == "line":
            cx, cy = cmd[1], cmd[2]
            yield cx, cy
        elif cmd[0] == "cubic":
            x1, y1, x2, y2, x3, y3 = cmd[1], cmd[2], cmd[3], cmd[4], cmd[5], cmd[6]
            yield cubic_mid(cx, cy, x1, y1, x2, y2, x3, y3)
            cx, cy = x3, y3
            yield cx, cy
        elif cmd[0] == "close":
            cx, cy = cmd[1], cmd[2]


def path_commands(
    path_data: str | None,
    point_transform: Callable[[float, float], Point2D] | None = None,
) -> list[PathCommand]:
    """Parse SVG path data into absolute draw.io-style commands."""

    def tp(x: float, y: float) -> Point2D:
        return point_transform(x, y) if point_transform else (x, y)

    commands: list[PathCommand] = []
    for cmd in _iter_svg_commands(path_data):
        if cmd[0] == "move":
            commands.append(("move", (tp(cmd[1], cmd[2]),)))
        elif cmd[0] == "line":
            commands.append(("line", (tp(cmd[1], cmd[2]),)))
        elif cmd[0] == "cubic":
            commands.append(
                (
                    "curve",
                    (tp(cmd[1], cmd[2]), tp(cmd[3], cmd[4]), tp(cmd[5], cmd[6])),
                )
            )
        elif cmd[0] == "close":
            commands.append(("close", ()))
    return commands
