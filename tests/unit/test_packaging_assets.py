"""Regression tests for packaging assets used by release builds."""

from __future__ import annotations

import struct
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
APP_ICON_PNG = REPO_ROOT / "svg_to_drawio_desktop" / "assets" / "app_logo_256x256.png"


def _read_png_size(path: Path) -> tuple[int, int]:
    """Return the PNG width and height from its IHDR chunk."""
    with path.open("rb") as handle:
        signature = handle.read(8)
        if signature != b"\x89PNG\r\n\x1a\n":
            raise AssertionError(f"{path} is not a valid PNG file.")

        chunk_length = struct.unpack(">I", handle.read(4))[0]
        chunk_type = handle.read(4)
        if chunk_type != b"IHDR":
            raise AssertionError(f"{path} does not start with an IHDR chunk.")
        if chunk_length < 8:
            raise AssertionError(f"{path} has an invalid IHDR chunk length.")

        width, height = struct.unpack(">II", handle.read(8))
        return width, height


class PackagingAssetTests(unittest.TestCase):
    """Validate binary assets required by desktop packaging workflows."""

    def test_linux_application_icon_is_square_256_png(self) -> None:
        """The Linux application icon must be a real 256x256 PNG for AppStream/Flatpak."""
        self.assertTrue(APP_ICON_PNG.is_file(), f"Missing packaging icon: {APP_ICON_PNG}")
        self.assertEqual(_read_png_size(APP_ICON_PNG), (256, 256))


if __name__ == "__main__":
    unittest.main()
