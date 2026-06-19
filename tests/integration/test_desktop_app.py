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
import unittest


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
