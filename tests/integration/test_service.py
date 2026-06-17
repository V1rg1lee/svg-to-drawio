"""Integration tests for the shared conversion service."""

from __future__ import annotations

import os
import tempfile
from os import path

from svg_to_drawio.conversion_service import (
    CancellationToken,
    ConversionEvent,
    ConversionEventKind,
    ConversionOptions,
    ConversionService,
)

from tests.helpers import SvgTestCase


class ConversionServiceTests(SvgTestCase):
    """Exercise the reusable file-and-directory conversion service."""

    def test_multi_root_output_dir_namespaces_and_dedupes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root_a = path.join(tmpdir, "alpha")
            root_b = path.join(tmpdir, "beta")
            output_dir = path.join(tmpdir, "out")

            os_path_alpha = path.join(root_a, "diagram.svg")
            os_path_beta = path.join(root_b, "diagram.svg")
            for parent, svg_path in ((root_a, os_path_alpha), (root_b, os_path_beta)):
                os.makedirs(parent, exist_ok=True)
                with open(svg_path, "w", encoding="utf-8") as handle:
                    handle.write(
                        '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
                        '<rect x="0" y="0" width="10" height="10" fill="red" />'
                        "</svg>"
                    )

            jobs = ConversionService().plan(
                [root_a, root_b],
                ConversionOptions(output_dir=output_dir, recursive=False, overwrite=True),
            )

            self.assertEqual(len(jobs), 2)
            self.assertEqual(
                {job.output_path for job in jobs},
                {
                    path.join(output_dir, "alpha", "diagram.drawio"),
                    path.join(output_dir, "beta", "diagram.drawio"),
                },
            )

    def test_cancellation_stops_before_processing_the_next_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            input_dir = path.join(tmpdir, "input")
            output_dir = path.join(tmpdir, "out")
            os.makedirs(input_dir, exist_ok=True)

            for name in ("one.svg", "two.svg"):
                with open(path.join(input_dir, name), "w", encoding="utf-8") as handle:
                    handle.write(
                        '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
                        '<rect x="0" y="0" width="10" height="10" fill="red" />'
                        "</svg>"
                    )

            token = CancellationToken()
            events: list[ConversionEvent] = []

            def report(event: ConversionEvent) -> None:
                events.append(event)
                if event.kind == ConversionEventKind.CONVERTED:
                    token.cancel()

            summary = ConversionService().convert(
                [input_dir],
                ConversionOptions(output_dir=output_dir, overwrite=True),
                reporter=report,
                cancellation_token=token,
            )

            self.assertTrue(summary.cancelled)
            self.assertEqual(summary.converted, 1)
            self.assertEqual(summary.total, 2)
            self.assertTrue(path.exists(path.join(output_dir, "one.drawio")))
            self.assertFalse(path.exists(path.join(output_dir, "two.drawio")))
            self.assertIn(ConversionEventKind.CANCELLED, {event.kind for event in events})

    def test_persistent_cache_skips_unchanged_inputs_on_the_second_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            svg_path = path.join(tmpdir, "diagram.svg")
            out_path = path.join(tmpdir, "diagram.drawio")
            with open(svg_path, "w", encoding="utf-8") as handle:
                handle.write(
                    '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
                    '<rect x="0" y="0" width="10" height="10" fill="red" />'
                    "</svg>"
                )

            service = ConversionService()
            first = service.convert([svg_path], ConversionOptions(overwrite=True, use_cache=True))
            second = service.convert([svg_path], ConversionOptions(overwrite=True, use_cache=True))

            self.assertEqual(first.converted, 1)
            self.assertEqual(second.converted, 0)
            self.assertEqual(second.skipped, 1)
            self.assertTrue(path.isfile(out_path))
            self.assertTrue(second.reports)
            self.assertTrue(second.reports[0].cached)
