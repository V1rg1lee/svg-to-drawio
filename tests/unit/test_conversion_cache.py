"""Security and regression tests for the persistent conversion cache."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from svg_to_drawio.conversion_cache import ConversionCache
from svg_to_drawio.diagnostics import ConversionReport


class ConversionCacheTests(unittest.TestCase):
    """Treat fingerprint paths loaded from the manifest as untrusted input."""

    def _write_valid_cache(
        self,
        trusted_dir: Path,
        *,
        source_name: str = "diagram.svg",
        dependency_name: str = "assets/image.png",
    ) -> tuple[Path, Path, Path, Path]:
        source = trusted_dir / source_name
        dependency = trusted_dir / dependency_name
        output = trusted_dir / "diagram.drawio"
        manifest = trusted_dir / ".svg-to-drawio-cache.json"
        source.parent.mkdir(parents=True, exist_ok=True)
        dependency.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("<svg/>", encoding="utf-8")
        dependency.write_bytes(b"asset")
        output.write_text("<mxfile/>", encoding="utf-8")
        report = ConversionReport(source_path=str(source), output_path=str(output), dependencies=[str(dependency)])
        ConversionCache(str(manifest)).update(
            str(source),
            str(output),
            options_signature="options",
            report=report,
        )
        return source, dependency, output, manifest

    def _replace_dependency_path(self, manifest: Path, replacement: str) -> None:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        entry = next(iter(payload["entries"].values()))
        entry["fingerprints"][1]["path"] = replacement
        manifest.write_text(json.dumps(payload), encoding="utf-8")

    def _cached_report(self, manifest: Path, source: Path, output: Path) -> ConversionReport | None:
        return ConversionCache(str(manifest)).get_cached_report(
            str(source),
            str(output),
            options_signature="options",
        )

    def test_valid_local_dependency_and_double_dot_names_are_cached(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            trusted = Path(tmpdir) / "trusted"
            source, _, output, manifest = self._write_valid_cache(
                trusted,
                source_name="diagram..final.svg",
                dependency_name="assets/image..final.png",
            )

            cached = self._cached_report(manifest, source, output)

            self.assertIsNotNone(cached)
            self.assertTrue(cached.cached if cached is not None else False)

    def test_absolute_external_fingerprint_is_rejected_before_hashing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            source, _, output, manifest = self._write_valid_cache(base / "trusted")
            outside = base / "outside" / "secret.txt"
            outside.parent.mkdir()
            outside.write_text("secret", encoding="utf-8")
            self._replace_dependency_path(manifest, str(outside))

            with patch("svg_to_drawio.conversion_cache._sha256_file") as sha256_file:
                cached = self._cached_report(manifest, source, output)

            self.assertIsNone(cached)
            sha256_file.assert_called_once_with(str(source))

    def test_traversal_outside_source_tree_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            trusted = base / "trusted"
            source, _, output, manifest = self._write_valid_cache(trusted)
            outside = base / "outside" / "secret.txt"
            outside.parent.mkdir()
            outside.write_text("secret", encoding="utf-8")
            traversal = trusted / "subdir" / ".." / ".." / "outside" / "secret.txt"
            self._replace_dependency_path(manifest, str(traversal))

            self.assertIsNone(self._cached_report(manifest, source, output))

    @unittest.skipIf(os.name == "nt", "Symlink creation may require privileges on Windows")
    def test_symlink_outside_source_tree_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            trusted = base / "trusted"
            source, _, output, manifest = self._write_valid_cache(trusted)
            outside = base / "outside" / "secret.txt"
            outside.parent.mkdir()
            outside.write_text("secret", encoding="utf-8")
            link = trusted / "link.txt"
            try:
                link.symlink_to(outside)
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f"Symlinks are unavailable: {exc}")
            self._replace_dependency_path(manifest, str(link))

            self.assertIsNone(self._cached_report(manifest, source, output))

    def test_missing_source_fingerprint_invalidates_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            source, _, output, manifest = self._write_valid_cache(Path(tmpdir) / "trusted")
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            entry = next(iter(payload["entries"].values()))
            entry["fingerprints"] = entry["fingerprints"][1:]
            manifest.write_text(json.dumps(payload), encoding="utf-8")

            self.assertIsNone(self._cached_report(manifest, source, output))

    def test_corrupt_or_stale_fingerprints_invalidate_cache(self) -> None:
        mutations = (
            lambda fingerprint: fingerprint.pop("path"),
            lambda fingerprint: fingerprint.pop("sha256"),
            lambda fingerprint: fingerprint.update(sha256="not-a-real-digest"),
            lambda fingerprint: fingerprint.update(path=str(Path(fingerprint["path"]).with_name("missing.png"))),
        )
        for mutate in mutations:
            with self.subTest(mutation=mutate), tempfile.TemporaryDirectory() as tmpdir:
                source, _, output, manifest = self._write_valid_cache(Path(tmpdir) / "trusted")
                payload = json.loads(manifest.read_text(encoding="utf-8"))
                entry = next(iter(payload["entries"].values()))
                mutate(entry["fingerprints"][1])
                manifest.write_text(json.dumps(payload), encoding="utf-8")

                self.assertIsNone(self._cached_report(manifest, source, output))


if __name__ == "__main__":
    unittest.main()
