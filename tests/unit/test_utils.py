"""Unit tests for shared parsing and style helpers."""

from __future__ import annotations

import unittest

from svg_to_drawio.utils import link_value


class LinkValueTests(unittest.TestCase):
    """Validate the allowlist and encoding used for draw.io links."""

    def test_supported_absolute_urls_are_accepted(self) -> None:
        urls = (
            "https://example.com/path?q=1#section",
            "HTTP://example.com",
            "mailto:user@example.com",
            "ftp://example.com/file",
            "ftps://example.com/file",
            "tel:+3212345678",
            "sms:+3212345678",
        )
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(link_value(url), url)

    def test_relative_and_network_path_urls_are_accepted(self) -> None:
        urls = (
            "/docs/page.html",
            "./docs/page.html",
            "../docs/page.html",
            "docs/page.html",
            "#section",
            "?page=2",
            "//example.com/path",
        )
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(link_value(url), url)

    def test_external_whitespace_is_stripped(self) -> None:
        self.assertEqual(link_value("  https://example.com/path  "), "https://example.com/path")

    def test_unsupported_schemes_are_rejected(self) -> None:
        urls = (
            "javascript:alert(1)",
            "JaVaScRiPt:alert(1)",
            "data:text/html,<script>alert(1)</script>",
            "file:///etc/passwd",
            "vbscript:msgbox(1)",
            "about:blank",
            "blob:https://example.com/id",
            "vscode://file/test",
            "urn:isbn:123456789",
            "drawio:diagram",
            "myapp:action",
        )
        for url in urls:
            with self.subTest(url=url):
                self.assertIsNone(link_value(url))

    def test_control_characters_are_rejected(self) -> None:
        urls = (
            "java\nscript:alert(1)",
            "java\rscript:alert(1)",
            "https://example.com/\x00evil",
            "https://example.com/\x7fevil",
            "https://example.com/\x80evil",
        )
        for url in urls:
            with self.subTest(url=repr(url)):
                self.assertIsNone(link_value(url))

    def test_semicolon_is_percent_encoded(self) -> None:
        result = link_value("https://example.com/a;evil=1")
        self.assertEqual(result, "https://example.com/a%3Bevil=1")
        self.assertNotIn(";", result or "")


if __name__ == "__main__":
    unittest.main()
