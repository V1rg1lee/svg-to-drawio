"""Parsing helpers for values read back from `QSettings`.

`QSettings` can hand back a native Python bool/int, or a plain string (e.g. when the
backing store is an INI file), depending on platform and prior storage format. These
helpers normalize either shape and are kept independent of Qt so the parsing/defaulting
rules can be unit tested without constructing a QApplication.
"""

from __future__ import annotations


def parse_bool_setting(raw: object) -> bool:
    """Normalize one value already returned by `QSettings.value(key, default)` into a bool."""
    return str(raw).lower() in {"1", "true", "yes"}


def parse_int_setting(raw: object, *, default: int) -> int:
    """Normalize one value already returned by `QSettings.value(key, default)` into an int."""
    try:
        return int(str(raw))
    except (TypeError, ValueError):
        return default
