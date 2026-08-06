"""Idempotent bounded export of user-visible conversation records."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ALLOWED_ROLES = {"user", "assistant"}
SECRET_KEYS = {"authorization", "token", "api_key", "password", "secret", "credential", "cookie"}


def _has_secret(value: Any) -> bool:
    """Return whether a nested record contains a credential-shaped key."""
    if isinstance(value, dict):
        return any(str(key).lower() in SECRET_KEYS or _has_secret(item) for key, item in value.items())
    if isinstance(value, list):
        return any(_has_secret(item) for item in value)
    return False


def _full_line_prefix(source: Path, prefix: int) -> bytes:
    """Return exactly prefix complete physical lines, rejecting partial boundaries."""
    if prefix < 0:
        raise ValueError("prefix must be nonnegative")
    raw = source.read_bytes()
    lines = raw.splitlines(keepends=True)
    if prefix > len(lines):
        raise ValueError("prefix exceeds source line count")
    selected = lines[:prefix]
    if selected and not selected[-1].endswith((b"\n", b"\r")):
        raise ValueError("source prefix must end at a stable full-line boundary")
    return b"".join(selected)


def export_bounded(source: Path, destination: Path, prefix: int) -> dict[str, Any]:
    """Export a full-line source prefix's safe user/assistant response records.

    Tool events, private records, non-string content, and records with any
    credential-shaped nested key are excluded. Repeating the export with the same
    source prefix produces byte-identical output and metadata.
    """
    prefix_bytes = _full_line_prefix(source, prefix)
    selected: list[dict[str, str]] = []
    selected_hashes: list[str] = []
    for raw_line in prefix_bytes.splitlines():
        item = json.loads(raw_line.decode("utf-8"))
        if item.get("type") != "response_item" or item.get("role") not in ALLOWED_ROLES:
            continue
        if _has_secret(item) or not isinstance(item.get("content", ""), str):
            continue
        record = {"type": "response_item", "role": item["role"], "content": item.get("content", "")}
        encoded = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        selected.append(record)
        selected_hashes.append(hashlib.sha256(encoded.encode("utf-8")).hexdigest())
    payload = "\n".join(json.dumps(item, sort_keys=True, separators=(",", ":"), ensure_ascii=True) for item in selected) + ("\n" if selected else "")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists() or destination.read_text(encoding="utf-8") != payload:
        destination.write_text(payload, encoding="utf-8")
    return {
        "source_prefix": {"line_count": prefix, "sha256": hashlib.sha256(prefix_bytes).hexdigest()},
        "selected_records": len(selected),
        "selected_record_hashes": selected_hashes,
        "selected_sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
    }
