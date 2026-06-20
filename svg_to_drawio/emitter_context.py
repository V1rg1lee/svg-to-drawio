"""Typed context passed to element emitters."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING

from .defs import DefsIndex
from .diagnostics import ConversionReport
from .drawio_model import Cell
from .rendering_options import RenderingOptions

if TYPE_CHECKING:
    from .css import CssRule, CssRuleIndex


@dataclass(frozen=True)
class TraversalMode:
    """Conversion-pass switches that always change together as one unit.

    `allow_fallback`, `record_issues`, and `enforce_max_elements` are all turned off
    together for the lightweight bounds-estimation pass (re-emitting a subtree into a
    throwaway context just to measure it, with no side effects), and all on for normal
    emission - there is no combination in between. Grouping them here avoids threading
    three separate boolean parameters through every recursive `_convert`/`_convert_group`/
    `_resolve_use` call.
    """

    allow_fallback: bool = True
    record_issues: bool = True
    enforce_max_elements: bool = True


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
    report: ConversionReport
    rendering_options: RenderingOptions
    add_cell: Callable[[Cell], None]
    next_id_callback: Callable[[], str]
    rule_index: CssRuleIndex | None = field(default=None)
    mode: TraversalMode = field(default_factory=TraversalMode)

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

    def with_mode(self, mode: TraversalMode) -> EmitterContext:
        """Return a copy of the context using a different traversal mode."""
        return replace(self, mode=mode)
