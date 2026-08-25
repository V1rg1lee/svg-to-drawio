#!/usr/bin/env python3
"""
Generate hash-pinned requirements lockfile for secure desktop builds.

This script uses pip-tools to generate requirements-desktop.lock from
requirements-desktop.txt with cryptographic hashes for all dependencies.

Usage:
    python scripts/generate_requirements_lock.py

Requirements:
    pip install pip-tools
"""

import subprocess
import sys
from pathlib import Path


def main() -> int:
    """Generate the requirements lockfile with hashes."""
    repo_root = Path(__file__).parent.parent
    requirements_in = repo_root / "requirements-desktop.txt"
    requirements_lock = repo_root / "requirements-desktop.lock"

    if not requirements_in.exists():
        print(f"Error: {requirements_in} not found", file=sys.stderr)
        return 1

    print("Checking for pip-tools...")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "show", "pip-tools"],
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError:
        print("pip-tools not found. Installing...", file=sys.stderr)
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "pip-tools"],
            check=True,
        )

    print(f"Generating {requirements_lock} from {requirements_in}...")
    print("This may take a few minutes as it resolves all dependencies...")

    try:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "piptools",
                "compile",
                "--generate-hashes",
                "--output-file",
                str(requirements_lock),
                str(requirements_in),
            ],
            check=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"Error generating lockfile: {e}", file=sys.stderr)
        return 1

    print(f"\n✓ Successfully generated {requirements_lock}")
    print("\nNext steps:")
    print("1. Review the generated lockfile for unexpected dependencies")
    print(
        "2. Test installation: pip install --require-hashes -r requirements-desktop.lock"
    )
    print("3. Commit the lockfile to version control")
    print(
        "\nThe lockfile should be regenerated whenever requirements-desktop.txt changes."
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
