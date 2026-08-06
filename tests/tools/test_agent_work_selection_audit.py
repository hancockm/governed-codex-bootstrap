from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[2] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import agent_work_selection_audit as audit  # noqa: E402


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=root, text=True, capture_output=True, check=True
    )
    return result.stdout.strip()


def _repository(tmp_path: Path, *, source_bytes: bytes | None = None) -> tuple[Path, str]:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.invalid")
    _git(root, "config", "user.name", "Test")
    raw = source_bytes or b"# Evidence\n\n## Gate\n\nExact candidate evidence.\n\n## Later\n"
    (root / "evidence.md").write_bytes(raw)
    (root / "disposition.md").write_text("accepted\n", encoding="utf-8")
    _git(root, "add", "evidence.md", "disposition.md")
    _git(root, "commit", "-q", "-m", "fixture")
    return root, _git(root, "rev-parse", "HEAD")


def _payload(commit: str, *, atom_ids: tuple[str, ...] = ("A1",)) -> dict:
    section = "\nExact candidate evidence.\n\n"
    atoms = [
        {"atom_id": atom_id, "excerpt": "Exact candidate evidence."}
        for atom_id in atom_ids
    ]
    findings = [
        {
            "atom_id": atom_id,
            "relation": "supports",
            "resolution": "verified",
            "authority": "canonical",
            "owner": "Core",
            "candidate_effect": "supports",
            "disposition_ref": "",
        }
        for atom_id in atom_ids
    ]
    return {
        "schema_version": "agent_work_selection_audit_v1",
        "authority": "source_only",
        "audit_kind": "live",
        "agent_role": "Core",
        "thread_id": "thread:CaseSensitive",
        "created_utc": "2026-07-21T12:00:00Z",
        "repository_commit": commit,
        "candidate": {
            "candidate_id": "Candidate:Opaque/Case",
            "owner": "Core",
            "summary": "Test one candidate.",
        },
        "sources": [
            {
                "source_id": "source:One",
                "path": "evidence.md",
                "heading_line": "## Gate",
                "section_sha256": hashlib.sha256(section.encode()).hexdigest(),
                "atoms": atoms,
            }
        ],
        "findings": findings,
        "prerequisites": [],
        "selection": {
            "status": "selectable",
            "blocking_atom_ids": [],
            "blocking_prerequisite_ids": [],
            "rationale": "All declared candidate prerequisites are satisfied.",
        },
        "supersedes_payload_sha256": "",
    }


def _write_audit(directory: Path, payload: dict, *, prefix: str = "audit") -> Path:
    encoded, _ = audit.canonical_payload(payload)
    digest = hashlib.sha256(encoded).hexdigest()
    path = directory / f"{prefix}-{digest[:12]}.md"
    body = (
        f"{audit.PREAMBLE}\n\n# Audit\n\n"
        "## Common Agreement\n\nDeclared evidence is pinned.\n\n"
        "## All Remaining Disagreements\n\nSemantic completeness remains open.\n\n"
        "## Critical Weak Points\n\nThe evidence universe is open.\n\n"
        "## Convergence Move\n\nValidate the record.\n\n"
        "## Decision Status\n\nPilot record.\n\n"
        "## Audit Payload\n\n"
        f"{audit.AUDIT_START}\n```json\n"
        f"{json.dumps(payload, indent=2)}\n```\n{audit.AUDIT_END}\n"
    )
    path.write_text(body, encoding="utf-8")
    return path


def _manifest(root: Path, roles: list[str], fixture_path: Path) -> dict:
    fixture = audit.load_audit_payload(fixture_path)
    return {
        "schema_version": "agent_work_selection_pilot_v1",
        "authority": "source_only",
        "audit_directory": fixture_path.parent.relative_to(root).as_posix(),
        "required_roles": roles,
        "bootstrap_fixtures": [
            {
                "fixture_id": "D7-coverage",
                "audit_path": fixture_path.relative_to(root).as_posix(),
                "counts_toward_role_coverage": False,
                "expected_atom_ids": [
                    atom["atom_id"]
                    for source in fixture["sources"]
                    for atom in source["atoms"]
                ],
                "evidence_commits": [fixture["repository_commit"]],
            }
        ],
    }


def test_bom_newline_and_atx_section_normalization() -> None:
    raw = (
        b"\xef\xbb\xbf# Root\r\n\r\n```markdown\r\n## Gate\r\nignored\r\n```\r\n"
        b"## Gate\r\n\r\nkeep  \r\n### Child\r\nchild\r\n## Next\r\n"
    )
    text = audit.normalize_text_bytes(raw)

    assert audit.extract_atx_section(text, "## Gate") == "\nkeep  \n### Child\nchild\n"
    assert "\r" not in text


def test_atx_heading_must_be_exact_unique_and_outside_fence() -> None:
    with pytest.raises(audit.AuditValidationError, match="not unique"):
        audit.extract_atx_section("## Gate\nA\n## Gate\nB\n", "## Gate")
    with pytest.raises(audit.AuditValidationError, match="not found"):
        audit.extract_atx_section("```\n## Gate\n```\n", "## Gate")
    with pytest.raises(audit.AuditValidationError, match="one exact line"):
        audit.extract_atx_section("## Gate\n", "## Gate\n")


@pytest.mark.parametrize(
    "value",
    ["../secret.md", "/secret.md", "C" + ":\\secret.md", "C" + ":secret.md"],
)
def test_repository_paths_cannot_escape_or_use_windows_drives(value: str) -> None:
    with pytest.raises(audit.AuditValidationError):
        audit.normalize_repo_path(value)


def test_validation_reads_pinned_git_bytes_not_worktree(tmp_path: Path) -> None:
    root, commit = _repository(tmp_path)
    payload = _payload(commit)
    record = _write_audit(root, payload)
    (root / "evidence.md").write_text("## Gate\nchanged\n", encoding="utf-8")

    result = audit.validate_audit(record, root=root)

    assert result.valid
    assert result.candidate_status == "selectable"


def test_content_address_atom_coverage_and_exact_excerpt(tmp_path: Path) -> None:
    root, commit = _repository(tmp_path)
    payload = _payload(commit)
    valid = _write_audit(root, payload)
    assert audit.validate_audit(valid, root=root).valid

    bad_name = root / "wrong-name.md"
    bad_name.write_text(valid.read_text(encoding="utf-8"), encoding="utf-8")
    assert "filename" in " ".join(audit.validate_audit(bad_name, root=root).errors)

    duplicate = copy.deepcopy(payload)
    duplicate["sources"][0]["atoms"].append(copy.deepcopy(duplicate["sources"][0]["atoms"][0]))
    duplicate["findings"].append(copy.deepcopy(duplicate["findings"][0]))
    duplicate_path = _write_audit(root, duplicate, prefix="duplicate")
    errors = " ".join(audit.validate_audit(duplicate_path, root=root).errors)
    assert "atom_id values must be globally unique" in errors
    assert "finding atom IDs must be unique" in errors

    missing = copy.deepcopy(payload)
    missing["findings"] = []
    missing_path = _write_audit(root, missing, prefix="missing")
    assert "cover the declared atom IDs exactly" in " ".join(
        audit.validate_audit(missing_path, root=root).errors
    )

    absent_excerpt = copy.deepcopy(payload)
    absent_excerpt["sources"][0]["atoms"][0]["excerpt"] = "not present"
    absent_path = _write_audit(root, absent_excerpt, prefix="excerpt")
    assert "occur exactly once" in " ".join(
        audit.validate_audit(absent_path, root=root).errors
    )


@pytest.mark.parametrize(
    ("resolution", "prerequisite_status", "expected"),
    [
        ("unverified", "unsatisfied", "not_selectable"),
        ("owner_disposition_required", "owner_disposition_required", "owner_disposition_required"),
        ("user_approval_required", "user_approval_required", "user_approval_required"),
    ],
)
def test_candidate_specific_blockers_and_prerequisite_routing(
    tmp_path: Path,
    resolution: str,
    prerequisite_status: str,
    expected: str,
) -> None:
    root, commit = _repository(tmp_path)
    payload = _payload(commit)
    finding = payload["findings"][0]
    finding.update(candidate_effect="blocks", resolution=resolution)
    if resolution == "owner_disposition_required":
        finding["disposition_ref"] = "disposition.md"
    payload["prerequisites"] = [
        {
            "prerequisite_id": "P1",
            "owner": (
                "Another Owner"
                if prerequisite_status == "owner_disposition_required"
                else "Core"
            ),
            "required": True,
            "status": prerequisite_status,
            "evidence_atom_ids": ["A1"],
            "disposition_ref": (
                "disposition.md" if prerequisite_status == "owner_disposition_required" else ""
            ),
        }
    ]
    payload["selection"].update(
        status=expected,
        blocking_atom_ids=["A1"],
        blocking_prerequisite_ids=["P1"],
    )
    record = _write_audit(root, payload)

    result = audit.validate_audit(record, root=root)

    assert result.valid
    assert result.candidate_status == expected


def test_unrelated_unresolved_atom_is_non_blocking(tmp_path: Path) -> None:
    root, commit = _repository(tmp_path)
    payload = _payload(commit)
    payload["findings"][0].update(
        relation="irrelevant", resolution="unverified", candidate_effect="non_blocking"
    )
    record = _write_audit(root, payload)

    assert audit.validate_audit(record, root=root).candidate_status == "selectable"


def test_canonicalization_preserves_opaque_strings_and_is_deterministic() -> None:
    payload = {
        "candidate_id": "Case/Sensitive:Identity",
        "path": "folder\\evidence.md",
        "text": "Line1\r\nLine2",
    }

    first, normalized = audit.canonical_payload(payload)
    second, _ = audit.canonical_payload(copy.deepcopy(payload))

    assert first == second
    assert normalized["candidate_id"] == "Case/Sensitive:Identity"
    assert normalized["path"] == "folder/evidence.md"
    assert normalized["text"] == "Line1\nLine2"


def test_structurally_valid_adverse_check_exits_zero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    root, commit = _repository(tmp_path)
    payload = _payload(commit)
    payload["findings"][0].update(
        candidate_effect="blocks", resolution="unverified"
    )
    payload["selection"].update(status="not_selectable", blocking_atom_ids=["A1"])
    record = _write_audit(root, payload)
    monkeypatch.setattr(audit, "ROOT", root)

    assert audit.main(["check", "--audit", str(record)]) == 0
    assert '"candidate_status": "not_selectable"' in capsys.readouterr().out


def test_repository_pilot_bootstrap_is_valid_and_pins_d7() -> None:
    manifest_path = audit.ROOT / "configs/work_selection_audit_v1.json"
    report, exit_code = audit.validate_pilot(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert report["valid"]
    assert report["pilot_status"] == "eligible_for_disposition"
    assert report["required_role_count"] == 1
    assert report["covered_role_count"] >= 1
    assert "Core" in report["covered_roles"]
    assert "D7" in manifest["bootstrap_fixtures"][0]["expected_atom_ids"]


def test_pilot_fixture_omitting_d7_fails_and_complete_flag_is_enforced(tmp_path: Path) -> None:
    root, commit = _repository(tmp_path)
    audits = root / "audits"
    audits.mkdir()
    fixture_payload = _payload(commit, atom_ids=("D1", "D2", "D3", "D4", "D5", "D6", "D8"))
    fixture_payload["audit_kind"] = "retrospective_fixture"
    fixture = _write_audit(audits, fixture_payload, prefix="fixture")
    manifest = _manifest(root, ["Core"], fixture)
    manifest["bootstrap_fixtures"][0]["expected_atom_ids"] = [
        "D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8"
    ]
    manifest_path = root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    report, exit_code = audit.validate_pilot(manifest_path, root=root)
    assert exit_code == 1
    assert any("declared atom IDs" in error for error in report["errors"])

    manifest["bootstrap_fixtures"][0]["expected_atom_ids"].remove("D7")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    report, exit_code = audit.validate_pilot(
        manifest_path, root=root, require_complete=True
    )
    assert exit_code == 1
    assert "pilot role coverage is incomplete" in report["errors"]


def test_all_manifest_roles_can_complete_coverage_and_unknown_roles_fail(tmp_path: Path) -> None:
    root, commit = _repository(tmp_path)
    audits = root / "audits"
    audits.mkdir()
    fixture_payload = _payload(commit)
    fixture_payload["audit_kind"] = "retrospective_fixture"
    fixture = _write_audit(audits, fixture_payload, prefix="fixture")
    roles = [f"Role {index}" for index in range(16)]
    for index, role in enumerate(roles):
        live = _payload(commit)
        live["agent_role"] = role
        live["thread_id"] = f"thread:{index}"
        _write_audit(audits, live, prefix=f"live-{index}")
    manifest = _manifest(root, roles, fixture)
    manifest_path = root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    report, exit_code = audit.validate_pilot(manifest_path, root=root, require_complete=True)
    assert exit_code == 0
    assert report["pilot_status"] == "eligible_for_disposition"
    assert report["covered_role_count"] == 16

    provider = _payload(commit)
    provider["agent_role"] = "Provider Handoff Agent"
    provider["thread_id"] = "thread:provider"
    _write_audit(audits, provider, prefix="provider")
    report, exit_code = audit.validate_pilot(manifest_path, root=root)
    assert exit_code == 1
    assert any("outside the pilot manifest" in error for error in report["errors"])


def test_missing_and_superseded_records_are_detected(tmp_path: Path) -> None:
    root, commit = _repository(tmp_path)
    audits = root / "audits"
    audits.mkdir()
    prior_payload = _payload(commit)
    prior_payload["audit_kind"] = "retrospective_fixture"
    prior = _write_audit(audits, prior_payload, prefix="prior")
    manifest = _manifest(root, ["Core"], prior)
    manifest_path = root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    successor = _payload(commit)
    successor["thread_id"] = "thread:successor"
    successor["supersedes_payload_sha256"] = "f" * 64
    _write_audit(audits, successor, prefix="successor")
    report, exit_code = audit.validate_pilot(manifest_path, root=root)
    assert exit_code == 1
    assert any("superseded audit hash is not in corpus" in error for error in report["errors"])

    manifest["bootstrap_fixtures"][0]["audit_path"] = "audits/missing.md"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    report, exit_code = audit.validate_pilot(manifest_path, root=root)
    assert exit_code == 1
    assert any("audit_path" in error and "corpus" in error for error in report["errors"])


def test_validation_commands_do_not_change_repository_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, commit = _repository(tmp_path)
    audits = root / "audits"
    audits.mkdir()
    fixture_payload = _payload(commit)
    fixture_payload["audit_kind"] = "retrospective_fixture"
    fixture = _write_audit(audits, fixture_payload, prefix="fixture")
    manifest = _manifest(root, ["Core"], fixture)
    manifest_path = root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    before = {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}
    monkeypatch.setattr(audit, "ROOT", root)

    assert audit.main([
        "section-hash", "--path", "evidence.md", "--heading-line", "## Gate", "--commit", commit
    ]) == 0
    assert audit.main(["check", "--audit", str(fixture)]) == 0
    assert audit.main(["pilot-check", "--manifest", str(manifest_path)]) == 0

    after = {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}
    assert after == before
