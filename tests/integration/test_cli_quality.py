"""Integration tests for CLI quality gates and parallel execution options."""

from __future__ import annotations

import io
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from os import makedirs, path

import main

from tests.helpers import SvgTestCase


class CliQualityTests(SvgTestCase):
    """Exercise CLI-only automation flags built on top of conversion reports."""

    def test_cli_rejects_an_out_of_range_min_score(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            svg_path = path.join(tmpdir, "diagram.svg")
            with open(svg_path, "w", encoding="utf-8") as handle:
                handle.write('<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" />')

            stderr = io.StringIO()
            with redirect_stderr(stderr), self.assertRaises(SystemExit) as ctx:
                main.main([svg_path, "--min-score", "150"])

        self.assertEqual(ctx.exception.code, 2)
        self.assertIn("must be between 0 and 100", stderr.getvalue())

    def test_cli_rejects_a_zero_max_elements(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            svg_path = path.join(tmpdir, "diagram.svg")
            with open(svg_path, "w", encoding="utf-8") as handle:
                handle.write('<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" />')

            stderr = io.StringIO()
            with redirect_stderr(stderr), self.assertRaises(SystemExit) as ctx:
                main.main([svg_path, "--max-elements", "0"])

        self.assertEqual(ctx.exception.code, 2)
        self.assertIn("must be a positive integer", stderr.getvalue())

    def test_cli_rejects_zero_workers(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            svg_path = path.join(tmpdir, "diagram.svg")
            with open(svg_path, "w", encoding="utf-8") as handle:
                handle.write('<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" />')

            stderr = io.StringIO()
            with redirect_stderr(stderr), self.assertRaises(SystemExit) as ctx:
                main.main([svg_path, "--workers", "0"])

        self.assertEqual(ctx.exception.code, 2)
        self.assertIn("must be a positive integer", stderr.getvalue())

    def test_cli_fail_on_fallback_and_require_native_surface_quality_gate_failures(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            svg_path = path.join(tmpdir, "diagram.svg")
            with open(svg_path, "w", encoding="utf-8") as handle:
                handle.write(
                    '<svg xmlns="http://www.w3.org/2000/svg" width="120" height="80">'
                    '<defs><clipPath id="cut"><circle cx="40" cy="40" r="20" /></clipPath></defs>'
                    '<rect x="10" y="10" width="60" height="60" fill="red" '
                    'stroke="black" stroke-width="2" clip-path="url(#cut)" />'
                    "</svg>"
                )

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main.main([svg_path, "--overwrite", "--fail-on-fallback", "--require-native", "clipping"])

        self.assertEqual(code, 1)
        self.assertIn("QUALITY GATE:", stdout.getvalue())

    def test_cli_fail_on_warning_surfaces_a_quality_gate_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            svg_path = path.join(tmpdir, "diagram.svg")
            with open(svg_path, "w", encoding="utf-8") as handle:
                handle.write(
                    '<svg xmlns="http://www.w3.org/2000/svg" width="30" height="10">'
                    '<rect x="0" y="0" width="10" height="10" fill="red" />'
                    '<rect x="10" y="0" width="10" height="10" fill="green" />'
                    '<rect x="20" y="0" width="10" height="10" fill="blue" />'
                    "</svg>"
                )

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main.main([svg_path, "--overwrite", "--max-elements", "1", "--fail-on-warning"])

        self.assertEqual(code, 1)
        self.assertIn("QUALITY GATE:", stdout.getvalue())

    def test_cli_min_score_surfaces_a_quality_gate_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            svg_path = path.join(tmpdir, "clip.svg")
            with open(svg_path, "w", encoding="utf-8") as handle:
                handle.write(
                    '<svg xmlns="http://www.w3.org/2000/svg" width="120" height="80">'
                    '<defs><clipPath id="cut"><circle cx="40" cy="40" r="20" /></clipPath></defs>'
                    '<rect x="10" y="10" width="60" height="60" fill="#ff0000" '
                    'stroke="#222222" stroke-width="2" clip-path="url(#cut)" />'
                    "</svg>"
                )

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main.main([svg_path, "--overwrite", "--min-score", "100"])

        self.assertEqual(code, 1)
        self.assertIn("QUALITY GATE:", stdout.getvalue())
        self.assertIn("below the required 100", stdout.getvalue())

    def test_cli_no_cache_forces_reconversion_of_an_unchanged_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            svg_path = path.join(tmpdir, "diagram.svg")
            with open(svg_path, "w", encoding="utf-8") as handle:
                handle.write(
                    '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
                    '<rect x="0" y="0" width="10" height="10" fill="red" />'
                    "</svg>"
                )

            first_stdout = io.StringIO()
            with redirect_stdout(first_stdout):
                first_code = main.main([svg_path, "--overwrite"])

            second_stdout = io.StringIO()
            with redirect_stdout(second_stdout):
                second_code = main.main([svg_path, "--overwrite", "--no-cache"])

        self.assertEqual(first_code, 0)
        self.assertEqual(second_code, 0)
        self.assertIn("Summary: 1 converted, 0 skipped, 0 failed", first_stdout.getvalue())
        self.assertIn(
            "Summary: 1 converted, 0 skipped, 0 failed",
            second_stdout.getvalue(),
            "with --no-cache the unchanged input should be reconverted, not skipped via the cache hit",
        )

    def test_cli_parallel_workers_convert_multiple_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            input_dir = path.join(tmpdir, "input")
            makedirs(input_dir, exist_ok=True)
            for name in ("one.svg", "two.svg"):
                with open(path.join(input_dir, name), "w", encoding="utf-8") as handle:
                    handle.write(
                        '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
                        '<rect x="0" y="0" width="10" height="10" fill="red" />'
                        "</svg>"
                    )

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main.main([input_dir, "--workers", "2", "--overwrite"])

        self.assertEqual(code, 0)
        self.assertIn("Summary: 2 converted, 0 skipped, 0 failed", stdout.getvalue())
