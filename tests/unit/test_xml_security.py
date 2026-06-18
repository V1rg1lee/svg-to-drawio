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
        with self.assertRaises(ET.ParseError):
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

            with self.assertRaises(ET.ParseError):
                convert_svg_string(payload, title="xxe-file-read")
