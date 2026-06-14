"""Affine transform helpers for SVG coordinate conversion."""

from __future__ import annotations

import math
import re
from xml.etree.ElementTree import Element

from .utils import parse_length

Matrix = list[float]
Point2D = tuple[float, float]

IDENTITY: Matrix = [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]


def mat_mul(left: Matrix, right: Matrix) -> Matrix:
    """Multiply two 2D affine matrices represented as SVG-style six-tuples."""
    return [
        left[0] * right[0] + left[2] * right[1],
        left[1] * right[0] + left[3] * right[1],
        left[0] * right[2] + left[2] * right[3],
        left[1] * right[2] + left[3] * right[3],
        left[0] * right[4] + left[2] * right[5] + left[4],
        left[1] * right[4] + left[3] * right[5] + left[5],
    ]


def apply_pt(matrix: Matrix, x: float, y: float) -> Point2D:
    """Apply a 2D affine matrix to a point."""
    return matrix[0] * x + matrix[2] * y + matrix[4], matrix[1] * x + matrix[3] * y + matrix[5]


def scale_x(matrix: Matrix) -> float:
    """Return the effective horizontal scale factor encoded by a matrix."""
    return math.sqrt(matrix[0] ** 2 + matrix[1] ** 2)


def scale_y(matrix: Matrix) -> float:
    """Return the effective vertical scale factor encoded by a matrix."""
    return math.sqrt(matrix[2] ** 2 + matrix[3] ** 2)


def stroke_scale(matrix: Matrix) -> float:
    """Return a stable scale factor for stroke widths under non-uniform scaling."""
    return math.sqrt(scale_x(matrix) * scale_y(matrix))


def parse_transform(transform: str | None) -> Matrix:
    """Parse an SVG `transform` attribute into a single affine matrix."""
    if not transform:
        return IDENTITY[:]

    result = IDENTITY[:]
    for match in re.finditer(r"(\w+)\(([^)]+)\)", transform):
        function_name = match.group(1)
        numbers = [float(n) for n in re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", match.group(2))]

        if function_name == "translate":
            tx, ty = (numbers + [0.0, 0.0])[:2]
            matrix = [1.0, 0.0, 0.0, 1.0, tx, ty]
        elif function_name == "scale":
            sx = numbers[0] if numbers else 1.0
            sy = numbers[1] if len(numbers) > 1 else sx
            matrix = [sx, 0.0, 0.0, sy, 0.0, 0.0]
        elif function_name == "rotate":
            angle = math.radians(numbers[0]) if numbers else 0.0
            cx, cy = (numbers + [0.0, 0.0, 0.0])[1:3]
            cos_a, sin_a = math.cos(angle), math.sin(angle)
            matrix = [
                cos_a,
                sin_a,
                -sin_a,
                cos_a,
                cx - cx * cos_a + cy * sin_a,
                cy - cx * sin_a - cy * cos_a,
            ]
        elif function_name == "skewX":
            angle = math.radians(numbers[0]) if numbers else 0.0
            matrix = [1.0, 0.0, math.tan(angle), 1.0, 0.0, 0.0]
        elif function_name == "skewY":
            angle = math.radians(numbers[0]) if numbers else 0.0
            matrix = [1.0, math.tan(angle), 0.0, 1.0, 0.0, 0.0]
        elif function_name == "matrix" and len(numbers) >= 6:
            matrix = numbers[:6]
        else:
            continue

        result = mat_mul(result, matrix)
    return result


def viewbox_transform(
    svg_root: Element,
    override_w: float | None = None,
    override_h: float | None = None,
) -> Matrix:
    """Return the matrix that maps an SVG viewBox into viewport pixels.

    The *override_w* and *override_h* parameters are used when a `<symbol>` is rendered
    through `<use width=... height=...>`, where the referenced element's own viewport size
    should be replaced by the dimensions from the `<use>` instance.
    """
    viewbox = svg_root.get("viewBox")
    if not viewbox:
        return IDENTITY[:]

    values = [float(value) for value in re.split(r"[\s,]+", viewbox.strip()) if value]
    if len(values) < 4:
        return IDENTITY[:]

    vb_x, vb_y, vb_w, vb_h = values
    if vb_w == 0 or vb_h == 0:
        return IDENTITY[:]

    if override_w is not None:
        width = override_w
    else:
        width_attr = svg_root.get("width", str(vb_w))
        width = vb_w if str(width_attr).strip().endswith("%") else (parse_length(width_attr) or vb_w)

    if override_h is not None:
        height = override_h
    else:
        height_attr = svg_root.get("height", str(vb_h))
        height = vb_h if str(height_attr).strip().endswith("%") else (parse_length(height_attr) or vb_h)

    scale_width = width / vb_w
    scale_height = height / vb_h

    preserve_aspect_ratio = (svg_root.get("preserveAspectRatio") or "xMidYMid meet").strip().lower()
    if "none" in preserve_aspect_ratio:
        return [scale_width, 0.0, 0.0, scale_height, -vb_x * scale_width, -vb_y * scale_height]

    scale = max(scale_width, scale_height) if "slice" in preserve_aspect_ratio else min(scale_width, scale_height)
    scaled_w = vb_w * scale
    scaled_h = vb_h * scale

    tx = -vb_x * scale + (width - scaled_w) / 2
    if "xmin" in preserve_aspect_ratio:
        tx = -vb_x * scale
    elif "xmax" in preserve_aspect_ratio:
        tx = -vb_x * scale + (width - scaled_w)

    ty = -vb_y * scale + (height - scaled_h) / 2
    if "ymin" in preserve_aspect_ratio:
        ty = -vb_y * scale
    elif "ymax" in preserve_aspect_ratio:
        ty = -vb_y * scale + (height - scaled_h)

    return [scale, 0.0, 0.0, scale, tx, ty]
