"""Module entry point for `python -m svg_to_drawio`."""

from __future__ import annotations

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
