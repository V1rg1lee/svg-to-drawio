"""Compute a deterministic fingerprint for one built static site directory."""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path
from typing import TextIO


def _hash_file(file_path: Path) -> str:
    """Return the SHA-256 digest of one file."""
    digest = hashlib.sha256()
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fingerprint_directory(root: Path) -> str:
    """Return a deterministic fingerprint for all files under one directory."""
    normalized_root = root.resolve()
    if not normalized_root.is_dir():
        raise FileNotFoundError(f"Site directory does not exist: {root}")

    manifest_lines: list[str] = []
    for file_path in sorted(candidate for candidate in normalized_root.rglob("*") if candidate.is_file()):
        relative_path = file_path.relative_to(normalized_root).as_posix()
        manifest_lines.append(f"{relative_path}\t{file_path.stat().st_size}\t{_hash_file(file_path)}")

    manifest = "\n".join(manifest_lines).encode("utf-8")
    return hashlib.sha256(manifest).hexdigest()


def _write_fingerprint(fingerprint: str, output_path: Path | None, stdout: TextIO) -> None:
    """Write the fingerprint to stdout and optionally to a file."""
    stdout.write(f"{fingerprint}\n")
    if output_path is not None:
        output_path.write_text(f"{fingerprint}\n", encoding="utf-8")


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the fingerprint helper."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("site_dir", help="Static site directory to fingerprint.")
    parser.add_argument(
        "--output",
        help="Optional file where the fingerprint should also be written.",
    )
    return parser.parse_args()


def main() -> int:
    """Run the site fingerprint helper as a small CLI."""
    args = _parse_args()
    fingerprint = fingerprint_directory(Path(args.site_dir))
    output_path = Path(args.output) if args.output else None
    _write_fingerprint(fingerprint, output_path, stdout=sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
