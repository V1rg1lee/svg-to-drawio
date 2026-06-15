"""Launcher entry point for the PySide6 desktop application."""

from __future__ import annotations

try:
    from svg_to_drawio_desktop.app import main
except ImportError as exc:  # pragma: no cover - depends on optional desktop dependencies
    raise SystemExit(
        "Desktop dependencies are not installed. Run `python -m pip install -r requirements-desktop.txt` first."
    ) from exc


if __name__ == "__main__":
    raise SystemExit(main())
