"""Unit tests for image embedding and transform handling."""

from __future__ import annotations

import tempfile
import xml.etree.ElementTree as ET
from os import path, symlink
from types import SimpleNamespace
from urllib.parse import unquote_to_bytes
from xml.sax.saxutils import quoteattr

from svg_to_drawio import convert_svg_string_result
from svg_to_drawio.diagnostics import ConversionReport
from svg_to_drawio.elements.image import _resolve_image_href
from svg_to_drawio.issue_codes import IMAGE_REMOTE_LINKED

from tests.helpers import SvgTestCase


class ImageTests(SvgTestCase):
    """Validate image resolution, security checks, and geometry mapping."""

    def _convert_image_href(self, href: str, *, base_dir: str) -> tuple[ET.Element, ConversionReport]:
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">'
            f'<image href={quoteattr(href)} x="0" y="0" width="20" height="20" />'
            "</svg>"
        )
        result = convert_svg_string_result(svg, title="image-href", base_dir=base_dir)
        return ET.fromstring(result.xml), result.report

    def _wrapped_remote_href(self, root: ET.Element) -> str:
        cells = self._user_cells(root)
        self.assertEqual(len(cells), 1)
        image_value = self._style_map(cells[0])["image"]
        self.assertIsInstance(image_value, str)
        assert isinstance(image_value, str)
        self.assertTrue(image_value.startswith("data:image/svg+xml,"))
        wrapper = unquote_to_bytes(image_value.split(",", 1)[1]).decode("utf-8")
        image = ET.fromstring(wrapper).find("{http://www.w3.org/2000/svg}image")
        self.assertIsNotNone(image)
        assert image is not None
        return image.get("href", "")

    def test_local_image_outside_source_dir_is_rejected(self) -> None:
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
          <image href="../secret.png" x="0" y="0" width="20" height="20" />
        </svg>
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            secret_path = path.join(tmpdir, "secret.png")
            with open(secret_path, "wb") as handle:
                handle.write(b"not-a-real-png")

            root, _ = self._convert_in_dir(tmpdir, svg, rel_path=path.join("nested", "diagram.svg"))
            self.assertEqual(self._user_cells(root), [])

    def test_local_image_inside_source_dir_is_embedded(self) -> None:
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
          <image href="asset.png" x="0" y="0" width="20" height="20" />
        </svg>
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            asset_path = path.join(tmpdir, "asset.png")
            with open(asset_path, "wb") as handle:
                handle.write(b"not-a-real-png")

            root, _ = self._convert_in_dir(tmpdir, svg)
            self.assertEqual(len(self._user_cells(root)), 1)

    def test_local_image_symlink_to_internal_target_is_embedded(self) -> None:
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
          <image href="asset-link.png" x="0" y="0" width="20" height="20" />
        </svg>
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            asset_path = path.join(tmpdir, "asset.png")
            with open(asset_path, "wb") as handle:
                handle.write(b"not-a-real-png")
            try:
                symlink(asset_path, path.join(tmpdir, "asset-link.png"))
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f"Symbolic links are unavailable: {exc}")

            root, _ = self._convert_in_dir(tmpdir, svg)
            self.assertEqual(len(self._user_cells(root)), 1)

    def test_local_image_symlink_to_external_target_is_rejected(self) -> None:
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
          <image href="asset-link.png" x="0" y="0" width="20" height="20" />
        </svg>
        """
        with tempfile.TemporaryDirectory() as tmpdir, tempfile.TemporaryDirectory() as outside_dir:
            outside_asset = path.join(outside_dir, "secret.png")
            with open(outside_asset, "wb") as handle:
                handle.write(b"not-a-real-png")
            try:
                symlink(outside_asset, path.join(tmpdir, "asset-link.png"))
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f"Symbolic links are unavailable: {exc}")

            root, _ = self._convert_in_dir(tmpdir, svg)
            self.assertEqual(self._user_cells(root), [])

    def test_image_data_uri_preserve_aspect_ratio_none_and_rotation_are_mapped(self) -> None:
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
          <image
            href="data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A//www.w3.org/2000/svg%22%20/%3E"
            x="0"
            y="0"
            width="10"
            height="10"
            preserveAspectRatio="none"
            transform="rotate(45 5 5)"
          />
        </svg>
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            root, _ = self._convert_in_dir(tmpdir, svg)
            styles = self._style_map(self._user_cells(root)[0])
            self.assertTrue(styles["image"].startswith("data:image/svg+xml,"))
            self.assertEqual(styles["imageAspect"], "0")
            self.assertEqual(styles["rotation"], "45.00")

    def test_sheared_images_use_transformed_bounding_box(self) -> None:
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
          <image
            href="data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A//www.w3.org/2000/svg%22%20/%3E"
            x="0"
            y="0"
            width="10"
            height="20"
            transform="matrix(1,0,1,1,0,0)"
          />
        </svg>
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            root, _ = self._convert_in_dir(tmpdir, svg)
            cell = self._user_cells(root)[0]
            styles = self._style_map(cell)
            geometry = cell.find("mxGeometry")
            self.assertNotIn("rotation", styles)
            self.assertAlmostEqual(float(geometry.get("width")), 30.0, places=2)
            self.assertAlmostEqual(float(geometry.get("height")), 20.0, places=2)

    def test_http_https_and_uppercase_schemes_remain_remote(self) -> None:
        urls = (
            "http://example.com/image.png",
            "https://example.com/image.png",
            "HTTP://example.com/image.png",
            "HtTpS://example.com/image.png",
        )
        for url in urls:
            with self.subTest(url=url), tempfile.TemporaryDirectory() as tmpdir:
                root, report = self._convert_image_href(url, base_dir=tmpdir)
                self.assertEqual(self._wrapped_remote_href(root), url)
                self.assertEqual([(asset.href, asset.status) for asset in report.assets], [(url, "remote")])
                self.assertIn(IMAGE_REMOTE_LINKED, {issue.code for issue in report.issues})

    def test_remote_queries_fragments_and_existing_escapes_are_preserved(self) -> None:
        urls = (
            "https://example.com/image.png?width=100&height=200",
            "https://example.com/image.png#fragment",
            "https://example.com/image.png?token=a%20b",
        )
        for url in urls:
            with self.subTest(url=url), tempfile.TemporaryDirectory() as tmpdir:
                root, report = self._convert_image_href(url, base_dir=tmpdir)
                self.assertEqual(self._wrapped_remote_href(root), url)
                self.assertEqual(report.assets[0].href, url)

    def test_disallowed_uri_schemes_are_rejected(self) -> None:
        urls = (
            "javascript:alert(1)",
            "JaVaScRiPt:alert(1)",
            "file:///etc/passwd",
            "ftp://example.com/image.png",
            "ftps://example.com/image.png",
            "vbscript:msgbox(1)",
            "blob:https://example.com/id",
            "about:blank",
            "custom://host/image",
            "vscode://file/foo",
            "urn:example:image",
            "mailto:test@example.com",
        )
        for url in urls:
            with self.subTest(url=url), tempfile.TemporaryDirectory() as tmpdir:
                root, report = self._convert_image_href(url, base_dir=tmpdir)
                self.assertEqual(self._user_cells(root), [])
                self.assertEqual(len(report.assets), 1)
                self.assertEqual(report.assets[0].status, "rejected")
                self.assertIn("scheme", report.assets[0].message or "")
                self.assertEqual(report.dependencies, [])

    def test_non_image_data_uris_are_rejected(self) -> None:
        uris = (
            "data:text/html,<script>alert(1)</script>",
            "data:text/plain,hello",
            "data:application/javascript,alert(1)",
            "data:application/octet-stream;base64,AA==",
        )
        for uri in uris:
            with self.subTest(uri=uri), tempfile.TemporaryDirectory() as tmpdir:
                root, report = self._convert_image_href(uri, base_dir=tmpdir)
                self.assertEqual(self._user_cells(root), [])
                self.assertEqual(report.assets[0].status, "rejected")
                self.assertIn("image/*", report.assets[0].message or "")

    def test_valid_raster_and_svg_data_uris_are_accepted(self) -> None:
        uris = (
            "data:image/png;base64,AA==",
            "data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A//www.w3.org/2000/svg%22/%3E",
        )
        for uri in uris:
            with self.subTest(uri=uri), tempfile.TemporaryDirectory() as tmpdir:
                root, report = self._convert_image_href(uri, base_dir=tmpdir)
                self.assertEqual(len(self._user_cells(root)), 1)
                self.assertEqual(report.assets[0].status, "embedded")

    def test_remote_semicolon_cannot_inject_drawio_style(self) -> None:
        url = "https://example.com/image.png?value=a;link=javascript:alert(1)"
        with tempfile.TemporaryDirectory() as tmpdir:
            root, report = self._convert_image_href(url, base_dir=tmpdir)
            cell = self._user_cells(root)[0]
            style = cell.get("style", "")
            wrapped_href = self._wrapped_remote_href(root)
            self.assertNotIn(";link=javascript", style)
            self.assertNotIn("link", self._style_map(cell))
            self.assertEqual(wrapped_href, "https://example.com/image.png?value=a%3Blink=javascript:alert(1)")
            self.assertEqual(report.assets[0].href, url)

    def test_control_characters_are_rejected_without_cleaning(self) -> None:
        hrefs = (
            "https://example.com/im\x00age.png",
            "https://example.com/im\nage.png",
            "java\rscript:alert(1)",
            "https://example.com/\x7fimage.png",
            "https://example.com/\x80image.png",
        )
        for href in hrefs:
            with self.subTest(href=repr(href)), tempfile.TemporaryDirectory() as tmpdir:
                report = ConversionReport()
                ctx = SimpleNamespace(source_dir=tmpdir, report=report)
                self.assertEqual(_resolve_image_href(ctx, href), (None, None))  # type: ignore[arg-type]
                self.assertEqual(report.assets[0].href, href.strip())
                self.assertEqual(report.assets[0].status, "rejected")
                self.assertIn("control", report.assets[0].message or "")

    def test_windows_drive_paths_are_classified_as_local(self) -> None:
        hrefs = (r"C:\Users\Virgile\image.png", "C:/Users/Virgile/image.png")
        for href in hrefs:
            with self.subTest(href=href), tempfile.TemporaryDirectory() as tmpdir:
                report = ConversionReport()
                ctx = SimpleNamespace(source_dir=tmpdir, report=report)
                self.assertEqual(_resolve_image_href(ctx, href), (None, None))  # type: ignore[arg-type]
                self.assertEqual(report.assets[0].status, "missing")
                self.assertNotIn("scheme", report.assets[0].message or "")
