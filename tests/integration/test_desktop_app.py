"""Smoke tests that actually construct the desktop GUI's main window.

Nothing else in the suite ever imports `svg_to_drawio_desktop.app`, so a broken
import or a crash in `MainWindow.__init__` could ship undetected. These tests
exercise the desktop app headlessly (Qt's "offscreen" platform plugin) and are
skipped when PySide6 isn't installed, matching the optional-dependency pattern
already used for the watchdog-backed watch tests.
"""

from __future__ import annotations

import importlib.util
import os
import tempfile
import time
import unittest
from pathlib import Path

_MINIMAL_SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><rect width="10" height="10"/></svg>'


def _pyside6_available() -> bool:
    """Return whether the optional PySide6 desktop dependency is installed."""
    try:
        return importlib.util.find_spec("PySide6.QtWidgets") is not None
    except ModuleNotFoundError:
        # find_spec("pkg.submodule") raises instead of returning None when the
        # parent package itself ("PySide6") isn't installed at all.
        return False


@unittest.skipUnless(_pyside6_available(), "PySide6 is not installed in this environment")
class DesktopAppSmokeTests(unittest.TestCase):
    """Construct the real MainWindow class instead of just its conversion backend."""

    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

        from PySide6.QtCore import QCoreApplication
        from PySide6.QtWidgets import QApplication

        # Use a dedicated org/app name so QSettings() reads/writes an isolated
        # location instead of the real user's saved desktop-app preferences.
        QCoreApplication.setOrganizationName("svg-to-drawio-tests")
        QCoreApplication.setApplicationName("svg-to-drawio-desktop-tests")
        cls.app = QApplication.instance() or QApplication([])

    @classmethod
    def tearDownClass(cls) -> None:
        from PySide6.QtCore import QSettings

        QSettings().clear()

    def test_main_window_constructs_without_crashing(self) -> None:
        from svg_to_drawio_desktop.app import MainWindow

        window = MainWindow()
        self.addCleanup(window.close)
        self.assertIsNotNone(window)

    def test_main_window_does_not_crash_on_a_stale_persisted_preset(self) -> None:
        from PySide6.QtCore import QSettings
        from svg_to_drawio_desktop.app import MainWindow

        QSettings().setValue("rendering/preset", "legacy-preset-removed-in-a-later-version")
        window = MainWindow()
        self.addCleanup(window.close)
        self.assertIsNotNone(window)

    def test_show_plain_text_dialog_never_interprets_content_as_rich_text(self) -> None:
        from unittest.mock import patch

        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QMessageBox
        from svg_to_drawio_desktop.app import MainWindow

        window = MainWindow()
        self.addCleanup(window.close)

        captured: list[QMessageBox] = []

        def fake_exec(box: QMessageBox) -> int:
            captured.append(box)
            return 0

        # SVG element ids/tags/messages are attacker- or author-controlled and end up in
        # these dialogs; without forcing plain text, Qt's mightBeRichText() heuristic could
        # misrender something that merely looks like a tag, e.g. an id of "<script>".
        svg_derived_text = "Source id: <script>alert(1)</script>"
        with patch.object(QMessageBox, "exec", fake_exec):
            window._show_plain_text_dialog(QMessageBox.Icon.Information, "Detail", svg_derived_text)

        self.assertEqual(len(captured), 1)
        self.assertEqual(captured[0].textFormat(), Qt.TextFormat.PlainText)
        self.assertEqual(captured[0].text(), svg_derived_text)

    def test_conversion_runs_through_worker_thread_and_updates_ui(self) -> None:
        """Drive a real conversion through the worker thread and Qt signal pipeline.

        Everything else in this file only checks that the window constructs. This
        exercises the path most likely to silently regress: the worker thread emits
        signals from a background `QThread`, and the GUI thread must drain its event
        loop (`processEvents`) for `_handle_event`/`_handle_finished` to ever run.
        """
        from PySide6.QtWidgets import QApplication
        from svg_to_drawio_desktop.app import MainWindow

        window = MainWindow()
        self.addCleanup(window.close)

        with tempfile.TemporaryDirectory() as tmp_dir:
            source_path = Path(tmp_dir) / "sample.svg"
            source_path.write_text(_MINIMAL_SVG, encoding="utf-8")
            output_dir = Path(tmp_dir) / "out"
            output_dir.mkdir()

            window._add_paths([str(source_path)])
            window.convert_page.output_dir_edit.setText(str(output_dir))
            window._start_conversion()

            deadline = time.monotonic() + 10.0
            while window._worker is not None or window._thread is not None:
                if time.monotonic() > deadline:
                    self.fail("Conversion did not finish through the worker thread in time")
                QApplication.processEvents()

            self.assertEqual(window._converted, 1)
            self.assertEqual(window._failed, 0)
            self.assertEqual(len(window._last_reports), 1)
            self.assertIn("1 converted", window.results_page.summary_label.text())
            self.assertTrue((output_dir / "sample.drawio").is_file())
