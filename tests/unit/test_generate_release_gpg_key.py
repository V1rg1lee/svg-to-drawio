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
from unittest.mock import Mock, patch

from scripts import generate_release_gpg_key


class GenerateReleaseGpgKeyTests(unittest.TestCase):
    """Keep generated private key material restricted to its owner."""

    def test_prompt_for_passphrase_returns_matching_value(self) -> None:
        with (
            patch("builtins.input", return_value="y"),
            patch("getpass.getpass", side_effect=["correct horse battery staple"] * 2),
            redirect_stdout(StringIO()),
        ):
            result = generate_release_gpg_key.prompt_for_passphrase()

        self.assertEqual(result, "correct horse battery staple")

    def test_prompt_for_passphrase_retries_after_mismatched_confirmation(self) -> None:
        with (
            patch("builtins.input", return_value="y"),
            patch("getpass.getpass", side_effect=["secret-one", "secret-two", "secret-final", "secret-final"]),
            redirect_stdout(StringIO()),
        ):
            result = generate_release_gpg_key.prompt_for_passphrase()

        self.assertEqual(result, "secret-final")

    def test_prompt_for_passphrase_retries_after_empty_value(self) -> None:
        with (
            patch("builtins.input", return_value="y"),
            patch("getpass.getpass", side_effect=["", "valid-secret", "valid-secret"]),
            redirect_stdout(StringIO()),
        ):
            result = generate_release_gpg_key.prompt_for_passphrase()

        self.assertEqual(result, "valid-secret")

    def test_prompt_for_passphrase_allows_confirmed_unprotected_key(self) -> None:
        with patch("builtins.input", side_effect=["n", "y"]), redirect_stdout(StringIO()):
            result = generate_release_gpg_key.prompt_for_passphrase()

        self.assertIsNone(result)

    def test_run_gpg_passes_secret_through_temporary_file_and_removes_it(self) -> None:
        passphrase_path: Path | None = None

        def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            nonlocal passphrase_path
            self.assertNotIn("super-secret", command)
            passphrase_index = command.index("--passphrase-file")
            passphrase_path = Path(command[passphrase_index + 1])
            self.assertTrue(passphrase_path.is_file())
            self.assertEqual(passphrase_path.read_text(encoding="utf-8"), "super-secret")
            return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

        with TemporaryDirectory() as tmpdir, patch("subprocess.run", side_effect=fake_run):
            result = generate_release_gpg_key.run_gpg("mock-gpg", Path(tmpdir), ["--export"], passphrase="super-secret")

        self.assertEqual(result.stdout, "ok")
        self.assertIsNotNone(passphrase_path)
        assert passphrase_path is not None
        self.assertFalse(passphrase_path.exists())

    def test_run_gpg_redacts_and_removes_passphrase_file_after_failure(self) -> None:
        passphrase_path: Path | None = None

        def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            nonlocal passphrase_path
            self.assertNotIn("super-secret", command)
            passphrase_index = command.index("--passphrase-file")
            passphrase_path = Path(command[passphrase_index + 1])
            self.assertTrue(passphrase_path.is_file())
            raise subprocess.CalledProcessError(2, command, output="", stderr="mock GPG failure")

        with TemporaryDirectory() as tmpdir, patch("subprocess.run", side_effect=fake_run):
            with self.assertRaises(SystemExit) as raised:
                generate_release_gpg_key.run_gpg(
                    "mock-gpg", Path(tmpdir), ["--export-secret-keys"], passphrase="super-secret"
                )

        message = str(raised.exception)
        self.assertIn("--passphrase-file", message)
        self.assertIn("[REDACTED]", message)
        self.assertNotIn("super-secret", message)
        self.assertIsNotNone(passphrase_path)
        assert passphrase_path is not None
        self.assertNotIn(str(passphrase_path), message)
        self.assertFalse(passphrase_path.exists())

    def test_main_generates_protected_key_without_persisting_passphrase(self) -> None:
        fingerprint = "0123456789ABCDEF0123456789ABCDEF01234567"
        batch_path: Path | None = None

        def fake_run_gpg(
            gpg_executable: str,
            homedir: Path,
            args: list[str],
            *,
            input_text: str | None = None,
            passphrase: str | None = None,
        ) -> subprocess.CompletedProcess[str]:
            nonlocal batch_path
            if "--generate-key" in args:
                batch_path = Path(args[-1])
                self.assertTrue(batch_path.is_file())
                return subprocess.CompletedProcess([], 0, stdout="", stderr="")
            if "--list-secret-keys" in args:
                return subprocess.CompletedProcess([], 0, stdout=f"fpr:::::::::{fingerprint}:\n", stderr="")
            if "--export-secret-keys" in args:
                self.assertEqual(passphrase, "test-secret-passphrase")
                self.assertNotIn("test-secret-passphrase", args)
                self.assertNotIn("--passphrase", args)
                return subprocess.CompletedProcess([], 0, stdout="PRIVATE KEY\n", stderr="")
            return subprocess.CompletedProcess([], 0, stdout="PUBLIC KEY\n", stderr="")

        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "release-gpg"
            argv = ["generate_release_gpg_key.py", "--output-dir", str(output_dir)]
            run_gpg = Mock(side_effect=fake_run_gpg)
            with (
                patch("sys.argv", argv),
                patch.object(generate_release_gpg_key, "prompt_for_passphrase", return_value="test-secret-passphrase"),
                patch.object(generate_release_gpg_key, "detect_gpg_executable", return_value="mock-gpg"),
                patch.object(generate_release_gpg_key, "run_gpg", run_gpg),
                redirect_stdout(StringIO()),
                redirect_stderr(StringIO()),
            ):
                self.assertEqual(generate_release_gpg_key.main(), 0)

            self.assertTrue((output_dir / "private-key.asc").is_file())
            github_secrets = (output_dir / "github-secrets.txt").read_text(encoding="utf-8")
            self.assertIn("RELEASE_GPG_PASSPHRASE", github_secrets)
            self.assertNotIn("test-secret-passphrase", github_secrets)
            self.assertIsNotNone(batch_path)
            assert batch_path is not None
            self.assertFalse(batch_path.exists())

    @unittest.skipIf(os.name == "nt", "POSIX permissions are not applicable on Windows")
    def test_sensitive_batch_file_has_restrictive_permissions(self) -> None:
        batch_path: Path | None = None

        def fail_after_inspecting_batch(
            gpg_executable: str,
            homedir: Path,
            args: list[str],
            *,
            input_text: str | None = None,
            passphrase: str | None = None,
        ) -> subprocess.CompletedProcess[str]:
            nonlocal batch_path
            batch_path = Path(args[-1])
            self.assertEqual(stat.S_IMODE(batch_path.stat().st_mode), 0o600)
            raise SystemExit("mock GPG failure")

        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "release-gpg"
            argv = ["generate_release_gpg_key.py", "--output-dir", str(output_dir)]
            with (
                patch("sys.argv", argv),
                patch.object(generate_release_gpg_key, "prompt_for_passphrase", return_value="batch-secret"),
                patch.object(generate_release_gpg_key, "detect_gpg_executable", return_value="mock-gpg"),
                patch.object(generate_release_gpg_key, "run_gpg", side_effect=fail_after_inspecting_batch),
                redirect_stdout(StringIO()),
                redirect_stderr(StringIO()),
                self.assertRaisesRegex(SystemExit, "mock GPG failure"),
            ):
                generate_release_gpg_key.main()

            self.assertIsNotNone(batch_path)
            assert batch_path is not None
            self.assertFalse(batch_path.exists())

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
