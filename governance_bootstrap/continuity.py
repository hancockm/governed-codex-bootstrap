"""Bounded export of user-visible conversation records."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ALLOWED_ROLES = {"user", "assistant"}
SECRET_KEYS = {"authorization", "token", "api_key", "password", "secret"}


def export_bounded(source: Path, destination: Path, prefix: int) -> dict[str, Any]:
    """Export a prefix of eligible JSONL response records with hashes.

    The source remains immutable; the export deliberately omits non-response records
    and records containing credential-shaped top-level keys.
    """
    selected: list[dict[str, Any]] = []
    for raw in source.read_text(encoding="utf-8").splitlines()[:prefix]:
        item = json.loads(raw)
        if item.get("type") != "response_item" or item.get("role") not in ALLOWED_ROLES:
            continue
        if SECRET_KEYS & set(item):
            continue
        selected.append({"type": "response_item", "role": item["role"], "content": item.get("content", "")})
    payload = "\n".join(json.dumps(item, sort_keys=True) for item in selected) + ("\n" if selected else "")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(payload, encoding="utf-8")
    return {"source_prefix": prefix, "selected_records": len(selected), "sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest()}
