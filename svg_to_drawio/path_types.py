"""Shared type aliases for SVG path parsing and serialization."""

from __future__ import annotations

Point2D = tuple[float, float]
BezierCurve = tuple[float, float, float, float, float, float]
PathCommand = tuple[str, tuple[Point2D, ...]]
