"""Integration tests for the shared conversion service."""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
import unittest
from os import path
from unittest import mock

from svg_to_drawio.conversion_service import (
    CancellationToken,
    ConversionEvent,
    ConversionEventKind,
    ConversionOptions,
    ConversionService,
    event_watch_available,
    resolve_watch_backend,
    watch_svg_files,
)
from svg_to_drawio.post_process import PostProcessOptions

from tests.helpers import SvgTestCase

_SVG_TEMPLATE = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
    '<rect x="0" y="0" width="10" height="10" fill="{color}" /></svg>'
)


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

    def test_parallel_conversion_keeps_every_entry_in_the_shared_cache_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            input_dir = path.join(tmpdir, "input")
            output_dir = path.join(tmpdir, "out")
            os.makedirs(input_dir, exist_ok=True)
            for name in ("one.svg", "two.svg", "three.svg", "four.svg"):
                with open(path.join(input_dir, name), "w", encoding="utf-8") as handle:
                    handle.write(_SVG_TEMPLATE.format(color="#ff0000"))

            summary = ConversionService().convert_parallel(
                [input_dir],
                ConversionOptions(output_dir=output_dir, overwrite=True, use_cache=True),
                max_workers=4,
            )

            self.assertEqual(summary.converted, 4)
            with open(path.join(output_dir, ".svg-to-drawio-cache.json"), encoding="utf-8") as handle:
                payload = json.load(handle)
            self.assertEqual(len(payload["entries"]), 4)

    def test_merge_pages_writes_a_combined_file_and_emits_progress_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            for name in ("one.svg", "two.svg"):
                with open(path.join(tmpdir, name), "w", encoding="utf-8") as handle:
                    handle.write(
                        '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
                        '<rect x="0" y="0" width="10" height="10" fill="red" />'
                        "</svg>"
                    )
            merged_path = path.join(tmpdir, "merged.drawio")
            events: list[ConversionEvent] = []

            summary = ConversionService().merge(
                [tmpdir],
                ConversionOptions(),
                mode="pages",
                output_path=merged_path,
                reporter=events.append,
            )

            self.assertEqual(summary.converted, 2)
            self.assertEqual(summary.failed, 0)
            self.assertTrue(path.isfile(merged_path))
            self.assertIn(ConversionEventKind.COMPLETED, {event.kind for event in events})

    def test_merge_respects_overwrite_for_an_existing_combined_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            svg_path = path.join(tmpdir, "one.svg")
            with open(svg_path, "w", encoding="utf-8") as handle:
                handle.write(_SVG_TEMPLATE.format(color="#ff0000"))
            merged_path = path.join(tmpdir, "merged.drawio")
            with open(merged_path, "w", encoding="utf-8") as handle:
                handle.write("sentinel")

            skipped = ConversionService().merge(
                [svg_path],
                ConversionOptions(overwrite=False),
                mode="pages",
                output_path=merged_path,
            )
            with open(merged_path, encoding="utf-8") as handle:
                self.assertEqual(handle.read(), "sentinel")
            self.assertEqual(skipped.skipped, 1)

            converted = ConversionService().merge(
                [svg_path],
                ConversionOptions(overwrite=True),
                mode="pages",
                output_path=merged_path,
            )
            with open(merged_path, encoding="utf-8") as handle:
                self.assertIn("<mxfile>", handle.read())
            self.assertEqual(converted.converted, 1)

    def test_merge_grid_records_a_failure_without_aborting_the_rest(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(path.join(tmpdir, "good.svg"), "w", encoding="utf-8") as handle:
                handle.write(
                    '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
                    '<rect x="0" y="0" width="10" height="10" fill="red" />'
                    "</svg>"
                )
            with open(path.join(tmpdir, "bad.svg"), "w", encoding="utf-8") as handle:
                handle.write("<svg")
            merged_path = path.join(tmpdir, "merged.drawio")

            summary = ConversionService().merge(
                [tmpdir],
                ConversionOptions(),
                mode="grid",
                output_path=merged_path,
            )

            self.assertEqual(summary.converted, 1)
            self.assertEqual(summary.failed, 1)
            self.assertTrue(path.isfile(merged_path))

    def test_merge_grid_applies_post_process_once_to_the_combined_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            for name in ("one.svg", "two.svg"):
                with open(path.join(tmpdir, name), "w", encoding="utf-8") as handle:
                    handle.write(
                        '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
                        '<rect x="0" y="0" width="10" height="10" fill="red" />'
                        "</svg>"
                    )
            merged_path = path.join(tmpdir, "merged.drawio")

            ConversionService().merge(
                [tmpdir],
                ConversionOptions(post_process=PostProcessOptions(legend=True)),
                mode="grid",
                output_path=merged_path,
            )

            with open(merged_path, encoding="utf-8") as handle:
                xml_text = handle.read()
            self.assertEqual(xml_text.count('value="Notes"'), 1)

    def test_merge_cancellation_stops_before_the_next_source_and_writes_partial_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            for name in ("one.svg", "two.svg"):
                with open(path.join(tmpdir, name), "w", encoding="utf-8") as handle:
                    handle.write(_SVG_TEMPLATE.format(color="#ff0000"))

            token = CancellationToken()
            events: list[ConversionEvent] = []

            def report(event: ConversionEvent) -> None:
                events.append(event)
                if event.kind == ConversionEventKind.CONVERTED:
                    token.cancel()

            merged_path = path.join(tmpdir, "merged.drawio")
            summary = ConversionService().merge(
                [tmpdir],
                ConversionOptions(),
                mode="pages",
                output_path=merged_path,
                reporter=report,
                cancellation_token=token,
            )

            self.assertTrue(summary.cancelled)
            self.assertEqual(summary.converted, 1)
            self.assertEqual(summary.total, 2)
            with open(merged_path, encoding="utf-8") as handle:
                self.assertEqual(handle.read().count("<diagram"), 1)
            self.assertIn(ConversionEventKind.CANCELLED, {event.kind for event in events})

    def test_poll_watch_preserves_post_process_options_on_the_initial_conversion(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            svg_path = path.join(tmpdir, "diagram.svg")
            with open(svg_path, "w", encoding="utf-8") as handle:
                handle.write(_SVG_TEMPLATE.format(color="#ff0000"))

            stop_event = threading.Event()
            stop_event.set()
            watch_svg_files(
                [svg_path],
                ConversionOptions(
                    overwrite=True,
                    post_process=PostProcessOptions(legend=True, background="#112233"),
                ),
                stop_event=stop_event,
                backend="poll",
            )

            with open(path.join(tmpdir, "diagram.drawio"), encoding="utf-8") as handle:
                xml_text = handle.read()
            self.assertIn('value="Notes"', xml_text)
            self.assertIn('background="#112233"', xml_text)


class WatchBackendResolutionTests(SvgTestCase):
    """Exercise the auto/poll/event watch-backend resolution logic in isolation."""

    def test_poll_is_always_available(self) -> None:
        self.assertEqual(resolve_watch_backend("poll"), "poll")

    def test_event_backend_raises_when_watchdog_is_unavailable(self) -> None:
        with mock.patch("svg_to_drawio.conversion_service.event_watch_available", return_value=False):
            with self.assertRaises(RuntimeError):
                resolve_watch_backend("event")

    def test_event_backend_resolves_when_watchdog_is_available(self) -> None:
        with mock.patch("svg_to_drawio.conversion_service.event_watch_available", return_value=True):
            self.assertEqual(resolve_watch_backend("event"), "event")

    def test_auto_falls_back_to_poll_without_watchdog(self) -> None:
        with mock.patch("svg_to_drawio.conversion_service.event_watch_available", return_value=False):
            self.assertEqual(resolve_watch_backend("auto"), "poll")

    def test_auto_prefers_event_when_watchdog_is_available(self) -> None:
        with mock.patch("svg_to_drawio.conversion_service.event_watch_available", return_value=True):
            self.assertEqual(resolve_watch_backend("auto"), "event")

    def test_event_watch_available_reflects_real_watchdog_installation(self) -> None:
        # Sanity-checks the real (unmocked) probe against this environment instead of
        # only ever exercising the mocked branches above.
        self.assertIsInstance(event_watch_available(), bool)


@unittest.skipUnless(event_watch_available(), "watchdog is not installed in this environment")
class EventDrivenWatchTests(SvgTestCase):
    """End-to-end exercise of the real watchdog-backed watch loop, not just its resolution."""

    def _wait_until(self, predicate: object, timeout: float = 10.0, interval: float = 0.1) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():  # type: ignore[operator]
                return True
            time.sleep(interval)
        return False

    def test_event_backend_reconverts_on_file_modification(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            svg_path = path.join(tmpdir, "diagram.svg")
            out_path = path.join(tmpdir, "diagram.drawio")
            with open(svg_path, "w", encoding="utf-8") as handle:
                handle.write(_SVG_TEMPLATE.format(color="#ff0000"))

            stop_event = threading.Event()
            thread = threading.Thread(
                target=watch_svg_files,
                args=([svg_path], ConversionOptions(overwrite=True)),
                kwargs={"backend": "event", "stop_event": stop_event},
                daemon=True,
            )
            thread.start()
            try:
                initial_ready = self._wait_until(lambda: path.isfile(out_path))
                self.assertTrue(initial_ready, "initial conversion never produced an output file")
                first_mtime = os.stat(out_path).st_mtime_ns

                time.sleep(0.2)  # ensure the modification below lands after the initial pass
                with open(svg_path, "w", encoding="utf-8") as handle:
                    handle.write(_SVG_TEMPLATE.format(color="#00ff00"))

                reconverted = self._wait_until(lambda: os.stat(out_path).st_mtime_ns != first_mtime)
                self.assertTrue(reconverted, "file modification was not picked up by the event watcher")

                with open(out_path, encoding="utf-8") as handle:
                    self.assertIn("#00FF00".lower(), handle.read().lower())
            finally:
                stop_event.set()
                thread.join(timeout=5.0)
                self.assertFalse(thread.is_alive(), "watcher thread did not stop after stop_event was set")
