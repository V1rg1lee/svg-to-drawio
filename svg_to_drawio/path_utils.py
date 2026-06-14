"""Compatibility facade for SVG path helpers.

The implementation now lives in smaller focused modules:
- `path_parser.py` for tokenization and command parsing
- `path_bounds.py` for tight bounding-box calculations
- `path_stencil.py` for draw.io stencil serialization
"""

from __future__ import annotations

from .path_bounds import commands_bbox
from .path_parser import path_commands, path_points, sample_open_path, tokenize_path
from .path_stencil import (
    commands_to_stencil_path,
    make_stencil_style,
    make_stencil_style_from_commands,
    make_stencil_style_from_xml,
    path_to_stencil,
)
from .path_types import BezierCurve, PathCommand, Point2D

__all__ = [
    "BezierCurve",
    "PathCommand",
    "Point2D",
    "commands_bbox",
    "commands_to_stencil_path",
    "make_stencil_style",
    "make_stencil_style_from_commands",
    "make_stencil_style_from_xml",
    "path_commands",
    "path_points",
    "path_to_stencil",
    "sample_open_path",
    "tokenize_path",
]
