from __future__ import annotations

import argparse
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
        return f"/{drive_letter}{tail.replace('\\', '/')}"
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
) -> subprocess.CompletedProcess[str]:
    command = [
        gpg_executable,
        "--batch",
        "--homedir",
        format_gpg_path(gpg_executable, homedir),
        *args,
    ]
    try:
        return subprocess.run(
            command,
            input=input_text,
            text=True,
            capture_output=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        message_lines = [
            "gpg command failed:",
            " ".join(command),
        ]
        if exc.stdout:
            message_lines.extend(["", "stdout:", exc.stdout.strip()])
        if exc.stderr:
            message_lines.extend(["", "stderr:", exc.stderr.strip()])
        raise SystemExit("\n".join(message_lines)) from exc


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
        "--passphrase",
        default=None,
        help=(
            "Passphrase to protect the private key. SECURITY WARNING: Omitting this "
            "creates an unprotected key that can be used by anyone who obtains the "
            "exported file. Unprotected keys are only appropriate for fully automated "
            "CI environments where the key is stored in encrypted secrets and never "
            "written to disk in plaintext outside the CI runner."
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

    # Security warning for unprotected keys
    if not args.passphrase:
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

    repo_root = Path(__file__).resolve().parents[1]
    output_dir = (repo_root / args.output_dir).resolve()
    if output_dir.exists():
        if not args.force:
            raise SystemExit(
                f"Output directory already exists: {output_dir}\n"
                "Use --force to replace it."
            )
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    gpg_executable = detect_gpg_executable()
    gnupg_home = output_dir / "gnupg-home"
    gnupg_home.mkdir(parents=True, exist_ok=True)

    if os.name != "nt":
        gnupg_home.chmod(0o700)

    batch_config = build_batch_config(
        args.name, args.email, args.passphrase, args.expiry_years
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
        if args.passphrase:
            secret_export_args.extend(["--passphrase", args.passphrase])
        secret_export_args.extend(["--export-secret-keys", fingerprint])
        private_key = run_gpg(gpg_executable, gnupg_home, secret_export_args).stdout

        write_text(output_dir / "public-key.asc", public_key)
        # Write private key with restrictive permissions (0600)
        write_text(output_dir / "private-key.asc", private_key, secure=True)
        write_text(output_dir / "fingerprint.txt", fingerprint + "\n")
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
                    "  Value: only set this if you generated the key with --passphrase",
                    "",
                    "Suggested gh CLI commands:",
                    f'  gh secret set RELEASE_GPG_PRIVATE_KEY < "{output_dir / "private-key.asc"}"',
                    (
                        f'  gh secret set RELEASE_GPG_PASSPHRASE --body "{args.passphrase}"'
                        if args.passphrase
                        else "  (no passphrase secret needed for this key)"
                    ),
                    "",
                    "Useful release assets:",
                    f"  Public key: {output_dir / 'public-key.asc'}",
                    f"  Fingerprint: {fingerprint}",
                ]
            )
            + "\n",
        )

    finally:
        batch_file.unlink(missing_ok=True)

    appimage_note = (
        "enabled"
        if not args.passphrase
        else "disabled in CI for embedded AppImage signatures (detached .asc files still work)"
    )

    print(f"GPG executable: {gpg_executable}")
    print(f"Output directory: {output_dir}")
    print(f"Fingerprint: {fingerprint}")
    print(f"Key expiry: {args.expiry_years} years")
    print(
        f"Passphrase protection: {'enabled' if args.passphrase else 'DISABLED (unprotected key)'}"
    )
    print(f"Embedded AppImage signing in CI: {appimage_note}")
    print(f"Private key export: {output_dir / 'private-key.asc'} (permissions: 0600)")
    print(f"Public key export: {output_dir / 'public-key.asc'}")
    print(f"GitHub secret helper: {output_dir / 'github-secrets.txt'}")

    if not args.passphrase:
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
