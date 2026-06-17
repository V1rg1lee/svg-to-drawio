"""Text measurement helpers with a best-effort real font backend."""

from __future__ import annotations

import importlib
from functools import lru_cache
from threading import Lock
from typing import Any

_TK_LOCK = Lock()
_tk: Any | None
_tkfont: Any | None
_TK_ROOT: Any = None
_TK_AVAILABLE = True


def _optional_import(module_name: str) -> Any | None:
    """Import one optional module and return ``None`` when it is unavailable."""
    try:  # pragma: no cover - availability depends on the Python build and runtime environment
        return importlib.import_module(module_name)
    except ImportError:  # pragma: no cover - uncommon, but keep the engine optional
        return None


_tk = _optional_import("tkinter")
_tkfont = _optional_import("tkinter.font")


def _normalized_family(family: str | None) -> str:
    """Return the first usable font-family token from an SVG/CSS family list."""
    text = (family or "Helvetica").split(",", 1)[0].strip()
    return text.strip("'\"") or "Helvetica"


def _weight_factor(character: str) -> float:
    """Return a width weight for one character in the heuristic backend."""
    if character in "il.,'`!:;| ":
        return 0.34
    if character in "fjrt()[]{}":
        return 0.42
    if character in "mwMW@%#&":
        return 0.95
    if character.isupper():
        return 0.72
    if character.isdigit():
        return 0.61
    return 0.56


def _heuristic_metrics(text: str, font_size: float, *, bold: bool, italic: bool) -> tuple[float, float]:
    """Estimate text metrics when no real font backend is available."""
    width_factor = sum(_weight_factor(character) for character in text) or 1.0
    width = max(width_factor * font_size, font_size * 0.9)
    if bold:
        width *= 1.04
    if italic:
        width *= 1.02
    height = max(font_size * 1.45, 10.0)
    return width, height


def _get_tk_root() -> Any | None:
    """Return a shared hidden Tk root when the runtime can provide one."""
    global _TK_ROOT, _TK_AVAILABLE

    if _tk is None or not _TK_AVAILABLE:
        return None
    if _TK_ROOT is not None:
        return _TK_ROOT

    with _TK_LOCK:
        if _TK_ROOT is None:
            try:  # pragma: no cover - depends on OS GUI availability
                root = _tk.Tk()
                root.withdraw()
            except Exception:
                _TK_AVAILABLE = False
                return None
            _TK_ROOT = root
        return _TK_ROOT


@lru_cache(maxsize=4096)
def measure_text(
    text: str,
    font_size: float,
    font_family: str,
    font_weight: str = "normal",
    font_style: str = "normal",
) -> tuple[float, float]:
    """Measure text using platform fonts when possible, else fall back to a tuned heuristic."""
    normalized_text = text or " "
    normalized_family = _normalized_family(font_family)
    bold = font_weight in {"bold", "600", "700", "800", "900"}
    italic = font_style == "italic"

    root = _get_tk_root()
    if root is None or _tkfont is None:
        return _heuristic_metrics(normalized_text, font_size, bold=bold, italic=italic)

    try:  # pragma: no cover - depends on Tk runtime behavior
        tk_font = _tkfont.Font(
            root=root,
            family=normalized_family,
            size=max(1, int(round(font_size))),
            weight="bold" if bold else "normal",
            slant="italic" if italic else "roman",
        )
        width = float(tk_font.measure(normalized_text))
        height = float(tk_font.metrics("linespace"))
        return max(width, font_size * 0.9), max(height, font_size * 1.2)
    except Exception:
        return _heuristic_metrics(normalized_text, font_size, bold=bold, italic=italic)
