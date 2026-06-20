"""Unit tests for the lightweight post-conversion document hooks."""

from __future__ import annotations

import unittest

from svg_to_drawio.diagnostics import ConversionReport
from svg_to_drawio.drawio_model import Cell, Geometry
from svg_to_drawio.post_process import PostProcessOptions, apply_post_process


def _cells() -> list[Cell]:
    return [
        Cell(id="2", style="fillColor=red;", parent="1", vertex=True, geometry=Geometry(x=0, y=0, width=10, height=10)),
        Cell(id="3", style="fillColor=blue;", parent="2", vertex=True, geometry=Geometry(x=1, y=1, width=2, height=2)),
    ]


class PostProcessOptionsTests(unittest.TestCase):
    """`PostProcessOptions.is_noop` controls whether `apply_post_process` does any work."""

    def test_default_is_noop(self) -> None:
        self.assertTrue(PostProcessOptions().is_noop())

    def test_legend_alone_is_not_noop(self) -> None:
        self.assertFalse(PostProcessOptions(legend=True).is_noop())

    def test_background_alone_is_a_noop_for_cells(self) -> None:
        # background is a document attribute threaded straight into make_xml/merge_*,
        # not a cell mutation - so it alone should not trigger any cell rewriting.
        self.assertTrue(PostProcessOptions(background="#FFFFFF").is_noop())


class ApplyPostProcessTests(unittest.TestCase):
    """Behavior of `apply_post_process` against a small synthetic cell list."""

    def test_noop_options_return_the_same_list(self) -> None:
        cells = _cells()
        result = apply_post_process(cells, ConversionReport(), options=PostProcessOptions(), title="diagram")
        self.assertIs(result, cells)

    def test_legend_appends_a_notes_layer_and_summary_cell(self) -> None:
        cells = _cells()
        report = ConversionReport()
        report.fallback_count = 2
        report.add_issue("some-code", "warning", "a warning happened")

        result = apply_post_process(cells, report, options=PostProcessOptions(legend=True), title="diagram")

        self.assertEqual(len(result), len(cells) + 2)
        layer = next(cell for cell in result if cell.value == "Notes")
        body = next(cell for cell in result if cell.parent == layer.id)
        self.assertIn("diagram", body.value)
        self.assertIn("Warnings: 1", body.value)
        self.assertIn("Fallbacks: 2", body.value)

    def test_legend_ids_do_not_collide_with_existing_cells(self) -> None:
        cells = _cells()
        result = apply_post_process(cells, ConversionReport(), options=PostProcessOptions(legend=True), title="d")
        ids = [cell.id for cell in result]
        self.assertEqual(len(ids), len(set(ids)))
