"""Shared helpers for SVG-to-draw.io tests."""

from __future__ import annotations

import base64
import re
import unittest
import xml.etree.ElementTree as ET
import zlib
from os import makedirs, path
from urllib.parse import unquote

from svg_to_drawio import convert_file

TESTS_DIR = path.dirname(path.abspath(__file__))
FIXTURES_DIR = path.join(TESTS_DIR, "fixtures")


class SvgTestCase(unittest.TestCase):
    """Test case with helpers for converting SVG snippets and inspecting draw.io output."""

    def _convert_in_dir(
        self,
        tmpdir: str,
        svg_text: str,
        rel_path: str = "diagram.svg",
        out_path: str | None = None,
    ) -> tuple[ET.Element, str]:
        """Write an SVG fixture, convert it, and return the parsed output root plus path."""
        svg_path = path.join(tmpdir, rel_path)
        makedirs(path.dirname(svg_path), exist_ok=True)
        with open(svg_path, "w", encoding="utf-8") as handle:
            handle.write(svg_text)
        target_path = out_path or path.splitext(svg_path)[0] + ".drawio"
        convert_file(svg_path, out_path=target_path)
        return ET.parse(target_path).getroot(), target_path

    def _user_cells(self, root: ET.Element) -> list[ET.Element]:
        """Return all non-root draw.io cells emitted by the converter."""
        return [cell for cell in root.findall(".//mxCell") if cell.get("id") not in ("0", "1")]

    def _style_map(self, cell: ET.Element) -> dict[str, str | bool]:
        """Parse a semicolon-delimited draw.io style string into a dictionary."""
        styles: dict[str, str | bool] = {}
        for fragment in (cell.get("style") or "").split(";"):
            if not fragment:
                continue
            if "=" in fragment:
                key, value = fragment.split("=", 1)
                styles[key] = value
            else:
                styles[fragment] = True
        return styles

    def _decode_stencil_xml(self, cell: ET.Element) -> str:
        """Decode the embedded XML payload from a stencil-style cell."""
        match = re.search(r"shape=stencil\(([^)]+)\)", cell.get("style", ""))
        self.assertIsNotNone(match)
        assert match is not None
        compressed = base64.b64decode(match.group(1))
        quoted = zlib.decompress(compressed, wbits=-15).decode("utf-8")
        return unquote(quoted)
