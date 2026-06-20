"""Integration tests for `--merge` and the post-processing CLI flags."""

from __future__ import annotations

import io
import tempfile
import xml.etree.ElementTree as ET
from contextlib import redirect_stderr, redirect_stdout
from os import path

import main

from tests.helpers import SvgTestCase

_RECT_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
    '<rect x="0" y="0" width="10" height="10" fill="red" /></svg>'
)


def _write_svg(tmpdir: str, name: str, content: str = _RECT_SVG) -> str:
    svg_path = path.join(tmpdir, name)
    with open(svg_path, "w", encoding="utf-8") as handle:
        handle.write(content)
    return svg_path


class CliMergeTests(SvgTestCase):
    """End-to-end `--merge pages`/`--merge grid` runs through the CLI entry point."""

    def test_merge_pages_writes_one_diagram_per_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            svg_a = _write_svg(tmpdir, "a.svg")
            svg_b = _write_svg(tmpdir, "b.svg")
            merged_path = path.join(tmpdir, "merged.drawio")

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main.main([svg_a, svg_b, "--merge", "pages", "--merge-output", merged_path])

            self.assertEqual(code, 0)
            root = ET.parse(merged_path).getroot()
            self.assertEqual(len(root.findall("diagram")), 2)
            self.assertIn("Merged output written to:", stdout.getvalue())

    def test_merge_grid_writes_one_tile_per_input_with_legend_and_background(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            svg_a = _write_svg(tmpdir, "a.svg")
            svg_b = _write_svg(tmpdir, "b.svg")
            merged_path = path.join(tmpdir, "merged.drawio")

            code = main.main(
                [
                    svg_a,
                    svg_b,
                    "--merge",
                    "grid",
                    "--merge-output",
                    merged_path,
                    "--grid-columns",
                    "2",
                    "--legend",
                    "--background-color",
                    "#FFFFFF",
                ]
            )

            self.assertEqual(code, 0)
            with open(merged_path, encoding="utf-8") as handle:
                xml_text = handle.read()
            root = ET.fromstring(xml_text)
            self.assertEqual(len(root.findall("diagram")), 1)
            self.assertEqual(xml_text.count("group;"), 2)
            self.assertIn('background="#FFFFFF"', xml_text)
            self.assertIsNotNone(root.find(".//mxCell[@value='Notes']"))

    def test_merge_requires_merge_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            svg_a = _write_svg(tmpdir, "a.svg")

            stderr = io.StringIO()
            with redirect_stderr(stderr):
                code = main.main([svg_a, "--merge", "pages"])

            self.assertEqual(code, 1)
            self.assertIn("--merge-output", stderr.getvalue())

    def test_merge_conflicts_with_watch_and_analyze(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            svg_a = _write_svg(tmpdir, "a.svg")
            merged_path = path.join(tmpdir, "merged.drawio")

            stderr = io.StringIO()
            with redirect_stderr(stderr):
                code = main.main([svg_a, "--merge", "pages", "--merge-output", merged_path, "--analyze"])

            self.assertEqual(code, 1)
            self.assertIn("--merge cannot be combined with", stderr.getvalue())

    def test_merge_continues_after_one_failure_and_reports_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            svg_good = _write_svg(tmpdir, "good.svg")
            svg_bad = _write_svg(tmpdir, "bad.svg", content="<svg")
            merged_path = path.join(tmpdir, "merged.drawio")

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main.main([svg_good, svg_bad, "--merge", "pages", "--merge-output", merged_path])

            self.assertEqual(code, 1)
            self.assertIn("Failed:", stdout.getvalue())
            root = ET.parse(merged_path).getroot()
            self.assertEqual(len(root.findall("diagram")), 1)


class CliPostProcessTests(SvgTestCase):
    """Post-processing flags also apply to ordinary (non-merge) conversion runs."""

    def test_legend_and_background_apply_to_a_normal_conversion(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            svg_path = _write_svg(tmpdir, "diagram.svg")
            out_path = path.join(tmpdir, "diagram.drawio")

            code = main.main(
                [
                    svg_path,
                    "--overwrite",
                    "--legend",
                    "--background-color",
                    "#EEEEEE",
                ]
            )

            self.assertEqual(code, 0)
            with open(out_path, encoding="utf-8") as handle:
                xml_text = handle.read()
            self.assertIn('background="#EEEEEE"', xml_text)
            root = ET.fromstring(xml_text)
            self.assertIsNotNone(root.find(".//mxCell[@value='Notes']"))

    def test_stdout_mode_also_applies_post_process(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            svg_path = _write_svg(tmpdir, "diagram.svg")

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main.main([svg_path, "--stdout", "--background-color", "#EEEEEE"])

            self.assertEqual(code, 0)
            self.assertIn('background="#EEEEEE"', stdout.getvalue())
