"""Regenerate checked-in draw.io fixture baselines deterministically."""

from __future__ import annotations

from os import path

from svg_to_drawio import RenderingOptions, convert_file

from tests.helpers import FIXTURES_DIR


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
