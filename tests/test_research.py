from __future__ import annotations

import json
from pathlib import Path

import pytest

from governance_bootstrap.research import intake
from governance_bootstrap.research_organizer import build, may_enter_canonical, review, scan


def research_root(tmp_path: Path) -> Path:
    (tmp_path / "research/inbox").mkdir(parents=True)
    (tmp_path / "research/records").mkdir()
    (tmp_path / "Project_Obsidian_Vault/00_Canonical").mkdir(parents=True)
    (tmp_path / "Project_Obsidian_Vault/00_Canonical/Core Thesis.md").write_text("unchanged\n", encoding="utf-8")
    return tmp_path


def test_intake_copies_content_addressed_source_and_is_idempotent(tmp_path: Path) -> None:
    root = research_root(tmp_path)
    source = root / "research/inbox/notes.md"
    source.write_text("evidence", encoding="utf-8")
    first = intake(root, source, "Notes", "interview")
    second = intake(root, source, "Notes", "interview")
    assert first["record_id"] == second["record_id"]
    assert (root / "research/records" / f"{first['record_id']}.md").read_text(encoding="utf-8") == "evidence"


def test_organizer_is_repeatable_and_preserves_exact_duplicate_provenance(tmp_path: Path) -> None:
    root = research_root(tmp_path)
    (root / "research/records/a.md").write_text("# Same\nA stable finding.", encoding="utf-8")
    (root / "research/records/b.md").write_text("# Same\nA stable finding.", encoding="utf-8")
    first = build(root)
    second = build(root)
    assert first == second
    assert all(item["duplicates"] for item in first["candidates"])
    assert scan(root)["unsupported"] == []


def test_deadend_candidate_never_enters_canonical_without_explicit_review(tmp_path: Path) -> None:
    root = research_root(tmp_path)
    (root / "research/records/a.md").write_text("# Retired\nThis is obsolete and superseded.", encoding="utf-8")
    candidate = build(root)["candidates"][0]
    assert candidate["status"] == "deadend_candidate"
    assert not may_enter_canonical(root, candidate["candidate_id"])
    review(root, candidate["candidate_id"], "superseded", "replaced by later evidence")
    assert not may_enter_canonical(root, candidate["candidate_id"])
    assert (root / "Project_Obsidian_Vault/00_Canonical/Core Thesis.md").read_text(encoding="utf-8") == "unchanged\n"


def test_review_rejects_unknown_status(tmp_path: Path) -> None:
    root = research_root(tmp_path)
    (root / "research/records/a.md").write_text("x", encoding="utf-8")
    candidate = build(root)["candidates"][0]
    with pytest.raises(ValueError):
        review(root, candidate["candidate_id"], "accepted", "not a permitted source status")
