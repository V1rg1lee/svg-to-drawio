"""Regression tests for desktop bundle naming and macOS build targeting."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
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

    def test_macos_app_icon_prefers_dedicated_bundle_icon(self) -> None:
        """The app bundle icon should come from the app-specific asset when provided."""
        with tempfile.TemporaryDirectory() as tmp:
            assets_dir = Path(tmp) / "assets"
            build_root = Path(tmp) / "build"
            assets_dir.mkdir()
            bundle_icon = assets_dir / "app_bundle.icns"
            bundle_icon.write_bytes(b"icns")
            (assets_dir / "VolumeIcon.icns").write_bytes(b"dmg")

            resolved = build_desktop._resolve_macos_app_icon_path(assets_dir, build_root)

            self.assertEqual(resolved, bundle_icon)

    def test_macos_app_icon_falls_back_to_generated_icns(self) -> None:
        """The app icon should be generated from the PNG when no bundle .icns exists."""
        with tempfile.TemporaryDirectory() as tmp:
            assets_dir = Path(tmp) / "assets"
            build_root = Path(tmp) / "build"
            assets_dir.mkdir()
            (assets_dir / "app_logo_256x256.png").write_bytes(b"png")

            generated_path = build_root / "app_logo.icns"
            with patch.object(build_desktop, "_generate_icns", return_value=True):
                resolved = build_desktop._resolve_macos_app_icon_path(assets_dir, build_root)

            self.assertEqual(resolved, generated_path)


if __name__ == "__main__":
    unittest.main()
