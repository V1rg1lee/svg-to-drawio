"""Regression tests for desktop bundle naming and macOS build targeting."""

from __future__ import annotations

import unittest
from unittest.mock import patch

import build_desktop


class BuildDesktopTests(unittest.TestCase):
    """Verify platform-specific desktop bundle defaults."""

    def test_default_name_is_cli_friendly_off_macos(self) -> None:
        """Non-macOS platforms keep the package-style executable name."""
        with patch.object(build_desktop.platform, "system", return_value="Windows"):
            self.assertEqual(build_desktop._resolve_app_name(), "svg-to-drawio")

    def test_macos_name_is_human_friendly(self) -> None:
        """macOS uses a Finder-friendly app bundle name without hyphens."""
        with patch.object(build_desktop.platform, "system", return_value="Darwin"):
            self.assertEqual(build_desktop._resolve_app_name(), "SVG to draw.io")

    def test_macos_auto_target_arch_defaults_to_universal2(self) -> None:
        """macOS auto-targeting should produce one universal build for Intel and ARM."""
        with patch.object(build_desktop.platform, "system", return_value="Darwin"):
            self.assertEqual(build_desktop._resolve_macos_target_arch("auto"), "universal2")

    def test_non_macos_ignores_macos_target_arch(self) -> None:
        """Non-macOS builds should not emit a PyInstaller macOS target override."""
        with patch.object(build_desktop.platform, "system", return_value="Linux"):
            self.assertIsNone(build_desktop._resolve_macos_target_arch("universal2"))


if __name__ == "__main__":
    unittest.main()
