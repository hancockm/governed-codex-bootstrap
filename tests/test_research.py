from __future__ import annotations

import json
from pathlib import Path
import subprocess

import pytest

from governance_bootstrap.git_research import (
    GitBlob,
    GitCliRepositoryAdapter,
    GitRepositorySnapshot,
    GitResearchError,
    capture_git_repository,
    validate_repository_url,
)
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


def test_git_adapter_publishes_exact_bounded_snapshot_and_organizer_reads_it(
    tmp_path: Path,
) -> None:
    root = research_root(tmp_path)
    repository_url = "https://github.com/example/reference-project.git"
    requested_ref = "refs/tags/v1.0.0"
    commit = "a" * 40
    snapshot = GitRepositorySnapshot(
        repository_url=repository_url,
        requested_ref=requested_ref,
        commit=commit,
        tree="b" * 40,
        tree_entry_count=4,
        blobs=(
            GitBlob("README.md", "100644", "c" * 40, b"# Reference\nExact evidence.\n"),
            GitBlob("docs/guide.txt", "100644", "d" * 40, b"Bounded guide evidence.\n"),
        ),
    )

    class StaticAdapter:
        def snapshot(self, **_: object) -> GitRepositorySnapshot:
            return snapshot

    first = capture_git_repository(
        root,
        StaticAdapter(),
        repository_url=repository_url,
        requested_ref=requested_ref,
        expected_commit=commit,
        title="Reference project",
        network_authorized=True,
    )
    second = capture_git_repository(
        root,
        StaticAdapter(),
        repository_url=repository_url,
        requested_ref=requested_ref,
        expected_commit=commit,
        title="Reference project",
        network_authorized=True,
    )

    assert first == second
    record = root / "research/records" / str(first["source_id"])
    assert (record / "README.md").read_bytes() == snapshot.blobs[0].payload
    assert (record / "docs/guide.txt").read_bytes() == snapshot.blobs[1].payload
    manifest = json.loads((record / "snapshot.json").read_text(encoding="utf-8"))
    assert manifest["commit"] == commit
    assert manifest["tree"] == "b" * 40
    assert [item["path"] for item in manifest["files"]] == [
        "README.md",
        "docs/guide.txt",
    ]
    mapped = build(root)
    assert {item["source"] for item in mapped["candidates"]} == {
        f"research/records/{first['source_id']}/README.md",
        f"research/records/{first['source_id']}/docs/guide.txt",
    }


def test_git_adapter_requires_explicit_authorization_and_exact_safe_identity(
    tmp_path: Path,
) -> None:
    root = research_root(tmp_path)

    class UnexpectedAdapter:
        def snapshot(self, **_: object) -> GitRepositorySnapshot:
            raise AssertionError("adapter must not run without authorization")

    with pytest.raises(GitResearchError, match="explicit network authorization"):
        capture_git_repository(
            root,
            UnexpectedAdapter(),
            repository_url="https://github.com/example/reference.git",
            requested_ref="refs/heads/main",
            expected_commit="a" * 40,
            title="Reference",
        )
    with pytest.raises(GitResearchError, match="credential-free HTTPS"):
        validate_repository_url("https://token@github.com/example/reference.git")


def test_git_adapter_rejects_identity_drift(tmp_path: Path) -> None:
    root = research_root(tmp_path)
    repository_url = "https://github.com/example/reference.git"
    requested_ref = "refs/heads/main"
    commit = "a" * 40

    class DriftedAdapter:
        def snapshot(self, **_: object) -> GitRepositorySnapshot:
            return GitRepositorySnapshot(
                repository_url=repository_url,
                requested_ref=requested_ref,
                commit="f" * 40,
                tree="b" * 40,
                tree_entry_count=1,
                blobs=(GitBlob("README.md", "100644", "c" * 40, b"evidence"),),
            )

    with pytest.raises(GitResearchError, match="identity does not match"):
        capture_git_repository(
            root,
            DriftedAdapter(),
            repository_url=repository_url,
            requested_ref=requested_ref,
            expected_commit=commit,
            title="Reference",
            network_authorized=True,
        )


def test_git_adapter_rejects_lfs_pointer_as_document_content(tmp_path: Path) -> None:
    root = research_root(tmp_path)
    repository_url = "https://github.com/example/reference.git"
    requested_ref = "refs/heads/main"
    commit = "a" * 40

    class LfsPointerAdapter:
        def snapshot(self, **_: object) -> GitRepositorySnapshot:
            return GitRepositorySnapshot(
                repository_url=repository_url,
                requested_ref=requested_ref,
                commit=commit,
                tree="b" * 40,
                tree_entry_count=1,
                blobs=(
                    GitBlob(
                        "report.pdf",
                        "100644",
                        "c" * 40,
                        b"version https://git-lfs.github.com/spec/v1\n"
                        b"oid sha256:deadbeef\nsize 42\n",
                    ),
                ),
            )

    with pytest.raises(GitResearchError, match="Git LFS pointer"):
        capture_git_repository(
            root,
            LfsPointerAdapter(),
            repository_url=repository_url,
            requested_ref=requested_ref,
            expected_commit=commit,
            title="Reference",
            network_authorized=True,
        )


def test_git_adapter_rejects_nonportable_paths(tmp_path: Path) -> None:
    root = research_root(tmp_path)
    repository_url = "https://github.com/example/reference.git"
    requested_ref = "refs/heads/main"
    commit = "a" * 40

    class UnsafePathAdapter:
        def snapshot(self, **_: object) -> GitRepositorySnapshot:
            return GitRepositorySnapshot(
                repository_url=repository_url,
                requested_ref=requested_ref,
                commit=commit,
                tree="b" * 40,
                tree_entry_count=1,
                blobs=(GitBlob("docs/CON.txt", "100644", "c" * 40, b"evidence"),),
            )

    with pytest.raises(GitResearchError, match="not portable"):
        capture_git_repository(
            root,
            UnsafePathAdapter(),
            repository_url=repository_url,
            requested_ref=requested_ref,
            expected_commit=commit,
            title="Reference",
            network_authorized=True,
        )


def test_git_cli_adapter_reads_regular_supported_blobs_without_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    commit = "a" * 40
    tree = "b" * 40
    blob = "c" * 40
    payload = b"# Exact repository evidence\n"
    observed: list[tuple[list[str], str]] = []

    def fake_run(
        _: str, arguments: list[str], operation: str
    ) -> subprocess.CompletedProcess[bytes]:
        observed.append((arguments, operation))
        if "rev-parse" in arguments:
            output = (commit + "\n").encode()
        elif "--format=%T" in arguments:
            output = (tree + "\n").encode()
        elif "ls-tree" in arguments:
            output = (
                f"100644 blob {blob} {len(payload)}\tdocs/README.md\0"
                f"160000 commit {'d' * 40} -\tvendor/submodule\0"
                f"100644 blob {'e' * 40} 4\tsrc/code.py\0"
            ).encode()
        elif "cat-file" in arguments:
            output = payload
        else:
            output = b""
        return subprocess.CompletedProcess(arguments, 0, stdout=output, stderr=b"")

    monkeypatch.setattr("shutil.which", lambda _: "git")
    monkeypatch.setattr(GitCliRepositoryAdapter, "_run", staticmethod(fake_run))
    adapter = GitCliRepositoryAdapter(tmp_path / "tmp")

    snapshot = adapter.snapshot(
        repository_url="https://github.com/example/reference.git",
        requested_ref="refs/heads/main",
        expected_commit=commit,
        include_prefixes=("docs",),
        max_files=10,
        max_file_bytes=1024,
        max_total_bytes=2048,
        network_authorized=True,
    )

    assert snapshot.commit == commit
    assert snapshot.tree == tree
    assert snapshot.tree_entry_count == 3
    assert snapshot.blobs == (GitBlob("docs/README.md", "100644", blob, payload),)
    assert any("fetch" in arguments for arguments, _ in observed)
    assert not list((tmp_path / "tmp").glob("git-research-fetch-*"))

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
