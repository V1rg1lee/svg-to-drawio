"""Compatibility wrapper around the packaged CLI entry point."""

from __future__ import annotations

from collections.abc import Sequence

from svg_to_drawio.cli import build_parser, run
from svg_to_drawio.cli import main as package_main


def main(argv: Sequence[str] | None = None) -> int:
    """Delegate to the packaged CLI implementation."""
    return package_main(argv)


__all__ = ["build_parser", "main", "run"]


if __name__ == "__main__":
    raise SystemExit(main())
