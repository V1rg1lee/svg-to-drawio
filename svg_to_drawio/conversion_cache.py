"""Persistent cache manifest for incremental SVG conversions."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from os import path
from threading import RLock

from .atomic_write import write_text_atomically
from .diagnostics import ConversionReport


def _sha256_file(file_path: str) -> str | None:
    """Return the SHA-256 digest of a file, or ``None`` when it cannot be read."""
    if not path.isfile(file_path):
        return None
    digest = hashlib.sha256()
    try:
        with open(file_path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 64), b""):
                digest.update(chunk)
    except OSError:
        return None
    return digest.hexdigest()


@dataclass(frozen=True)
class DependencyFingerprint:
    """A stable hash snapshot for one source or dependency file."""

    file_path: str
    sha256: str

    def to_dict(self) -> dict[str, str]:
        """Serialize the fingerprint into a JSON-friendly dictionary."""
        return {"path": self.file_path, "sha256": self.sha256}

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> DependencyFingerprint | None:
        """Rehydrate a serialized dependency fingerprint when it is valid."""
        file_path = payload.get("path")
        sha256 = payload.get("sha256")
        if not isinstance(file_path, str) or not isinstance(sha256, str):
            return None
        return cls(file_path=file_path, sha256=sha256)


class ConversionCache:
    """Load, query, and update a JSON cache manifest stored on disk."""

    def __init__(self, manifest_path: str) -> None:
        self.manifest_path = manifest_path
        self._entries: dict[str, dict[str, object]] = {}
        self._loaded = False
        self._lock = RLock()

    def _load(self) -> None:
        """Load the manifest file on first use."""
        if self._loaded:
            return
        self._loaded = True
        if not path.isfile(self.manifest_path):
            return
        try:
            with open(self.manifest_path, encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError):
            return
        if isinstance(payload, dict):
            raw_entries = payload.get("entries")
            if isinstance(raw_entries, dict):
                self._entries = {str(key): value for key, value in raw_entries.items() if isinstance(value, dict)}

    def _save(self) -> None:
        """Persist the current manifest to disk."""
        manifest_dir = path.dirname(self.manifest_path)
        if manifest_dir and not path.isdir(manifest_dir):
            return
        payload = {"entries": self._entries}
        write_text_atomically(self.manifest_path, json.dumps(payload, indent=2, sort_keys=True))

    @staticmethod
    def key_for(source_path: str, output_path: str) -> str:
        """Return the stable manifest key for one source/output pair."""
        return f"{path.abspath(source_path)}::{path.abspath(output_path)}"

    def get_cached_report(
        self,
        source_path: str,
        output_path: str,
        *,
        options_signature: str,
    ) -> ConversionReport | None:
        """Return a cached report when the input, output, and dependencies are unchanged."""
        with self._lock:
            self._load()
            cache_key = self.key_for(source_path, output_path)
            entry = self._entries.get(cache_key)
            if not isinstance(entry, dict):
                return None

            if entry.get("options_signature") != options_signature:
                return None
            if not path.isfile(output_path):
                return None

            report_payload = entry.get("report")
            if not isinstance(report_payload, dict):
                return None

            fingerprints = entry.get("fingerprints")
            if not isinstance(fingerprints, list):
                return None

            expected: list[DependencyFingerprint] = []
            for item in fingerprints:
                if not isinstance(item, dict):
                    return None
                fingerprint = DependencyFingerprint.from_dict(item)
                if fingerprint is None:
                    return None
                expected.append(fingerprint)

            for fingerprint in expected:
                current_hash = _sha256_file(fingerprint.file_path)
                if current_hash != fingerprint.sha256:
                    return None

            report = ConversionReport.from_dict(report_payload)
            report.cached = True
            report.output_path = output_path
            return report

    def update(
        self,
        source_path: str,
        output_path: str,
        *,
        options_signature: str,
        report: ConversionReport,
    ) -> None:
        """Store or refresh the manifest entry for one successful conversion."""
        with self._lock:
            self._load()
            fingerprint_paths = [path.abspath(source_path), *[path.abspath(dep) for dep in report.dependencies]]
            fingerprints: list[DependencyFingerprint] = []
            for dependency_path in fingerprint_paths:
                digest = _sha256_file(dependency_path)
                if digest is None:
                    continue
                fingerprints.append(DependencyFingerprint(file_path=dependency_path, sha256=digest))

            cache_key = self.key_for(source_path, output_path)
            self._entries[cache_key] = {
                "options_signature": options_signature,
                "fingerprints": [fingerprint.to_dict() for fingerprint in fingerprints],
                "report": report.to_dict(),
            }
            self._save()


def default_manifest_path(output_path: str, output_dir: str | None) -> str:
    """Return the cache manifest path used for one conversion output."""
    base_dir = path.abspath(output_dir) if output_dir else path.dirname(path.abspath(output_path))
    return path.join(base_dir, ".svg-to-drawio-cache.json")
