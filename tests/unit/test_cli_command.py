"""Tests for the desktop app's "Copy CLI Command" builder (no Qt dependency)."""

from __future__ import annotations

import unittest

from svg_to_drawio.rendering_options import RenderingOptions
from svg_to_drawio_desktop.cli_command import CliCommandOptions, build_equivalent_cli_command


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
        self.assertIn('--merge-output "out/merged.drawio"', command)
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
        self.assertIn('--background-color "#FFFFFF"', command)
