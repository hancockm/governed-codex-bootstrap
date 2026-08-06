"""Immutable, advisory coordination-record helpers."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .common import canonical_json

CRITIQUE_PREAMBLE = "Be critical of this input. You need to be analytical in your response.  Do not take this as the answer. Look at the weak points in the argument. Let's begin to list areas of common agreement. List areas of disagreement. The goal for each iteration is to reduce one disagreement. If each round, you eliminate one disagreement but add 2 disagreements you are going in the wrong direction.  We need to converge on a plan. List ALL remaining disagreements. Don't keep adding them after each round."
CRITIQUE_HEADINGS = ("Common Agreement", "All Remaining Disagreements", "Critical Weak Points", "Convergence Move", "Decision Status")


def content_id(value: Any) -> str:
    """Return a deterministic content identifier for an immutable record."""
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def write_immutable(path: Path, text: str) -> bool:
    """Create an immutable text record, returning false for an idempotent match.

    Raises:
        ValueError: If the target exists with different content.
    """
    if path.exists():
        if path.read_text(encoding="utf-8") != text:
            raise ValueError(f"immutable record already exists with different content: {path}")
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True


def update_index(path: Path, record_path: str, label: str) -> bool:
    """Append one path-qualified immutable-record link to a generated index."""
    marker = f"- [[{record_path}|{label}]]"
    current = path.read_text(encoding="utf-8") if path.exists() else "# Active Coordination Records\n\n"
    if marker in current:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(current.rstrip() + "\n" + marker + "\n", encoding="utf-8")
    return True
