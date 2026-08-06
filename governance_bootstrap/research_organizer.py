"""Deterministic, source-preserving research organization."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .common import canonical_json, sha256_file

SUPPORTED_SUFFIXES = {".md", ".txt"}
STATUSES = {"current", "candidate", "superseded", "deadend_candidate", "evidence", "source"}


def _record_sources(root: Path) -> list[Path]:
    return sorted(path for path in (root / "research/records").iterdir() if path.suffix.lower() in SUPPORTED_SUFFIXES)


def _sections(path: Path) -> list[dict[str, str]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    parts = re.split(r"(?m)^(#{1,6}\s+.+)$", text)
    result: list[dict[str, str]] = []
    title = path.stem
    body = parts[0]
    if body.strip():
        result.append({"title": title, "text": body.strip()})
    for index in range(1, len(parts), 2):
        title = parts[index].lstrip("#").strip()
        body = parts[index + 1].strip()
        if body:
            result.append({"title": title, "text": body})
    return result or [{"title": title, "text": ""}]


def scan(root: Path) -> dict[str, Any]:
    """Report supported and unsupported immutable source records without mutation."""
    records = root / "research/records"
    sources = _record_sources(root)
    unsupported = sorted(path.name for path in records.iterdir() if path.is_file() and not path.name.startswith(".") and path.suffix.lower() not in SUPPORTED_SUFFIXES | {".json"})
    return {"supported": [{"path": path.relative_to(root).as_posix(), "sha256": sha256_file(path)} for path in sources], "unsupported": unsupported}


def build(root: Path) -> dict[str, Any]:
    """Build a reproducible map; never mutate source records or canonical documents."""
    chunks: list[dict[str, Any]] = []
    for source in _record_sources(root):
        source_hash = sha256_file(source)
        for index, section in enumerate(_sections(source)):
            normalized = " ".join(section["text"].lower().split())
            fingerprint = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
            source_key = source.relative_to(root).as_posix()
            candidate_id = f"candidate-{hashlib.sha256((source_key + source_hash + str(index)).encode()).hexdigest()[:12]}"
            words = set(re.findall(r"[a-z0-9_]+", normalized))
            inferred = "deadend_candidate" if any(term in normalized for term in ("dead end", "superseded", "obsolete")) else "candidate"
            chunks.append({"candidate_id": candidate_id, "source": source_key, "source_sha256": source_hash, "section": section["title"], "section_index": index, "fingerprint": fingerprint, "status": inferred, "word_set": sorted(words)})
    for chunk in chunks:
        duplicates = []
        own = set(chunk["word_set"])
        for other in chunks:
            if other["candidate_id"] == chunk["candidate_id"]:
                continue
            other_words = set(other["word_set"])
            union = own | other_words
            similarity = len(own & other_words) / len(union) if union else 1.0
            if chunk["fingerprint"] == other["fingerprint"]:
                duplicates.append({"candidate_id": other["candidate_id"], "kind": "exact"})
            elif similarity >= 0.85:
                duplicates.append({"candidate_id": other["candidate_id"], "kind": "near", "similarity": round(similarity, 4)})
        chunk["duplicates"] = sorted(duplicates, key=lambda item: item["candidate_id"])
    for chunk in chunks:
        del chunk["word_set"]
    result = {"schema_version": 1, "candidates": sorted(chunks, key=lambda item: item["candidate_id"])}
    output = root / "research/derived/research_map.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def review(root: Path, candidate_id: str, status: str, reason: str) -> dict[str, str]:
    """Write a separate human review decision for a map candidate."""
    if status not in STATUSES or not reason.strip():
        raise ValueError("a permitted status and nonempty reason are required")
    map_path = root / "research/derived/research_map.json"
    candidates = json.loads(map_path.read_text(encoding="utf-8"))["candidates"]
    if candidate_id not in {item["candidate_id"] for item in candidates}:
        raise ValueError("unknown candidate")
    decision = {"candidate_id": candidate_id, "status": status, "reason": reason}
    output = root / "research/reviews" / f"{candidate_id}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(canonical_json(decision) + "\n", encoding="utf-8")
    return decision


def may_enter_canonical(root: Path, candidate_id: str) -> bool:
    """Return true only for a separately reviewed, explicitly current candidate."""
    decision = root / "research/reviews" / f"{candidate_id}.json"
    return decision.is_file() and json.loads(decision.read_text(encoding="utf-8")).get("status") == "current"
