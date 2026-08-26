"""Tests for the desktop app's "Copy CLI Command" builder (no Qt dependency)."""

from __future__ import annotations

import shlex
import unittest
from unittest.mock import patch

from svg_to_drawio.rendering_options import RenderingOptions
from svg_to_drawio_desktop.cli_command import (
    CliCommandOptions,
    build_cli_argv,
    build_equivalent_cli_command,
    quote_powershell_arg,
    render_powershell_command,
)


def _base_options(**overrides: object) -> CliCommandOptions:
    defaults: dict[str, object] = dict(
        sources=("diagram.svg",),
        output_dir=None,
        recursive=False,
        overwrite=False,
        flatten=False,
        watch=False,
        use_cache=True,
        max_elements=None,
        workers=1,
        preset="balanced",
        rendering_options=RenderingOptions(),
    )
    defaults.update(overrides)
    return CliCommandOptions(**defaults)  # type: ignore[arg-type]


class CliArgvTests(unittest.TestCase):
    """Build shell-independent arguments without changing option behavior."""

    def test_merge_pages_includes_mode_and_output(self) -> None:
        argv = build_cli_argv(_base_options(merge="pages", merge_output="out/merged.drawio"))
        self.assertEqual(
            argv,
            ["svg-to-drawio", "diagram.svg", "--merge", "pages", "--merge-output", "out/merged.drawio"],
        )

    def test_all_existing_option_groups_are_preserved(self) -> None:
        options = _base_options(
            sources=("one.svg", "two.svg"),
            output_dir="out dir",
            recursive=True,
            overwrite=True,
            flatten=True,
            watch=False,
            use_cache=False,
            max_elements=42,
            workers=3,
            merge="grid",
            merge_output="merged.drawio",
            grid_columns=2,
            legend=True,
            background_color="#FFFFFF",
            preset="fidelity",
        )
        self.assertEqual(
            build_cli_argv(options),
            [
                "svg-to-drawio",
                "one.svg",
                "two.svg",
                "--output-dir",
                "out dir",
                "--recursive",
                "--overwrite",
                "--flatten",
                "--no-cache",
                "--max-elements",
                "42",
                "--workers",
                "3",
                "--merge",
                "grid",
                "--merge-output",
                "merged.drawio",
                "--grid-columns",
                "2",
                "--legend",
                "--background-color",
                "#FFFFFF",
                "--rendering-preset",
                "fidelity",
            ],
        )

    def test_watch_still_omits_workers(self) -> None:
        argv = build_cli_argv(_base_options(watch=True, workers=4))
        self.assertIn("--watch", argv)
        self.assertNotIn("--workers", argv)


class PosixCommandTests(unittest.TestCase):
    """POSIX commands must round-trip every untrusted value as one literal argument."""

    def test_special_source_values_round_trip_with_shlex(self) -> None:
        values = (
            "$(touch /tmp/marker)",
            "`touch /tmp/marker`",
            "$HOME/evil",
            "file.svg; rm -rf /",
            "file.svg | cat",
            "file.svg && whoami",
            "file.svg > /tmp/output",
            "path with spaces.svg",
            "path'with'apostrophes.svg",
            'path"with"quotes.svg',
            r"path\with\backslashes.svg",
        )
        for value in values:
            with self.subTest(value=value):
                command = build_equivalent_cli_command(_base_options(sources=(value,)), shell="posix")
                self.assertEqual(shlex.split(command), ["svg-to-drawio", value])

    def test_all_user_controlled_fields_round_trip(self) -> None:
        options = _base_options(
            sources=("source $(whoami); ' file.svg",),
            output_dir="output | $(id)",
            merge="pages",
            merge_output="merged; ' $(id).drawio",
            background_color="color | ' $(id)",
        )
        self.assertEqual(shlex.split(build_equivalent_cli_command(options, shell="posix")), build_cli_argv(options))

    def test_normal_command_does_not_require_artificial_quotes(self) -> None:
        options = _base_options(merge="pages", merge_output="out/merged.drawio")
        command = build_equivalent_cli_command(options, shell="posix")
        self.assertEqual(shlex.split(command), build_cli_argv(options))
        self.assertEqual(command, "svg-to-drawio diagram.svg --merge pages --merge-output out/merged.drawio")


class PowerShellCommandTests(unittest.TestCase):
    """PowerShell rendering must use literal single-quoted arguments."""

    def test_quote_powershell_arg_preserves_literal_values(self) -> None:
        cases = {
            "": "''",
            "hello": "'hello'",
            "my diagram.svg": "'my diagram.svg'",
            "$(whoami)": "'$(whoami)'",
            "$HOME": "'$HOME'",
            "`whoami`": "'`whoami`'",
            "a;b": "'a;b'",
            "a|b": "'a|b'",
            "a&b": "'a&b'",
            "Virgile's file.svg": "'Virgile''s file.svg'",
            'path"with"quotes.svg': "'path\"with\"quotes.svg'",
            r"path\with\backslashes.svg": r"'path\with\backslashes.svg'",
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(quote_powershell_arg(value), expected)

    def test_windows_paths_are_preserved_and_single_quoted(self) -> None:
        paths = (
            r"C:\Users\Virgile\diagram.svg",
            r"C:\Users\Virgile\My Diagram.svg",
            r"C:\Users\O'Brien\diagram.svg",
            r"C:\Temp\$(whoami)\diagram.svg",
        )
        for windows_path in paths:
            with self.subTest(path=windows_path):
                rendered = render_powershell_command(["svg-to-drawio", windows_path])
                self.assertEqual(rendered, f"svg-to-drawio {quote_powershell_arg(windows_path)}")

    def test_every_argument_after_program_is_quoted(self) -> None:
        options = _base_options(
            sources=("source $(whoami); ' file.svg",),
            output_dir="output | $(id)",
            merge="pages",
            merge_output="merged; ' $(id).drawio",
            background_color="color & ' $(id)",
        )
        argv = build_cli_argv(options)
        expected = " ".join([argv[0], *(quote_powershell_arg(arg) for arg in argv[1:])])
        self.assertEqual(build_equivalent_cli_command(options, shell="powershell"), expected)

    def test_windows_platform_defaults_to_powershell(self) -> None:
        options = _base_options(sources=("$(whoami)",))
        with patch("svg_to_drawio_desktop.cli_command.os.name", "nt"):
            command = build_equivalent_cli_command(options)
        self.assertEqual(command, "svg-to-drawio '$(whoami)'")


if __name__ == "__main__":
    unittest.main()
