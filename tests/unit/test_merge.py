"""Unit tests for combining several converted SVGs into one draw.io document."""

from __future__ import annotations

import unittest
import xml.etree.ElementTree as ET
from os import path

from svg_to_drawio.conversion_service import resolve_merge_output_path
from svg_to_drawio.drawio_model import Cell, Geometry
from svg_to_drawio.merge import build_grid_cells, merge_grid, merge_pages


def _rect_cells(cell_id: str = "2") -> list[Cell]:
    """Return a single root-level rectangle cell, mimicking one converted SVG's output."""
    return [
        Cell(
            id=cell_id,
            style="rounded=0;whiteSpace=wrap;html=1;fillColor=red;",
            parent="1",
            vertex=True,
            geometry=Geometry(x=0, y=0, width=100, height=50),
        )
    ]


class MergePagesTests(unittest.TestCase):
    """`merge_pages` combines independently-converted SVGs into separate diagram pages."""

    def test_one_diagram_per_input(self) -> None:
        named_cells = [("logo-a", _rect_cells()), ("logo-b", _rect_cells())]
        xml = merge_pages(named_cells)
        root = ET.fromstring(xml)
        diagrams = root.findall("diagram")
        self.assertEqual(len(diagrams), 2)
        self.assertEqual([diagram.get("name") for diagram in diagrams], ["logo-a", "logo-b"])

    def test_reused_ids_across_pages_do_not_collide(self) -> None:
        # Each Converter run starts numbering at id "2", so two independent SVGs reuse the
        # same ids on purpose - this only stays valid because each page gets its own root.
        named_cells = [("logo-a", _rect_cells("2")), ("logo-b", _rect_cells("2"))]
        xml = merge_pages(named_cells)
        root = ET.fromstring(xml)
        for diagram in root.findall("diagram"):
            cell = diagram.find(".//mxCell[@id='2']")
            self.assertIsNotNone(cell)

    def test_empty_input_still_produces_a_valid_document(self) -> None:
        xml = merge_pages([])
        root = ET.fromstring(xml)
        self.assertEqual(root.findall("diagram"), [])

    def test_background_is_applied_to_every_page(self) -> None:
        named_cells = [("logo-a", _rect_cells()), ("logo-b", _rect_cells())]
        xml = merge_pages(named_cells, background="#112233")
        self.assertEqual(xml.count('background="#112233"'), 2)


class MergeGridTests(unittest.TestCase):
    """`merge_grid` combines independently-converted SVGs into one labeled tile grid."""

    def test_single_diagram_with_one_tile_per_input(self) -> None:
        named_cells = [("a", _rect_cells()), ("b", _rect_cells()), ("c", _rect_cells())]
        xml = merge_grid(named_cells, columns=2)
        root = ET.fromstring(xml)
        self.assertEqual(len(root.findall("diagram")), 1)
        self.assertEqual(xml.count("group;"), 3)
        labels = {cell.get("value") for cell in root.findall(".//mxCell") if cell.get("style", "").startswith("text;")}
        self.assertEqual(labels, {"a", "b", "c"})

    def test_no_id_collisions_across_tiles(self) -> None:
        named_cells = [("a", _rect_cells("2")), ("b", _rect_cells("2")), ("c", _rect_cells("2"))]
        cells = build_grid_cells(named_cells, columns=2)
        ids = [cell.id for cell in cells]
        self.assertEqual(len(ids), len(set(ids)))

    def test_tiles_are_laid_out_on_a_grid_without_overlap(self) -> None:
        named_cells = [("a", _rect_cells()), ("b", _rect_cells())]
        cells = build_grid_cells(named_cells, columns=2)
        groups = [cell for cell in cells if cell.style == "group;"]
        self.assertEqual(len(groups), 2)
        xs = sorted(cell.geometry.x for cell in groups if cell.geometry is not None)
        self.assertEqual(len(xs), 2)
        self.assertLess(xs[0], xs[1])

    def test_empty_input_returns_empty_grid(self) -> None:
        self.assertEqual(build_grid_cells([]), [])
        xml = merge_grid([])
        root = ET.fromstring(xml)
        cells = root.findall(".//mxCell")
        self.assertEqual({cell.get("id") for cell in cells}, {"0", "1"})

    def test_background_threads_into_graph_model(self) -> None:
        named_cells = [("a", _rect_cells())]
        xml = merge_grid(named_cells, background="#445566")
        self.assertIn('background="#445566"', xml)


class ResolveMergeOutputPathTests(unittest.TestCase):
    """`resolve_merge_output_path` is the shared CLI/desktop merge-output resolution rule."""

    def test_bare_filename_resolves_against_output_dir(self) -> None:
        resolved = resolve_merge_output_path("merged.drawio", output_dir=path.join("out", "dir"))
        self.assertEqual(resolved, path.abspath(path.join("out", "dir", "merged.drawio")))

    def test_bare_filename_without_output_dir_resolves_against_cwd(self) -> None:
        resolved = resolve_merge_output_path("merged.drawio", output_dir=None)
        self.assertEqual(resolved, path.abspath("merged.drawio"))

    def test_missing_extension_is_appended(self) -> None:
        resolved = resolve_merge_output_path("merged", output_dir=None)
        self.assertTrue(resolved.endswith(".drawio"))

    def test_existing_extension_is_not_duplicated(self) -> None:
        resolved = resolve_merge_output_path("merged.drawio", output_dir=None)
        self.assertTrue(resolved.endswith(".drawio"))
        self.assertFalse(resolved.endswith(".drawio.drawio"))

    def test_absolute_path_ignores_output_dir(self) -> None:
        absolute = path.abspath(path.join("somewhere", "else", "merged.drawio"))
        resolved = resolve_merge_output_path(absolute, output_dir=path.join("out", "dir"))
        self.assertEqual(resolved, absolute)

    def test_relative_subfolder_is_preserved_under_output_dir(self) -> None:
        resolved = resolve_merge_output_path(path.join("brand", "merged"), output_dir=path.join("out", "dir"))
        self.assertEqual(resolved, path.abspath(path.join("out", "dir", "brand", "merged.drawio")))
