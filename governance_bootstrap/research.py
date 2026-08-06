"""Immutable research intake."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from .common import sha256_file


def intake(root: Path, source: Path, title: str, origin: str) -> dict[str, str]:
    """Copy source material into a content-addressed immutable research record.

    Raises:
        ValueError: If the source is outside the research inbox or metadata is incomplete.
    """
    inbox = (root / "research/inbox").resolve()
    source = source.resolve()
    if inbox not in source.parents or not title.strip() or not origin.strip():
        raise ValueError("source must be inside research/inbox and title/origin are required")
    digest = sha256_file(source)
    record_id = f"research-{digest[:12]}"
    destination = root / "research/records" / f"{record_id}{source.suffix.lower()}"
    metadata_path = root / "research/records" / f"{record_id}.json"
    if destination.exists() and sha256_file(destination) != digest:
        raise ValueError("content-address collision detected")
    if not destination.exists():
        shutil.copy2(source, destination)
    metadata = {
        "record_id": record_id,
        "title": title,
        "origin": origin,
        "source_filename": source.name,
        "sha256": digest,
        "ingested_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }
    if metadata_path.exists():
        existing = json.loads(metadata_path.read_text(encoding="utf-8"))
        if {key: existing[key] for key in ("record_id", "sha256", "source_filename")} != {key: metadata[key] for key in ("record_id", "sha256", "source_filename")}:
            raise ValueError("immutable metadata conflicts with existing record")
        return existing
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return metadata
