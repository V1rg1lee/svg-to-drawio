from __future__ import annotations

import argparse
import getpass
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path


def is_git_for_windows_gpg(gpg_executable: str) -> bool:
    normalized = gpg_executable.replace("/", "\\").lower()
    return normalized.endswith(r"git\usr\bin\gpg.exe")


def format_gpg_path(gpg_executable: str, path: Path) -> str:
    resolved = path.resolve()
    if os.name == "nt" and is_git_for_windows_gpg(gpg_executable):
        drive, tail = os.path.splitdrive(str(resolved))
        drive_letter = drive.rstrip(":").lower()
        normalized_tail = tail.replace("\\", "/")
        return f"/{drive_letter}{normalized_tail}"
    return str(resolved)


def detect_gpg_executable() -> str:
    configured = os.environ.get("GPG_EXECUTABLE")
    if configured:
        return configured

    for candidate in ("gpg", "gpg2"):
        resolved = shutil.which(candidate)
        if resolved:
            return resolved

    windows_candidates = (
        Path(r"C:\Program Files\Git\usr\bin\gpg.exe"),
        Path(r"C:\Program Files\GnuPG\bin\gpg.exe"),
        Path(r"C:\Program Files (x86)\GnuPG\bin\gpg.exe"),
    )
    for candidate in windows_candidates:
        if candidate.exists():
            return str(candidate)

    raise SystemExit(
        "Unable to find gpg. Install GnuPG or Git for Windows, or set GPG_EXECUTABLE."
    )


def run_gpg(
    gpg_executable: str,
    homedir: Path,
    args: list[str],
    *,
    input_text: str | None = None,
    passphrase: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a GPG command with optional passphrase via file descriptor.

    Args:
        gpg_executable: Path to GPG executable
        homedir: GPG home directory
        args: Additional GPG arguments
        input_text: Optional text to pass to stdin
        passphrase: Optional passphrase to pass via file descriptor (secure method)

    Returns:
        CompletedProcess result
    """
    command = [
        gpg_executable,
        "--batch",
        "--homedir",
        format_gpg_path(gpg_executable, homedir),
        *args,
    ]

    # If passphrase is provided, use a temporary file descriptor to pass it securely
    # This avoids exposing the passphrase in process arguments
    passphrase_file = None
    try:
        if passphrase is not None:
            # Create a temporary file to hold the passphrase
            # Use delete=False so we can control when it's deleted
            passphrase_file = tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", delete=False
            )
            passphrase_file.write(passphrase)
            passphrase_file.close()

            # Use --passphrase-file to read from the temporary file
            # This is more secure than --passphrase as it doesn't expose the value in argv
            command.insert(4, "--passphrase-file")
            command.insert(5, passphrase_file.name)

        result = subprocess.run(
            command,
            input=input_text,
            text=True,
            capture_output=True,
            check=True,
        )
        return result
    except subprocess.CalledProcessError as exc:
        # Redact passphrase-file path from error messages for security
        safe_command = [
            (
                arg
                if not (i > 0 and command[i - 1] == "--passphrase-file")
                else "[REDACTED]"
            )
            for i, arg in enumerate(command)
        ]
        message_lines = [
            "gpg command failed:",
            " ".join(safe_command),
        ]
        if exc.stdout:
            message_lines.extend(["", "stdout:", exc.stdout.strip()])
        if exc.stderr:
            message_lines.extend(["", "stderr:", exc.stderr.strip()])
        raise SystemExit("\n".join(message_lines)) from exc
    finally:
        # Clean up the temporary passphrase file
        if passphrase_file is not None:
            try:
                os.unlink(passphrase_file.name)
            except OSError:
                pass


def parse_fingerprint(gpg_output: str) -> str:
    for line in gpg_output.splitlines():
        parts = line.split(":")
        if len(parts) > 9 and parts[0] == "fpr":
            return parts[9]
    raise ValueError("Unable to parse generated key fingerprint.")


def build_batch_config(
    name: str, email: str, passphrase: str | None, expiry_years: int
) -> str:
    lines = [
        "Key-Type: RSA",
        "Key-Length: 4096",
        "Key-Usage: sign",
        f"Name-Real: {name}",
        f"Name-Email: {email}",
        f"Expire-Date: {expiry_years}y",
    ]
    if passphrase:
        lines.append(f"Passphrase: {passphrase}")
    else:
        lines.append("%no-protection")
    lines.append("%commit")
    return "\n".join(lines) + "\n"


def write_text(path: Path, content: str, *, secure: bool = False) -> None:
    """Write text to a file, optionally with restrictive permissions.

    Args:
        path: Target file path
        content: Text content to write
        secure: If True, set file permissions to 0600 (owner read/write only)
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    if secure:
        # Set restrictive permissions: owner read/write only (0600)
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def prompt_for_passphrase() -> str | None:
    """Securely prompt for a passphrase without exposing it in process arguments.

    Returns:
        The passphrase string, or None if user chooses no passphrase
    """
    print()
    print("=" * 70)
    print("PASSPHRASE CONFIGURATION")
    print("=" * 70)
    print()
    print("You can protect the private key with a passphrase.")
    print()
    print("SECURITY CONSIDERATIONS:")
    print("  • WITH passphrase: Key is encrypted and requires the passphrase to use")
    print("  • WITHOUT passphrase: Key is unencrypted and can be used by anyone")
    print()
    print("For CI/CD automation, you'll need to store the passphrase as a secret.")
    print("For local use, a passphrase provides additional security.")
    print()

    while True:
        use_passphrase = (
            input("Do you want to set a passphrase? (y/n): ").strip().lower()
        )
        if use_passphrase in ("y", "yes"):
            break
        elif use_passphrase in ("n", "no"):
            print()
            print("WARNING: Generating an UNPROTECTED private key without passphrase.")
            print("WARNING: Anyone who obtains the private key file can use it.")
            print()
            confirm = (
                input("Are you sure you want no passphrase? (y/n): ").strip().lower()
            )
            if confirm in ("y", "yes"):
                return None
        else:
            print("Please answer 'y' or 'n'.")

    print()
    while True:
        passphrase = getpass.getpass("Enter passphrase: ")
        if not passphrase:
            print("Passphrase cannot be empty. Please try again.")
            continue

        passphrase_confirm = getpass.getpass("Confirm passphrase: ")
        if passphrase == passphrase_confirm:
            print("Passphrase set successfully.")
            return passphrase
        else:
            print("Passphrases do not match. Please try again.")
            print()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a dedicated GPG release signing key for GitHub CI."
    )
    parser.add_argument(
        "--name",
        default="svg-to-drawio Release Signing",
        help="Key owner name.",
    )
    parser.add_argument(
        "--email",
        default="release-signing@svg-to-drawio.local",
        help="Key owner email.",
    )
    parser.add_argument(
        "--output-dir",
        default=".signing/release-gpg",
        help="Directory where generated key material will be written.",
    )
    parser.add_argument(
        "--no-passphrase",
        action="store_true",
        help=(
            "Generate an unprotected key without prompting for a passphrase. "
            "SECURITY WARNING: This creates an unprotected key that can be used by "
            "anyone who obtains the exported file. Only appropriate for fully automated "
            "CI environments where the key is stored in encrypted secrets."
        ),
    )
    parser.add_argument(
        "--expiry-years",
        type=int,
        default=2,
        help=(
            "Key expiry in years. Default is 2 years. While expiry does not prevent "
            "misuse of a stolen key before expiration, it limits the window of "
            "vulnerability and enforces periodic key rotation."
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite the output directory if it already exists.",
    )
    args = parser.parse_args()

    # Securely prompt for passphrase (not via command-line arguments)
    if args.no_passphrase:
        passphrase = None
        print(
            "WARNING: Generating an UNPROTECTED private key without passphrase protection.",
            file=sys.stderr,
        )
        print(
            "WARNING: Anyone who obtains the exported private-key.asc file can use it to",
            file=sys.stderr,
        )
        print(
            "WARNING: forge signatures. This is only appropriate for CI automation where",
            file=sys.stderr,
        )
        print(
            "WARNING: the key is stored in encrypted repository secrets.",
            file=sys.stderr,
        )
        print(file=sys.stderr)
    else:
        passphrase = prompt_for_passphrase()

    repo_root = Path(__file__).resolve().parents[1]
    output_dir = (repo_root / args.output_dir).resolve()
    if output_dir.exists():
        if not args.force:
            raise SystemExit(
                f"Output directory already exists: {output_dir}\n"
                "Use --force to replace it."
            )
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

    # Set restrictive permissions on output directory to prevent unauthorized access
    if os.name != "nt":
        output_dir.chmod(0o700)

    gpg_executable = detect_gpg_executable()
    gnupg_home = output_dir / "gnupg-home"
    gnupg_home.mkdir(parents=True, exist_ok=True)

    if os.name != "nt":
        gnupg_home.chmod(0o700)

    batch_config = build_batch_config(
        args.name, args.email, passphrase, args.expiry_years
    )
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", delete=False, suffix=".batch"
    ) as handle:
        handle.write(batch_config)
        batch_file = Path(handle.name)

    try:
        generate_args = [
            "--pinentry-mode",
            "loopback",
            "--generate-key",
            format_gpg_path(gpg_executable, batch_file),
        ]
        run_gpg(gpg_executable, gnupg_home, generate_args)

        secret_key_listing = run_gpg(
            gpg_executable,
            gnupg_home,
            ["--with-colons", "--list-secret-keys", args.email],
        )
        fingerprint = parse_fingerprint(secret_key_listing.stdout)

        export_args = ["--armor", "--export", fingerprint]
        public_key = run_gpg(gpg_executable, gnupg_home, export_args).stdout

        secret_export_args = ["--pinentry-mode", "loopback", "--armor"]
        secret_export_args.extend(["--export-secret-keys", fingerprint])
        private_key = run_gpg(
            gpg_executable, gnupg_home, secret_export_args, passphrase=passphrase
        ).stdout

        write_text(output_dir / "public-key.asc", public_key)
        # Write private key with restrictive permissions (0600)
        write_text(output_dir / "private-key.asc", private_key, secure=True)
        write_text(output_dir / "fingerprint.txt", fingerprint + "\n")
        # Write github-secrets.txt with restrictive permissions
        # Note: We don't include the actual passphrase value for security
        write_text(
            output_dir / "github-secrets.txt",
            "\n".join(
                [
                    "GitHub repository secrets to set:",
                    "",
                    "RELEASE_GPG_PRIVATE_KEY",
                    "  Value: contents of private-key.asc",
                    "",
                    "RELEASE_GPG_PASSPHRASE",
                    (
                        "  Value: the passphrase you entered during key generation"
                        if passphrase
                        else "  (no passphrase secret needed for this key)"
                    ),
                    "",
                    "Suggested gh CLI commands:",
                    f'  gh secret set RELEASE_GPG_PRIVATE_KEY < "{output_dir / "private-key.asc"}"',
                    (
                        "  gh secret set RELEASE_GPG_PASSPHRASE  # You will be prompted to enter it"
                        if passphrase
                        else "  (no passphrase secret needed for this key)"
                    ),
                    "",
                    "Useful release assets:",
                    f"  Public key: {output_dir / 'public-key.asc'}",
                    f"  Fingerprint: {fingerprint}",
                ]
            )
            + "\n",
            secure=True,
        )

    finally:
        batch_file.unlink(missing_ok=True)

    appimage_note = (
        "enabled"
        if not passphrase
        else "disabled in CI for embedded AppImage signatures (detached .asc files still work)"
    )

    print(f"GPG executable: {gpg_executable}")
    print(f"Output directory: {output_dir}")
    print(f"Fingerprint: {fingerprint}")
    print(f"Key expiry: {args.expiry_years} years")
    print(
        f"Passphrase protection: {'enabled' if passphrase else 'DISABLED (unprotected key)'}"
    )
    print(f"Embedded AppImage signing in CI: {appimage_note}")
    print(f"Private key export: {output_dir / 'private-key.asc'} (permissions: 0600)")
    print(f"Public key export: {output_dir / 'public-key.asc'}")
    print(f"GitHub secret helper: {output_dir / 'github-secrets.txt'}")

    if not passphrase:
        print()
        print(
            "SECURITY REMINDER: The private key has NO passphrase protection.",
            file=sys.stderr,
        )
        print(
            "Store it securely and never commit it to version control.", file=sys.stderr
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
