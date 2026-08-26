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
        """Keep SVG text as literal text instead of executable draw.io HTML."""
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg" width="300" height="100">
          <text x="10" y="30" font-size="14">&lt;img src=x onerror=alert(1)&gt;</text>
          <text x="10" y="60" font-size="14">&lt;script&gt;alert(2)&lt;/script&gt;</text>
        </svg>
        """

        xml = convert_svg_string(svg, title="html-injection-test")
        root = ET.fromstring(xml)
        cells = {cell.get("value"): cell for cell in root.findall(".//mxCell[@value]")}

        image_value = "&lt;img src=x onerror=alert(1)&gt;"
        script_value = "&lt;script&gt;alert(2)&lt;/script&gt;"
        self.assertIn(image_value, cells)
        self.assertIn(script_value, cells)

        for value in (image_value, script_value):
            lowered = value.lower()
            self.assertNotIn("<img", lowered)
            self.assertNotIn("<script", lowered)
            self.assertIn("html=1", cells[value].get("style", ""))

        self.assertIn("&lt;img", image_value.lower())
        self.assertIn("onerror=alert(1)", image_value)
        self.assertIn("&lt;script", script_value.lower())
        self.assertIn("alert(2)", script_value)

    def test_svg_text_html_escaping_preserves_normal_text_logically(self) -> None:
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg" width="300" height="100">
          <text x="10" y="20">A &amp; B</text>
          <text x="10" y="50">2 &lt; 5</text>
          <text x="10" y="80">Hello World</text>
        </svg>
        """

        xml = convert_svg_string(svg, title="normal-html-text-test")
        root = ET.fromstring(xml)
        cells = {cell.get("value"): cell for cell in root.findall(".//mxCell[@value]")}

        for value in ("A &amp; B", "2 &lt; 5", "Hello World"):
            self.assertIn(value, cells)
            self.assertIn("html=1", cells[value].get("style", ""))
