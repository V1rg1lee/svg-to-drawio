"""Integration tests for CLI quality gates and parallel execution options."""

from __future__ import annotations

import io
import tempfile
from contextlib import redirect_stdout
from os import makedirs, path

import main

from tests.helpers import SvgTestCase


class CliQualityTests(SvgTestCase):
    """Exercise CLI-only automation flags built on top of conversion reports."""

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
