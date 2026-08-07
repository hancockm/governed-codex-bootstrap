from __future__ import annotations

import json
from pathlib import Path

import pytest

from governance_bootstrap.research import intake
from governance_bootstrap import research_organizer as organizer
from governance_bootstrap.research_organizer import (
    ResearchDependencyUnavailable,
    ResearchExtractionError,
    build,
    may_enter_canonical,
    review,
    scan,
)


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


def test_intake_preserves_exact_pdf_bytes_without_loading_a_parser(tmp_path: Path) -> None:
    root = research_root(tmp_path)
    source = root / "research/inbox/report.pdf"
    payload = b"%PDF-1.7\nexact research bytes\n%%EOF\n"
    source.write_bytes(payload)

    record = intake(root, source, "Report", "publisher")

    assert (root / "research/records" / f"{record['record_id']}.pdf").read_bytes() == payload


def test_organizer_is_repeatable_and_preserves_exact_duplicate_provenance(tmp_path: Path) -> None:
    root = research_root(tmp_path)
    (root / "research/records/README.md").write_text("folder instructions", encoding="utf-8")
    (root / "research/records/a.md").write_text("# Same\nA stable finding.", encoding="utf-8")
    (root / "research/records/b.md").write_text("# Same\nA stable finding.", encoding="utf-8")
    first = build(root)
    second = build(root)
    assert first == second
    assert all(item["duplicates"] for item in first["candidates"])
    assert all(item["source"] != "research/records/README.md" for item in first["candidates"])
    assert scan(root)["unsupported"] == []


def test_scan_reports_pdf_dependency_unavailable_instead_of_skipping(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = research_root(tmp_path)
    (root / "research/records/report.pdf").write_bytes(b"%PDF-1.7\n%%EOF\n")

    def unavailable() -> type[object]:
        raise ResearchDependencyUnavailable("approved PDF parser is unavailable")

    monkeypatch.setattr(organizer, "_pdf_reader_type", unavailable)

    report = scan(root)
    assert report["supported"] == []
    assert report["unsupported"] == []
    assert report["unavailable"][0]["reason"] == "pdf_dependency_unavailable"
    assert report["unavailable"][0]["detail"] == "approved PDF parser is unavailable"
    with pytest.raises(ResearchDependencyUnavailable, match="approved PDF parser"):
        build(root)


def test_pdf_pages_are_extracted_in_order_with_empty_pages_visible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = research_root(tmp_path)
    (root / "research/records/report.pdf").write_bytes(b"%PDF-1.7\n%%EOF\n")

    class Page:
        def __init__(self, text: str | None) -> None:
            self.text = text

        def extract_text(self) -> str | None:
            return self.text

    class Reader:
        is_encrypted = False

        def __init__(self, path: str) -> None:
            assert path.endswith("report.pdf")
            self.pages = [Page("First page evidence."), Page(None)]

    monkeypatch.setattr(organizer, "_pdf_reader_type", lambda: Reader)

    first = build(root)
    second = build(root)
    assert first == second
    pages = sorted(first["candidates"], key=lambda item: item["page_number"])
    assert [item["section"] for item in pages] == ["Page 1", "Page 2"]
    assert [item["extraction_status"] for item in pages] == [
        "extracted",
        "no_extractable_text",
    ]
    assert all(item["media_type"] == "application/pdf" for item in pages)
    assert first["diagnostics"] == [
        {
            "candidate_id": pages[1]["candidate_id"],
            "source": "research/records/report.pdf",
            "status": "no_extractable_text",
        }
    ]


def test_encrypted_pdf_fails_without_requesting_or_storing_passwords(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = research_root(tmp_path)
    (root / "research/records/report.pdf").write_bytes(b"%PDF-1.7\n%%EOF\n")

    class Reader:
        is_encrypted = True
        pages: list[object] = []

        def __init__(self, path: str) -> None:
            assert path.endswith("report.pdf")

    monkeypatch.setattr(organizer, "_pdf_reader_type", lambda: Reader)

    with pytest.raises(ResearchExtractionError, match="does not request or store passwords"):
        build(root)


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
