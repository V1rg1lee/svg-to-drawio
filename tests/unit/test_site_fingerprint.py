"""Regression tests for static site fingerprint generation."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.site_fingerprint import fingerprint_directory

from tests.helpers import SvgTestCase


class SiteFingerprintTests(SvgTestCase):
    """Keep site fingerprinting deterministic and content-sensitive."""

    def test_fingerprint_is_order_independent(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "b.txt").write_text("beta\n", encoding="utf-8")
            (root / "nested").mkdir()
            (root / "nested" / "a.txt").write_text("alpha\n", encoding="utf-8")

            first = fingerprint_directory(root)
            second = fingerprint_directory(root)

        self.assertEqual(first, second)

    def test_fingerprint_changes_when_file_content_changes(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "index.html").write_text("<h1>Hello</h1>\n", encoding="utf-8")
            baseline = fingerprint_directory(root)

            (root / "index.html").write_text("<h1>Hello world</h1>\n", encoding="utf-8")
            changed = fingerprint_directory(root)

        self.assertNotEqual(baseline, changed)
