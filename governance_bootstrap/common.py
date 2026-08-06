"""Shared deterministic file helpers."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    """Return the SHA-256 digest of a file."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_json(value: Any) -> str:
    """Serialize finite JSON-safe values into the canonical v1 representation."""

    _validate_canonical_value(value)
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def sha256_canonical(value: Any) -> str:
    """Return SHA-256 over canonical JSON UTF-8 bytes."""

    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _validate_canonical_value(value: Any) -> None:
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise TypeError("canonical JSON object keys must be strings")
        for item in value.values():
            _validate_canonical_value(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _validate_canonical_value(item)


_WINDOWS_PATH_FRAGMENT = re.compile(r"[a-zA-Z]:[\\/]")
_POSIX_PATH_FRAGMENT = re.compile(
    r"(?:^|\s)/(?:users|home|srv|var|tmp|etc)/",
    re.IGNORECASE,
)
_PRIVATE_FRAGMENTS = (
    ".config/",
    ".config\\",
    ".cache/",
    ".cache\\",
    "appdata/",
    "appdata\\",
    "state.db",
    "history.json",
    "sessions.json",
    "provider-private",
    "provider_private",
)
_CREDENTIAL_ASSIGNMENTS = (
    "api_key=",
    "apikey=",
    "password=",
    "token=",
    "secret=",
)


def validate_safe_diagnostic(field_name: str, value: str) -> None:
    """Reject multiline, path-bearing, private, or credential diagnostics."""

    if not value.strip() or value != value.strip() or "\n" in value or "\r" in value:
        raise ValueError(f"{field_name} must contain trimmed single-line diagnostic text")
    lowered = value.lower()
    if (
        _WINDOWS_PATH_FRAGMENT.search(value)
        or _POSIX_PATH_FRAGMENT.search(value)
        or lowered.startswith(("file:", "/", "\\"))
    ):
        raise ValueError(f"{field_name} cannot contain a filesystem path")
    if any(fragment in lowered for fragment in _PRIVATE_FRAGMENTS):
        raise ValueError(f"{field_name} cannot contain private storage references")
    if any(fragment in lowered for fragment in _CREDENTIAL_ASSIGNMENTS):
        raise ValueError(f"{field_name} cannot contain credentials")
