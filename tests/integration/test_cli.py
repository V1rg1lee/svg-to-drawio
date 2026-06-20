"""Integration tests for the command-line interface."""

from __future__ import annotations

import io
import json
import tempfile
import xml.etree.ElementTree as ET
from contextlib import redirect_stderr, redirect_stdout
from os import makedirs, path
from unittest.mock import patch

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

    def test_cli_stdout_reports_a_clean_error_for_malformed_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            svg_path = path.join(tmpdir, "bad.svg")
            with open(svg_path, "w", encoding="utf-8") as handle:
                handle.write("<svg")

            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = main.run(svg_path, stdout=True)

            self.assertEqual(code, 1)
            self.assertEqual(stdout.getvalue(), "")
            self.assertIn("Error:", stderr.getvalue())

    def test_cli_stdout_rejects_being_combined_with_analyze_and_quality_gates(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            svg_path = path.join(tmpdir, "diagram.svg")
            with open(svg_path, "w", encoding="utf-8") as handle:
                handle.write(
                    '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
                    '<rect x="0" y="0" width="10" height="10" fill="red" />'
                    "</svg>"
                )

            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = main.run(svg_path, stdout=True, analyze=True, fail_on_warning=True)

            self.assertEqual(code, 1)
            self.assertEqual(stdout.getvalue(), "")
            self.assertIn("--analyze", stderr.getvalue())
            self.assertIn("--fail-on-warning", stderr.getvalue())

    def test_cli_workers_is_ignored_with_a_note_in_analyze_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            svg_path = path.join(tmpdir, "diagram.svg")
            with open(svg_path, "w", encoding="utf-8") as handle:
                handle.write(
                    '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
                    '<rect x="0" y="0" width="10" height="10" fill="red" />'
                    "</svg>"
                )

            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = main.run(svg_path, analyze=True, workers=4)

            self.assertEqual(code, 0)
            self.assertIn("--workers is ignored in --analyze mode", stderr.getvalue())

    def test_cli_main_reports_a_clean_error_when_no_input_and_stdin_is_not_interactive(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("sys.stdin.isatty", return_value=False), redirect_stdout(stdout), redirect_stderr(stderr):
            code = main.main([])

        self.assertEqual(code, 1)
        self.assertIn("Error: no input path provided.", stderr.getvalue())

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

    def test_cli_analyze_mode_writes_a_structured_report_without_emitting_drawio(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            svg_path = path.join(tmpdir, "diagram.svg")
            report_path = path.join(tmpdir, "report.json")
            with open(svg_path, "w", encoding="utf-8") as handle:
                handle.write(
                    '<svg xmlns="http://www.w3.org/2000/svg" width="120" height="80">'
                    '<defs><clipPath id="cut"><circle cx="40" cy="40" r="20" /></clipPath></defs>'
                    '<rect x="10" y="10" width="60" height="60" fill="red" stroke="black" stroke-width="2" '
                    'clip-path="url(#cut)" />'
                    "</svg>"
                )

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main.main([svg_path, "--analyze", "--report-json", report_path])

            self.assertEqual(code, 0)
            self.assertTrue(path.isfile(report_path))
            self.assertFalse(path.exists(path.splitext(svg_path)[0] + ".drawio"))
            with open(report_path, encoding="utf-8") as handle:
                payload = json.load(handle)
            self.assertEqual(payload["mode"], "analyze")
            self.assertEqual(len(payload["reports"]), 1)
            self.assertEqual(payload["reports"][0]["fallback_count"], 1)
            self.assertIn("compatibility_overview", payload["reports"][0])
            self.assertIn("compatibility_matrix", payload["reports"][0])
            self.assertIn("Compatibility:", stdout.getvalue())
            self.assertIn("score", stdout.getvalue())

    def test_cli_exposes_gradient_policy_flags(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            svg_path = path.join(tmpdir, "diagram.svg")
            out_path = path.join(tmpdir, "diagram.drawio")
            with open(svg_path, "w", encoding="utf-8") as handle:
                handle.write(
                    '<svg xmlns="http://www.w3.org/2000/svg" width="160" height="100">'
                    "<defs>"
                    '<linearGradient id="multi" x1="0" y1="0" x2="1" y2="0">'
                    '<stop offset="0%" stop-color="#e53935" />'
                    '<stop offset="35%" stop-color="#fb8c00" />'
                    '<stop offset="70%" stop-color="#fdd835" />'
                    '<stop offset="100%" stop-color="#1e88e5" />'
                    "</linearGradient>"
                    "</defs>"
                    '<rect x="10" y="15" width="120" height="50" rx="12" '
                    'fill="url(#multi)" stroke="#263238" stroke-width="2" />'
                    "</svg>"
                )

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main.main([svg_path, "--overwrite", "--gradient-policy", "prefer-fallback"])

            self.assertEqual(code, 0)
            root = ET.parse(out_path).getroot()
            self.assertTrue(any(self._style_map(cell).get("shape") == "image" for cell in self._user_cells(root)))

    def test_cli_rendering_preset_matches_fidelity_preset_behavior(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            svg_path = path.join(tmpdir, "diagram.svg")
            out_path = path.join(tmpdir, "diagram.drawio")
            with open(svg_path, "w", encoding="utf-8") as handle:
                handle.write(
                    '<svg xmlns="http://www.w3.org/2000/svg" width="160" height="100">'
                    "<defs>"
                    '<linearGradient id="multi" x1="0" y1="0" x2="1" y2="0">'
                    '<stop offset="0%" stop-color="#e53935" />'
                    '<stop offset="35%" stop-color="#fb8c00" />'
                    '<stop offset="70%" stop-color="#fdd835" />'
                    '<stop offset="100%" stop-color="#1e88e5" />'
                    "</linearGradient>"
                    "</defs>"
                    '<rect x="10" y="15" width="120" height="50" rx="12" '
                    'fill="url(#multi)" stroke="#263238" stroke-width="2" />'
                    "</svg>"
                )

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main.main([svg_path, "--overwrite", "--rendering-preset", "fidelity"])

            self.assertEqual(code, 0)
            root = ET.parse(out_path).getroot()
            self.assertTrue(any(self._style_map(cell).get("shape") == "image" for cell in self._user_cells(root)))
            self.assertIn("Rendering preset: Best visual fidelity", stdout.getvalue())

    def test_cli_explicit_policy_can_override_rendering_preset(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            svg_path = path.join(tmpdir, "diagram.svg")
            out_path = path.join(tmpdir, "diagram.drawio")
            with open(svg_path, "w", encoding="utf-8") as handle:
                handle.write(
                    '<svg xmlns="http://www.w3.org/2000/svg" width="160" height="100">'
                    "<defs>"
                    '<linearGradient id="multi" x1="0" y1="0" x2="1" y2="0">'
                    '<stop offset="0%" stop-color="#e53935" />'
                    '<stop offset="35%" stop-color="#fb8c00" />'
                    '<stop offset="70%" stop-color="#fdd835" />'
                    '<stop offset="100%" stop-color="#1e88e5" />'
                    "</linearGradient>"
                    "</defs>"
                    '<rect x="10" y="15" width="120" height="50" rx="12" '
                    'fill="url(#multi)" stroke="#263238" stroke-width="2" />'
                    "</svg>"
                )

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main.main(
                    [
                        svg_path,
                        "--overwrite",
                        "--rendering-preset",
                        "fidelity",
                        "--gradient-policy",
                        "prefer-native",
                    ]
                )

            self.assertEqual(code, 0)
            root = ET.parse(out_path).getroot()
            self.assertFalse(any(self._style_map(cell).get("shape") == "image" for cell in self._user_cells(root)))
            self.assertIn("Rendering preset: Custom", stdout.getvalue())
