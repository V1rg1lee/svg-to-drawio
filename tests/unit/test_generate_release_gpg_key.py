"""Regression tests for release GPG key output permissions."""

from __future__ import annotations

import os
import stat
import subprocess
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from scripts import generate_release_gpg_key


class GenerateReleaseGpgKeyTests(unittest.TestCase):
    """Keep generated private key material restricted to its owner."""

    @unittest.skipIf(os.name == "nt", "POSIX permissions are not applicable on Windows")
    def test_generated_sensitive_outputs_have_restrictive_permissions(self) -> None:
        fingerprint = "0123456789ABCDEF0123456789ABCDEF01234567"
        gpg_results = [
            subprocess.CompletedProcess([], 0, stdout="", stderr=""),
            subprocess.CompletedProcess([], 0, stdout=f"fpr:::::::::{fingerprint}:\n", stderr=""),
            subprocess.CompletedProcess([], 0, stdout="PUBLIC KEY\n", stderr=""),
            subprocess.CompletedProcess([], 0, stdout="PRIVATE KEY\n", stderr=""),
        ]

        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "release-gpg"
            argv = ["generate_release_gpg_key.py", "--output-dir", str(output_dir), "--no-passphrase"]
            with (
                patch("sys.argv", argv),
                patch.object(generate_release_gpg_key, "detect_gpg_executable", return_value="mock-gpg"),
                patch.object(generate_release_gpg_key, "run_gpg", side_effect=gpg_results),
                redirect_stdout(StringIO()),
                redirect_stderr(StringIO()),
            ):
                self.assertEqual(generate_release_gpg_key.main(), 0)

            self.assertEqual(stat.S_IMODE(output_dir.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE((output_dir / "private-key.asc").stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE((output_dir / "github-secrets.txt").stat().st_mode), 0o600)
