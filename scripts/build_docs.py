from __future__ import annotations

import os
import subprocess
import sys


def main() -> int:
    env = os.environ.copy()
    # Material for MkDocs provides this official opt-out for the MkDocs 2.0
    # warning. We already pin MkDocs < 2.0 in requirements-docs.txt, so this
    # keeps local and CI builds quiet without hiding a real incompatibility.
    env.setdefault("NO_MKDOCS_2_WARNING", "1")
    command = [sys.executable, "-m", "mkdocs", *sys.argv[1:]]
    return subprocess.call(command, env=env)


if __name__ == "__main__":
    raise SystemExit(main())
