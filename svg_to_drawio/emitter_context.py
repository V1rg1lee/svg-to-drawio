"""Typed context passed to element emitters."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from .defs import DefsIndex
from .drawio_model import Cell

if TYPE_CHECKING:
    from .css import CssRule


@dataclass(frozen=True)
class EmitterContext:
    """State exposed to element emitters during a conversion pass.

    The context deliberately carries only the pieces emitters need: access to indexed
    definitions, the active parent/link scope, the source directory for images, the CSS
    rules for nested text styling, and callbacks for creating output cells.
    """

    defs: DefsIndex
    parent_id: str
    link_url: str
    source_dir: str
    css_rules: Sequence[CssRule]
    custom_props: dict[str, str]
    add_cell: Callable[[Cell], None]
    next_id_callback: Callable[[], str]

    def add(self, cell: Cell) -> None:
        """Append a generated draw.io cell to the output document."""
        self.add_cell(cell)

    def next_id(self) -> str:
        """Return the next draw.io cell identifier."""
        return self.next_id_callback()

    def with_parent(self, parent_id: str) -> EmitterContext:
        """Return a copy of the context scoped to a different parent cell."""
        return replace(self, parent_id=parent_id)

    def with_link(self, link_url: str) -> EmitterContext:
        """Return a copy of the context scoped to a different active link URL."""
        return replace(self, link_url=link_url)
