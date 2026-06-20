"""Shared atomic text-file write helper."""

from __future__ import annotations

import os
import tempfile
from os import path


def write_text_atomically(output_path: str, text: str) -> None:
    """Write *text* to *output_path* via a temp file + atomic rename.

    Writing in place left a truncated output file on disk if the process was killed
    mid-write (e.g. the desktop app's force-close path), which a later run's cache/overwrite
    logic could then mistake for a valid prior output.
    """
    output_dir = path.dirname(output_path) or "."
    fd, tmp_path = tempfile.mkstemp(dir=output_dir, prefix=".svg-to-drawio-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(tmp_path, output_path)
    except BaseException:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise
