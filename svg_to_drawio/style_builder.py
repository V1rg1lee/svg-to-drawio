"""Helpers for assembling draw.io style strings."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Self

StyleValue = str | int | float
StyleMappingValue = StyleValue | bool | None


class StyleBuilder:
    """Incrementally build a draw.io style string while preserving insertion order."""

    def __init__(self) -> None:
        self._parts: list[str] = []

    def add_flag(self, flag: str, *, when: bool = True) -> Self:
        """Append a bare style flag such as `ellipse` or `rounded`."""
        if when and flag:
            self._parts.append(flag)
        return self

    def add(self, key: str, value: StyleValue | None, *, when: bool = True) -> Self:
        """Append a `key=value` style entry when a value is available."""
        if when and value is not None:
            self._parts.append(f"{key}={value}")
        return self

    def extend_pairs(
        self,
        pairs: Mapping[str, StyleMappingValue] | Iterable[tuple[str, StyleMappingValue]],
        *,
        when: bool = True,
    ) -> Self:
        """Append multiple entries from a mapping or an ordered iterable of pairs."""
        if not when:
            return self

        items = pairs.items() if isinstance(pairs, Mapping) else pairs
        for key, value in items:
            if value is None or value is False:
                continue
            if value is True:
                self.add_flag(key)
            else:
                self.add(key, value)
        return self

    def extend_raw(self, raw: str | None, *, when: bool = True) -> Self:
        """Append entries from an existing semicolon-delimited style fragment."""
        if not when or not raw:
            return self
        for part in raw.split(";"):
            part = part.strip()
            if part:
                self._parts.append(part)
        return self

    def build(self) -> str:
        """Serialize the accumulated style entries with trailing semicolons."""
        if not self._parts:
            return ""
        return ";".join(self._parts) + ";"
