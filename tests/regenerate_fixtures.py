"""Regenerate checked-in draw.io fixture baselines deterministically."""

from __future__ import annotations

import sys
from os import path

ROOT_DIR = path.dirname(path.dirname(path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from svg_to_drawio import RenderingOptions, convert_file  # noqa: E402

from tests.helpers import FIXTURES_DIR  # noqa: E402


def main() -> None:
    """Rebuild versioned fixture outputs using deterministic rendering policies."""
    svg_path = path.join(FIXTURES_DIR, "test_all_features.svg")
    drawio_path = path.join(FIXTURES_DIR, "test_all_features.drawio")
    convert_file(
        svg_path,
        out_path=drawio_path,
        rendering_options=RenderingOptions(text_metrics_policy="heuristic"),
    )
    print(f"Regenerated fixture: {drawio_path}")


if __name__ == "__main__":
    main()
