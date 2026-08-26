"""Regression tests locking in safe handling of malicious XML/DTD payloads.

CPython's bundled expat (since 3.7.1) caps DTD/entity amplification and never
resolves external entities through `xml.etree.ElementTree`, so both classic
"billion laughs" and external-entity ("XXE") payloads already fail with a
clean `ParseError` instead of hanging or leaking data. These tests exist so a
future change (e.g. swapping the XML backend) cannot silently regress that.
"""

from __future__ import annotations

import tempfile
import xml.etree.ElementTree as ET
from os import path

from defusedxml.common import DefusedXmlException
from svg_to_drawio import convert_svg_string

from tests.helpers import SvgTestCase

_BILLION_LAUGHS_SVG = """<?xml version="1.0"?>
<!DOCTYPE svg [
<!ENTITY a "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA">
<!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">
<!ENTITY c "&b;&b;&b;&b;&b;&b;&b;&b;&b;&b;">
<!ENTITY d "&c;&c;&c;&c;&c;&c;&c;&c;&c;&c;">
<!ENTITY e "&d;&d;&d;&d;&d;&d;&d;&d;&d;&d;">
<!ENTITY f "&e;&e;&e;&e;&e;&e;&e;&e;&e;&e;">
<!ENTITY g "&f;&f;&f;&f;&f;&f;&f;&f;&f;&f;">
]>
<svg xmlns="http://www.w3.org/2000/svg"><title>&g;</title></svg>"""


class XmlSecurityTests(SvgTestCase):
    """Confirm malicious DTD/entity payloads are rejected, not executed or leaked."""

    def test_billion_laughs_entity_expansion_is_rejected(self) -> None:
        with self.assertRaises(DefusedXmlException):
            convert_svg_string(_BILLION_LAUGHS_SVG, title="billion-laughs")

    def test_external_entity_file_read_is_not_resolved(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            secret_path = path.join(tmpdir, "secret.txt")
            with open(secret_path, "w", encoding="utf-8") as handle:
                handle.write("super-secret-marker")

            secret_uri = "file:///" + secret_path.replace("\\", "/")
            payload = (
                '<?xml version="1.0"?>\n'
                f'<!DOCTYPE svg [<!ENTITY xxe SYSTEM "{secret_uri}">]>\n'
                '<svg xmlns="http://www.w3.org/2000/svg"><title>&xxe;</title></svg>'
            )

            with self.assertRaises(DefusedXmlException):
                convert_svg_string(payload, title="xxe-file-read")

    def test_svg_text_with_html_markup_is_escaped_in_drawio_labels(self) -> None:
        """Verify that SVG text containing HTML markup is properly escaped.

        This prevents stored XSS when the draw.io document is opened, since
        text cells use html=1 in their style. Without escaping, markup like
        <img src=x onerror=alert(1)> would be rendered as HTML.
        """
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg" width="200" height="100">
          <text x="10" y="30" font-size="14">Normal &amp; Safe</text>
          <text x="10" y="60" font-size="14">&lt;img src=x onerror=alert(1)&gt;</text>
          <text x="10" y="90" font-size="14"><tspan>Nested &lt;script&gt;alert(2)&lt;/script&gt;</tspan></text>
        </svg>
        """

        xml = convert_svg_string(svg, title="html-injection-test")
        root = ET.fromstring(xml)

        # Find all text cells with values
        text_cells = [
            cell
            for cell in root.findall(".//mxCell[@value]")
            if cell.get("value") and cell.get("value").strip()
        ]

        # Verify we have the expected text cells
        self.assertGreaterEqual(len(text_cells), 3)

        # Check that all text values are properly HTML-escaped
        for cell in text_cells:
            value = cell.get("value", "")
            style = cell.get("style", "")

            # If the cell has html=1, the value must be HTML-escaped
            if "html=1" in style:
                # These patterns should NOT appear unescaped in HTML-enabled cells
                self.assertNotIn(
                    "<img", value, "Unescaped <img> tag found in HTML-enabled cell"
                )
                self.assertNotIn(
                    "<script",
                    value,
                    "Unescaped <script> tag found in HTML-enabled cell",
                )
                self.assertNotIn(
                    "onerror=",
                    value,
                    "Unescaped event handler found in HTML-enabled cell",
                )

                # The escaped versions should be present
                if "img" in value.lower():
                    # After XML parsing, HTML-escaped < becomes &lt; which is safe
                    self.assertIn("&lt;", value, "Expected HTML-escaped content")
                if "script" in value.lower():
                    self.assertIn("&lt;", value, "Expected HTML-escaped content")
