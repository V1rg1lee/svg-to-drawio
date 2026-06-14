"""Arc-conversion helpers for SVG path processing."""

from __future__ import annotations

import math

from .path_types import BezierCurve


def arc_to_bezier(
    x1: float,
    y1: float,
    rx: float,
    ry: float,
    phi_deg: float,
    large_arc: int,
    sweep: int,
    x2: float,
    y2: float,
) -> list[BezierCurve]:
    """Convert one SVG arc segment to cubic Bezier segments."""
    if x1 == x2 and y1 == y2:
        return []
    if rx == 0 or ry == 0:
        return [(x1, y1, x2, y2, x2, y2)]

    phi = math.radians(phi_deg % 360)
    cos_phi = math.cos(phi)
    sin_phi = math.sin(phi)

    dx, dy = (x1 - x2) / 2, (y1 - y2) / 2
    x1p = cos_phi * dx + sin_phi * dy
    y1p = -sin_phi * dx + cos_phi * dy

    rx, ry = abs(rx), abs(ry)
    x1p_sq, y1p_sq = x1p * x1p, y1p * y1p
    rx_sq, ry_sq = rx * rx, ry * ry

    lam = x1p_sq / rx_sq + y1p_sq / ry_sq
    if lam > 1:
        lam = math.sqrt(lam)
        rx *= lam
        ry *= lam
        rx_sq = rx * rx
        ry_sq = ry * ry

    num = max(0.0, rx_sq * ry_sq - rx_sq * y1p_sq - ry_sq * x1p_sq)
    den = rx_sq * y1p_sq + ry_sq * x1p_sq
    sq = math.sqrt(num / den) if den else 0.0
    if large_arc == sweep:
        sq = -sq

    cxp = sq * rx * y1p / ry
    cyp = -sq * ry * x1p / rx
    cx = cos_phi * cxp - sin_phi * cyp + (x1 + x2) / 2
    cy = sin_phi * cxp + cos_phi * cyp + (y1 + y2) / 2

    def angle_between(ux: float, uy: float, vx: float, vy: float) -> float:
        length = math.sqrt(ux * ux + uy * uy) * math.sqrt(vx * vx + vy * vy)
        if length == 0:
            return 0.0
        cosine = max(-1.0, min(1.0, (ux * vx + uy * vy) / length))
        angle = math.acos(cosine)
        return -angle if ux * vy - uy * vx < 0 else angle

    theta1 = angle_between(1, 0, (x1p - cxp) / rx, (y1p - cyp) / ry)
    dtheta = angle_between(
        (x1p - cxp) / rx,
        (y1p - cyp) / ry,
        (-x1p - cxp) / rx,
        (-y1p - cyp) / ry,
    )
    if not sweep and dtheta > 0:
        dtheta -= 2 * math.pi
    elif sweep and dtheta < 0:
        dtheta += 2 * math.pi

    segment_count = max(1, int(math.ceil(abs(dtheta) / (math.pi / 2))))
    dt = dtheta / segment_count
    curves: list[BezierCurve] = []
    theta = theta1
    for _ in range(segment_count):
        half = dt / 2
        alpha = math.sin(dt) * (math.sqrt(4 + 3 * math.tan(half) ** 2) - 1) / 3
        cos_theta, sin_theta = math.cos(theta), math.sin(theta)
        cos_next, sin_next = math.cos(theta + dt), math.sin(theta + dt)
        ex = cx + rx * cos_phi * cos_theta - ry * sin_phi * sin_theta
        ey = cy + rx * sin_phi * cos_theta + ry * cos_phi * sin_theta
        fx = cx + rx * cos_phi * cos_next - ry * sin_phi * sin_next
        fy = cy + rx * sin_phi * cos_next + ry * cos_phi * sin_next
        d1x = -rx * cos_phi * sin_theta - ry * sin_phi * cos_theta
        d1y = -rx * sin_phi * sin_theta + ry * cos_phi * cos_theta
        d2x = -rx * cos_phi * sin_next - ry * sin_phi * cos_next
        d2y = -rx * sin_phi * sin_next + ry * cos_phi * cos_next
        curves.append(
            (
                ex + alpha * d1x,
                ey + alpha * d1y,
                fx - alpha * d2x,
                fy - alpha * d2y,
                fx,
                fy,
            )
        )
        theta += dt
    return curves
