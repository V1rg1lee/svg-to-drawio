"""Integration tests for the command-line interface."""

from __future__ import annotations

import io
import tempfile
from contextlib import redirect_stdout
from os import makedirs, path

import main

from tests.helpers import SvgTestCase


class CliTests(SvgTestCase):
    """Exercise the public CLI entry points with real filesystem interactions."""

    def test_cli_supports_recursive_output_dir_and_continues_after_failures(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            input_dir = path.join(tmpdir, "input")
            output_dir = path.join(tmpdir, "out")
            makedirs(path.join(input_dir, "nested"), exist_ok=True)

            with open(path.join(input_dir, "nested", "good.svg"), "w", encoding="utf-8") as handle:
                handle.write(
                    '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
                    '<rect x="0" y="0" width="10" height="10" fill="red" />'
                    "</svg>"
                )
            with open(path.join(input_dir, "bad.svg"), "w", encoding="utf-8") as handle:
                handle.write("<svg")

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main.main([input_dir, "--recursive", "--output-dir", output_dir, "--overwrite"])

            self.assertEqual(code, 1)
            self.assertTrue(path.isfile(path.join(output_dir, "nested", "good.drawio")))
            self.assertFalse(path.exists(path.join(output_dir, "bad.drawio")))
            self.assertIn("Failed:", stdout.getvalue())
            self.assertIn("Summary: 1 converted, 0 skipped, 1 failed", stdout.getvalue())

    def test_cli_overwrite_flag_controls_existing_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            svg_path = path.join(tmpdir, "diagram.svg")
            out_path = path.join(tmpdir, "diagram.drawio")
            with open(svg_path, "w", encoding="utf-8") as handle:
                handle.write(
                    '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
                    '<rect x="0" y="0" width="10" height="10" fill="red" />'
                    "</svg>"
                )

            with open(out_path, "w", encoding="utf-8") as handle:
                handle.write("sentinel")

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main.run(svg_path, overwrite=False)
            self.assertEqual(code, 0)
            with open(out_path, encoding="utf-8") as handle:
                self.assertEqual(handle.read(), "sentinel")

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main.run(svg_path, overwrite=True)
            self.assertEqual(code, 0)
            with open(out_path, encoding="utf-8") as handle:
                self.assertIn("<mxfile>", handle.read())
