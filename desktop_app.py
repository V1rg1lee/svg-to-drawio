"""Launcher entry point for the PySide6 desktop application."""

from __future__ import annotations

import sys


def _handle_headless_flags(argv: list[str]) -> int | None:
    """Handle simple non-GUI flags before importing PySide dependencies."""
    if "--version" in argv:
        from svg_to_drawio import __version__

        print(__version__)
        return 0

    if "--smoke-test" in argv:
        from svg_to_drawio import __version__

        print(f"svg-to-drawio desktop smoke test OK ({__version__})")
        return 0

    return None


headless_exit_code = _handle_headless_flags(sys.argv[1:])
if headless_exit_code is not None:
    raise SystemExit(headless_exit_code)

try:
    from svg_to_drawio_desktop.app import main
except ImportError as exc:  # pragma: no cover - depends on optional desktop dependencies
    raise SystemExit(
        "Desktop dependencies are not installed. Run `python -m pip install -r requirements-desktop.txt` first."
    ) from exc


if __name__ == "__main__":
    raise SystemExit(main())
