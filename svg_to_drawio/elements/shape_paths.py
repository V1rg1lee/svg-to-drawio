"""Path-building helpers for primitive SVG shapes."""

from __future__ import annotations


def ellipse_path_d(cx: float, cy: float, rx: float, ry: float) -> str:
    """Build path data for an ellipse."""
    return (
        f"M {cx - rx:.6f} {cy:.6f} "
        f"A {rx:.6f} {ry:.6f} 0 1 0 {cx + rx:.6f} {cy:.6f} "
        f"A {rx:.6f} {ry:.6f} 0 1 0 {cx - rx:.6f} {cy:.6f} Z"
    )


def rect_path_d(x: float, y: float, width: float, height: float) -> str:
    """Build path data for a rectangle."""
    return f"M {x:.6f} {y:.6f} H {x + width:.6f} V {y + height:.6f} H {x:.6f} Z"


def rounded_rect_path_d(x: float, y: float, width: float, height: float, rx: float, ry: float) -> str:
    """Build path data for a rounded rectangle."""
    rx = max(0.0, min(rx, width / 2))
    ry = max(0.0, min(ry, height / 2))
    if rx == 0 or ry == 0:
        return rect_path_d(x, y, width, height)
    return (
        f"M {x + rx:.6f} {y:.6f} "
        f"H {x + width - rx:.6f} "
        f"A {rx:.6f} {ry:.6f} 0 0 1 {x + width:.6f} {y + ry:.6f} "
        f"V {y + height - ry:.6f} "
        f"A {rx:.6f} {ry:.6f} 0 0 1 {x + width - rx:.6f} {y + height:.6f} "
        f"H {x + rx:.6f} "
        f"A {rx:.6f} {ry:.6f} 0 0 1 {x:.6f} {y + height - ry:.6f} "
        f"V {y + ry:.6f} "
        f"A {rx:.6f} {ry:.6f} 0 0 1 {x + rx:.6f} {y:.6f} Z"
    )
