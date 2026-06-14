"""Unit tests for image embedding and transform handling."""

from __future__ import annotations

import tempfile
from os import path

from tests.helpers import SvgTestCase


class ImageTests(SvgTestCase):
    """Validate image resolution, security checks, and geometry mapping."""

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
