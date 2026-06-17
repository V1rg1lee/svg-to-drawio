"""Text measurement helpers with a best-effort real font backend."""

from __future__ import annotations

import importlib
import os
from functools import lru_cache
from threading import Lock
from typing import Any

_TK_LOCK = Lock()
_tk: Any | None
_tkfont: Any | None
_TK_ROOT: Any = None
_TK_AVAILABLE = True
_PIL_IMAGE_FONT: Any | None
_FONT_CACHE: dict[tuple[str, bool, bool], str | None] = {}


def _optional_import(module_name: str) -> Any | None:
    """Import one optional module and return ``None`` when it is unavailable."""
    try:  # pragma: no cover - availability depends on the Python build and runtime environment
        return importlib.import_module(module_name)
    except ImportError:  # pragma: no cover - uncommon, but keep the engine optional
        return None


_tk = _optional_import("tkinter")
_tkfont = _optional_import("tkinter.font")
_PIL_IMAGE_FONT = _optional_import("PIL.ImageFont")


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


def _font_dirs() -> list[str]:
    """Return a short list of common system font directories."""
    candidates = [
        os.path.join(os.environ.get("WINDIR", ""), "Fonts"),
        "/usr/share/fonts",
        "/usr/local/share/fonts",
        os.path.expanduser("~/.fonts"),
        os.path.expanduser("~/.local/share/fonts"),
        "/System/Library/Fonts",
        "/Library/Fonts",
    ]
    return [directory for directory in candidates if directory and os.path.isdir(directory)]


def _candidate_font_names(family: str, *, bold: bool, italic: bool) -> list[str]:
    """Return plausible filename candidates for one CSS font family."""
    normalized = _normalized_family(family).lower().replace(" ", "")
    if normalized in {"helvetica", "arial", "sans-serif", "sansserif"}:
        return [
            "arialbi.ttf" if bold and italic else "",
            "arialbd.ttf" if bold else "",
            "ariali.ttf" if italic else "",
            "arial.ttf",
            "LiberationSans-BoldItalic.ttf" if bold and italic else "",
            "LiberationSans-Bold.ttf" if bold else "",
            "LiberationSans-Italic.ttf" if italic else "",
            "LiberationSans-Regular.ttf",
            "DejaVuSans-BoldOblique.ttf" if bold and italic else "",
            "DejaVuSans-Bold.ttf" if bold else "",
            "DejaVuSans-Oblique.ttf" if italic else "",
            "DejaVuSans.ttf",
        ]
    if normalized in {"times", "timesnewroman", "serif"}:
        return [
            "timesbi.ttf" if bold and italic else "",
            "timesbd.ttf" if bold else "",
            "timesi.ttf" if italic else "",
            "times.ttf",
            "LiberationSerif-BoldItalic.ttf" if bold and italic else "",
            "LiberationSerif-Bold.ttf" if bold else "",
            "LiberationSerif-Italic.ttf" if italic else "",
            "LiberationSerif-Regular.ttf",
            "DejaVuSerif-BoldItalic.ttf" if bold and italic else "",
            "DejaVuSerif-Bold.ttf" if bold else "",
            "DejaVuSerif-Italic.ttf" if italic else "",
            "DejaVuSerif.ttf",
        ]
    if normalized in {"courier", "couriernew", "monospace"}:
        return [
            "courbi.ttf" if bold and italic else "",
            "courbd.ttf" if bold else "",
            "couri.ttf" if italic else "",
            "cour.ttf",
            "LiberationMono-BoldItalic.ttf" if bold and italic else "",
            "LiberationMono-Bold.ttf" if bold else "",
            "LiberationMono-Italic.ttf" if italic else "",
            "LiberationMono-Regular.ttf",
            "DejaVuSansMono-BoldOblique.ttf" if bold and italic else "",
            "DejaVuSansMono-Bold.ttf" if bold else "",
            "DejaVuSansMono-Oblique.ttf" if italic else "",
            "DejaVuSansMono.ttf",
        ]
    return [
        normalized,
        f"{normalized}-bolditalic.ttf" if bold and italic else "",
        f"{normalized}-bold.ttf" if bold else "",
        f"{normalized}-italic.ttf" if italic else "",
        f"{normalized}.ttf",
    ]


def _find_font_path(family: str, *, bold: bool, italic: bool) -> str | None:
    """Best-effort search for a font file matching the requested family."""
    cache_key = (_normalized_family(family).lower(), bold, italic)
    if cache_key in _FONT_CACHE:
        return _FONT_CACHE[cache_key]

    for directory in _font_dirs():
        for candidate_name in _candidate_font_names(family, bold=bold, italic=italic):
            if not candidate_name:
                continue
            for root, _, files in os.walk(directory):
                lower_to_name = {name.lower(): name for name in files}
                actual_name = lower_to_name.get(candidate_name.lower())
                if actual_name is not None:
                    font_path = os.path.join(root, actual_name)
                    _FONT_CACHE[cache_key] = font_path
                    return font_path

    _FONT_CACHE[cache_key] = None
    return None


def _measure_with_pillow(
    text: str,
    font_size: float,
    font_family: str,
    *,
    bold: bool,
    italic: bool,
) -> tuple[float, float] | None:
    """Measure text with Pillow when a matching font file can be located."""
    if _PIL_IMAGE_FONT is None:
        return None

    font_path = _find_font_path(font_family, bold=bold, italic=italic)
    if not font_path:
        return None

    try:  # pragma: no cover - depends on optional Pillow and platform fonts
        font = _PIL_IMAGE_FONT.truetype(font_path, size=max(1, int(round(font_size))))
        left, top, right, bottom = font.getbbox(text)
    except Exception:
        return None

    width = float(max(right - left, font_size * 0.9))
    height = float(max(bottom - top, font_size * 1.2))
    return width, height


@lru_cache(maxsize=4096)
def measure_text_detailed(
    text: str,
    font_size: float,
    font_family: str,
    font_weight: str = "normal",
    font_style: str = "normal",
    *,
    policy: str = "auto",
) -> tuple[float, float, str]:
    """Measure text and return both its size and the backend that produced it."""
    normalized_text = text or " "
    normalized_family = _normalized_family(font_family)
    bold = font_weight in {"bold", "600", "700", "800", "900"}
    italic = font_style == "italic"

    if policy == "heuristic":
        width, height = _heuristic_metrics(normalized_text, font_size, bold=bold, italic=italic)
        return width, height, "heuristic"

    if policy == "system":
        pillow_metrics = _measure_with_pillow(
            normalized_text,
            font_size,
            normalized_family,
            bold=bold,
            italic=italic,
        )
        if pillow_metrics is not None:
            return pillow_metrics[0], pillow_metrics[1], "pillow"

    root = _get_tk_root()
    if root is not None and _tkfont is not None:
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
            return max(width, font_size * 0.9), max(height, font_size * 1.2), "tk"
        except Exception:
            pass

    width, height = _heuristic_metrics(normalized_text, font_size, bold=bold, italic=italic)
    return width, height, "heuristic"


@lru_cache(maxsize=4096)
def measure_text(
    text: str,
    font_size: float,
    font_family: str,
    font_weight: str = "normal",
    font_style: str = "normal",
    *,
    policy: str = "auto",
) -> tuple[float, float]:
    """Measure text using platform fonts when possible, else fall back to a tuned heuristic."""
    width, height, _ = measure_text_detailed(
        text,
        font_size,
        font_family,
        font_weight=font_weight,
        font_style=font_style,
        policy=policy,
    )
    return width, height
