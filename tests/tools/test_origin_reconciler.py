from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[2] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import origin_reconciler as reconciler  # noqa: E402


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROJECT_CONFIG = (
    PROJECT_ROOT / "configs/git_reconciliation_v1.json"
)


def _run(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        list(args), cwd=root, text=True, capture_output=True, check=False
    )
    if check and result.returncode != 0:
        raise AssertionError(
            f"command failed ({result.returncode}): {' '.join(args)}\n{result.stderr}"
        )
    return result


def _git(root: Path, *args: str) -> str:
    return _run(root, "git", *args).stdout.strip()


def _write(root: Path, relative: str, value: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def _commit(root: Path, message: str, relative: str, value: str) -> str:
    _write(root, relative, value)
    _git(root, "add", relative)
    _git(root, "commit", "-q", "-m", message)
    return _git(root, "rev-parse", "HEAD")


def _repository(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "repo"
    remote = tmp_path / "origin.git"
    root.mkdir()
    _git(root, "init", "-q", "-b", "master")
    _git(root, "config", "user.email", "test@example.invalid")
    _git(root, "config", "user.name", "Test User")
    config_target = root / "configs/git_reconciliation_v1.json"
    config_target.parent.mkdir(parents=True)
    shutil.copyfile(PROJECT_CONFIG, config_target)
    _write(root, ".gitignore", "/.worktrees/\n/tmp/\n")
    _write(root, "base.txt", "base\n")
    _git(root, "add", ".gitignore", "base.txt", "configs")
    _git(root, "commit", "-q", "-m", "initial")
    _git(tmp_path, "init", "-q", "--bare", str(remote))
    _git(root, "remote", "add", "origin", str(remote))
    _git(root, "push", "-q", "-u", "origin", "master")
    return root, remote


def _branch(report: reconciler.RepositoryInspection, name: str) -> reconciler.BranchInspection:
    return next(item for item in report.branches if item.branch == name)


def test_clean_synchronized_repository_is_healthy(tmp_path: Path) -> None:
    root, _ = _repository(tmp_path)

    report = reconciler.inspect_repository(root, agent="core", fetch=False)

    assert report.schema_version == reconciler.REPORT_SCHEMA_VERSION
    assert report.target_head == report.canonical_local_head
    assert report.canonical_branch_only_commit_count == 0
    assert report.canonical_target_only_commit_count == 0
    assert report.exit_code == 0
    assert report.diagnostics == ()


def test_unlanded_owned_branch_reports_facts_without_action_inference(
    tmp_path: Path,
) -> None:
    root, _ = _repository(tmp_path)
    _git(root, "switch", "-q", "-c", "core/example")
    head = _commit(root, "feature", "feature.txt", "feature\n")
    _git(root, "switch", "-q", "master")

    report = reconciler.inspect_repository(root, agent="core", fetch=False)
    branch = _branch(report, "core/example")

    assert branch.inspected_head == head
    assert branch.owner == "core"
    assert branch.owner_confidence == "exact"
    assert branch.branch_only_commit_count == 1
    assert branch.target_only_commit_count == 0
    assert branch.integration_evidence == "not_landed"
    assert branch.publication_state == "local_only_unpublished"
    assert _diagnostic_tuple(report) == (("owned_branch_not_landed", "core/example"),)
    assert report.exit_code == 2


def test_core_inbox_surfaces_published_non_core_branch_without_inferring_merge(
    tmp_path: Path,
) -> None:
    root, _ = _repository(tmp_path)
    _git(root, "switch", "-q", "-c", "compliance/core-request")
    commit = _commit(root, "compliance request", "compliance-request.md", "request\n")
    _git(root, "push", "-q", "-u", "origin", "compliance/core-request")
    _git(root, "switch", "-q", "master")

    report = reconciler.inspect_repository(root, agent="core", fetch=False)
    config = reconciler.load_reconciliation_config(root)
    inbox = reconciler.build_core_integration_inbox(report, config)

    assert ("core_integration_inbox_pending", "compliance/core-request") in (
        _diagnostic_tuple(report)
    )
    assert report.exit_code == 2
    assert inbox.schema_version == reconciler.INBOX_SCHEMA_VERSION
    assert inbox.exit_code == 2
    assert len(inbox.items) == 1
    item = inbox.items[0]
    assert item.branch == "compliance/core-request"
    assert item.remote_branch == "origin/compliance/core-request"
    assert item.branch_head == commit
    assert item.branch_only_commits == (commit,)
    assert item.disposition_posture == "owner_or_core_disposition_required"


def test_core_inbox_excludes_unpublished_unknown_and_landed_owner_branches(
    tmp_path: Path,
) -> None:
    root, _ = _repository(tmp_path)
    _git(root, "switch", "-q", "-c", "domain/unpublished")
    _commit(root, "unpublished", "domain.txt", "domain\n")
    _git(root, "switch", "-q", "master")
    _git(root, "branch", "docs/unknown")
    _git(root, "branch", "audit/already-landed")

    report = reconciler.inspect_repository(root, agent="core", fetch=False)
    config = reconciler.load_reconciliation_config(root)
    inbox = reconciler.build_core_integration_inbox(report, config)

    assert inbox.items == ()
    assert ("branch_owner_review_required", "docs/unknown") in (
        _diagnostic_tuple(report)
    )
    assert not any(
        code == "core_integration_inbox_pending"
        for code, _ in _diagnostic_tuple(report)
    )


def test_core_inbox_includes_remote_only_owner_branch(tmp_path: Path) -> None:
    root, remote = _repository(tmp_path)
    updater = tmp_path / "updater"
    _git(tmp_path, "clone", "-q", str(remote), str(updater))
    _git(updater, "config", "user.email", "test@example.invalid")
    _git(updater, "config", "user.name", "Test User")
    _git(updater, "switch", "-q", "-c", "governance/core-request")
    commit = _commit(updater, "governance request", "request.md", "request\n")
    _git(updater, "push", "-q", "-u", "origin", "governance/core-request")
    _git(root, "fetch", "-q", "origin")

    report = reconciler.inspect_repository(root, agent="core", fetch=False)
    config = reconciler.load_reconciliation_config(root)
    inbox = reconciler.build_core_integration_inbox(report, config)

    assert len(inbox.items) == 1
    assert inbox.items[0].branch == "governance/core-request"
    assert inbox.items[0].branch_head == commit
    assert inbox.items[0].publication_state == "remote_only"


def test_core_inbox_uses_remote_tip_when_published_branch_is_ahead(
    tmp_path: Path,
) -> None:
    root, remote = _repository(tmp_path)
    _git(root, "switch", "-q", "-c", "compliance/remote-ahead")
    first = _commit(root, "first request", "request-1.md", "first\n")
    _git(root, "push", "-q", "-u", "origin", "compliance/remote-ahead")
    _git(root, "switch", "-q", "master")
    updater = tmp_path / "updater"
    _git(tmp_path, "clone", "-q", str(remote), str(updater))
    _git(updater, "config", "user.email", "test@example.invalid")
    _git(updater, "config", "user.name", "Test User")
    _git(updater, "switch", "-q", "compliance/remote-ahead")
    second = _commit(updater, "second request", "request-2.md", "second\n")
    _git(updater, "push", "-q", "origin", "compliance/remote-ahead")
    _git(root, "fetch", "-q", "origin")

    report = reconciler.inspect_repository(root, agent="core", fetch=False)
    config = reconciler.load_reconciliation_config(root)
    item = reconciler.build_core_integration_inbox(report, config).items[0]

    assert item.branch_head == second
    assert item.branch_only_commits == (first, second)
    assert item.publication_state == "remote_ahead"


def test_core_inbox_retains_active_worktree_evidence(tmp_path: Path) -> None:
    root, _ = _repository(tmp_path)
    path = root / ".worktrees" / "audit-core-request"
    _git(root, "worktree", "add", "-q", "-b", "audit/core-request", str(path))
    _commit(path, "audit request", "audit-request.md", "request\n")
    _git(path, "push", "-q", "-u", "origin", "audit/core-request")

    report = reconciler.inspect_repository(root, agent="core", fetch=False)
    config = reconciler.load_reconciliation_config(root)
    inbox = reconciler.build_core_integration_inbox(report, config)

    assert len(inbox.items) == 1
    assert inbox.items[0].worktree_paths == (str(path.resolve()),)


def test_core_inbox_preserves_inspection_failure_precedence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _ = _repository(tmp_path)
    _git(root, "switch", "-q", "-c", "documentation/core-request")
    _commit(root, "documentation request", "documentation-request.md", "request\n")
    _git(root, "push", "-q", "-u", "origin", "documentation/core-request")
    _git(root, "switch", "-q", "master")
    original = reconciler._git

    def fail_status(repo: Path, *args: str) -> reconciler._CommandResult:
        if args and args[0] == "status":
            return reconciler._CommandResult("", "denied", 1)
        return original(repo, *args)

    monkeypatch.setattr(reconciler, "_git", fail_status)
    report = reconciler.inspect_repository(root, agent="core", fetch=False)
    config = reconciler.load_reconciliation_config(root)
    inbox = reconciler.build_core_integration_inbox(report, config)

    assert inbox.items
    assert report.exit_code == 3
    assert inbox.exit_code == 3


def test_remote_only_and_missing_upstream_are_reported(tmp_path: Path) -> None:
    root, remote = _repository(tmp_path)
    updater = tmp_path / "updater"
    _git(tmp_path, "clone", "-q", str(remote), str(updater))
    _git(updater, "config", "user.email", "test@example.invalid")
    _git(updater, "config", "user.name", "Test User")
    _git(updater, "switch", "-q", "-c", "audit/remote-only")
    _commit(updater, "remote feature", "audit.txt", "audit\n")
    _git(updater, "push", "-q", "-u", "origin", "audit/remote-only")
    _git(root, "fetch", "-q", "origin")
    _git(root, "switch", "-q", "-c", "documentation/no-upstream")
    _git(root, "switch", "-q", "master")

    report = reconciler.inspect_repository(root, agent="audit", fetch=False)

    remote_branch = _branch(report, "audit/remote-only")
    local_branch = _branch(report, "documentation/no-upstream")
    assert remote_branch.publication_state == "remote_only"
    assert remote_branch.local_head == ""
    assert local_branch.upstream == ""
    assert local_branch.integration_evidence == "landed_exact_evidence"


def test_patch_equivalent_landing_includes_original_to_replacement_mapping(
    tmp_path: Path,
) -> None:
    root, _ = _repository(tmp_path)
    _git(root, "switch", "-q", "-c", "domain/example")
    original = _commit(root, "domain change", "domain.txt", "domain\n")
    _git(root, "push", "-q", "-u", "origin", "domain/example")
    _git(root, "switch", "-q", "master")
    _commit(root, "independent master change", "master.txt", "master\n")
    _git(root, "cherry-pick", original)
    replacement = _git(root, "rev-parse", "HEAD")
    assert replacement != original
    _git(root, "push", "-q", "origin", "master")

    report = reconciler.inspect_repository(root, agent="domain", fetch=False)
    branch = _branch(report, "domain/example")

    assert not branch.exact_reachable
    assert branch.patch_equivalent
    assert branch.integration_evidence == "landed_patch_equivalent_evidence"
    assert len(branch.patch_mappings) == 1
    assert branch.patch_mappings[0].source_commit == original
    assert branch.patch_mappings[0].target_commit == replacement

    evidence = reconciler.build_closeout_evidence(
        report, "domain/example", "landed"
    )
    assert evidence.terminal
    assert evidence.patch_mappings == branch.patch_mappings
    assert len(evidence.evidence_sha256) == 64

    core_report = reconciler.inspect_repository(root, agent="core", fetch=False)
    config = reconciler.load_reconciliation_config(root)
    assert reconciler.build_core_integration_inbox(core_report, config).items == ()


def test_merge_and_empty_commits_do_not_claim_patch_equivalence(tmp_path: Path) -> None:
    root, _ = _repository(tmp_path)
    _git(root, "switch", "-q", "-c", "core/merge-history")
    _git(root, "commit", "--allow-empty", "-q", "-m", "empty")
    _git(root, "switch", "-q", "-c", "core/side")
    _commit(root, "side", "side.txt", "side\n")
    _git(root, "switch", "-q", "core/merge-history")
    _commit(root, "main line", "line.txt", "line\n")
    _git(root, "merge", "--no-ff", "-q", "core/side", "-m", "merge")
    _git(root, "switch", "-q", "master")

    report = reconciler.inspect_repository(root, agent="core", fetch=False)
    branch = _branch(report, "core/merge-history")

    reasons = {item.reason for item in branch.unmapped_commits}
    assert "empty_commit" in reasons
    assert "merge_commit" in reasons
    assert not branch.patch_equivalent
    with pytest.raises(reconciler.ReconciliationError, match="landed requires"):
        reconciler.build_closeout_evidence(report, branch.branch, "landed")


def test_owner_configuration_covers_all_roles_and_keeps_shared_prefixes_ambiguous(
    tmp_path: Path,
) -> None:
    root, _ = _repository(tmp_path)
    names = (
        "core/current",
        "interface/current",
        "domain/current",
        "compliance/current",
        "governance/current",
        "audit/current",
        "documentation/current",
        "application/legacy",
        "runtime/legacy",
        "operations/legacy",
        "docs/ambiguous",
    )
    for name in names:
        _git(root, "branch", name)

    report = reconciler.inspect_repository(root, agent="core", fetch=False)
    owners = {
        name: (_branch(report, name).owner, _branch(report, name).owner_confidence)
        for name in names
    }

    assert owners["core/current"] == ("core", "exact")
    assert owners["interface/current"] == ("interface", "exact")
    assert owners["domain/current"] == ("domain", "exact")
    assert owners["compliance/current"] == ("compliance", "exact")
    assert owners["governance/current"] == ("governance", "exact")
    assert owners["audit/current"] == ("audit", "exact")
    assert owners["documentation/current"] == ("documentation", "exact")
    assert owners["application/legacy"] == ("core", "legacy")
    assert owners["runtime/legacy"] == ("core", "legacy")
    assert owners["operations/legacy"] == ("core", "legacy")
    assert owners["docs/ambiguous"] == ("unknown", "ambiguous")


def test_physical_worktree_enumeration_is_independent_of_git_ignore(
    tmp_path: Path,
) -> None:
    root, _ = _repository(tmp_path)
    orphan = root / ".worktrees" / "orphan"
    orphan.mkdir(parents=True)
    _write(orphan, "note.txt", "not a registered worktree\n")
    assert _git(root, "status", "--porcelain") == ""

    report = reconciler.inspect_repository(root, agent="core", fetch=False)

    assert report.physical_worktree_entries == (
        reconciler.PhysicalWorktreeEntry(
            path=str(orphan.resolve()),
            kind="unregistered_directory",
            registered=False,
        ),
    )
    assert ("unregistered_directory", str(orphan.resolve())) in _diagnostic_tuple(
        report
    )
    assert report.exit_code == 2


def test_standalone_clone_and_detached_primary_are_reported(tmp_path: Path) -> None:
    root, remote = _repository(tmp_path)
    standalone = root / ".worktrees" / "standalone"
    standalone.parent.mkdir(parents=True)
    _git(root, "clone", "-q", str(remote), str(standalone))
    _git(root, "switch", "-q", "--detach")

    report = reconciler.inspect_repository(root, agent="core", fetch=False)

    assert any(
        item.path == str(standalone.resolve()) and item.kind == "standalone_clone"
        for item in report.physical_worktree_entries
    )
    assert ("primary_worktree_not_master", "") in _diagnostic_tuple(report)
    assert ("standalone_clone", str(standalone.resolve())) in _diagnostic_tuple(
        report
    )


def test_diverged_local_and_remote_branch_publication_is_reported(
    tmp_path: Path,
) -> None:
    root, remote = _repository(tmp_path)
    _git(root, "switch", "-q", "-c", "core/diverged")
    _commit(root, "shared", "shared.txt", "shared\n")
    _git(root, "push", "-q", "-u", "origin", "core/diverged")
    updater = tmp_path / "updater"
    _git(tmp_path, "clone", "-q", str(remote), str(updater))
    _git(updater, "config", "user.email", "test@example.invalid")
    _git(updater, "config", "user.name", "Test User")
    _git(updater, "switch", "-q", "core/diverged")
    _commit(updater, "remote side", "remote-side.txt", "remote\n")
    _git(updater, "push", "-q", "origin", "core/diverged")
    _commit(root, "local side", "local-side.txt", "local\n")
    _git(root, "fetch", "-q", "origin")
    _git(root, "switch", "-q", "master")

    report = reconciler.inspect_repository(root, agent="core", fetch=False)

    branch = _branch(report, "core/diverged")
    assert branch.publication_state == "publication_diverged"
    assert not branch.published_contains_local_head
    assert branch.integration_evidence == "not_landed"


def test_registered_worktree_is_correlated_with_branch_and_physical_entry(
    tmp_path: Path,
) -> None:
    root, _ = _repository(tmp_path)
    path = root / ".worktrees" / "audit-example"
    _git(root, "worktree", "add", "-q", "-b", "audit/example", str(path))

    report = reconciler.inspect_repository(root, agent="audit", fetch=False)

    worktree = next(item for item in report.worktrees if item.path == str(path.resolve()))
    physical = next(
        item for item in report.physical_worktree_entries if item.path == str(path.resolve())
    )
    assert worktree.location_state == "configured_root"
    assert worktree.clean is True
    assert physical.kind == "registered_worktree"
    assert _branch(report, "audit/example").worktree_paths == (str(path.resolve()),)


def test_status_failure_is_never_classified_as_clean(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _ = _repository(tmp_path)
    original = reconciler._git

    def fail_status(repo: Path, *args: str) -> reconciler._CommandResult:
        if args and args[0] == "status":
            return reconciler._CommandResult("", "denied", 1)
        return original(repo, *args)

    monkeypatch.setattr(reconciler, "_git", fail_status)

    report = reconciler.inspect_repository(root, agent="core", fetch=False)

    primary = next(item for item in report.worktrees if item.is_primary)
    assert primary.status == "inspection_failed"
    assert primary.clean is None
    assert report.exit_code == 3


def test_active_git_operation_and_non_master_primary_are_blockers(tmp_path: Path) -> None:
    root, _ = _repository(tmp_path)
    (root / ".git" / "BISECT_LOG").write_text("fixture\n", encoding="utf-8")
    _git(root, "switch", "-q", "-c", "core/active")

    report = reconciler.inspect_repository(root, agent="core", fetch=False)

    diagnostics = _diagnostic_tuple(report)
    assert ("primary_git_operation_active", "bisect") in diagnostics
    assert ("primary_worktree_not_master", "core/active") in diagnostics
    assert report.exit_code == 2


def test_awaiting_integrator_requires_published_commits_and_exact_handoff_fields(
    tmp_path: Path,
) -> None:
    root, _ = _repository(tmp_path)
    _git(root, "switch", "-q", "-c", "interface/example")
    _commit(root, "interface change", "interface.txt", "interface\n")
    _git(root, "switch", "-q", "master")
    report = reconciler.inspect_repository(root, agent="interface", fetch=False)

    with pytest.raises(reconciler.ReconciliationError, match="requires"):
        reconciler.build_closeout_evidence(
            report, "interface/example", "awaiting_named_integrator"
        )

    _git(root, "push", "-q", "-u", "origin", "interface/example")
    report = reconciler.inspect_repository(root, agent="interface", fetch=False)
    evidence = reconciler.build_closeout_evidence(
        report,
        "interface/example",
        "awaiting_named_integrator",
        named_integrator="core",
        remote_branch="origin/interface/example",
        remaining_action="Integrate the accepted commit.",
        evidence_ref="a2a:interface:example",
    )

    assert not evidence.terminal
    assert evidence.branch_only_commits
    assert evidence.named_integrator == "core"


def test_superseded_requires_authorization_reference_and_description(
    tmp_path: Path,
) -> None:
    root, _ = _repository(tmp_path)
    _git(root, "branch", "compliance/obsolete")
    report = reconciler.inspect_repository(root, agent="compliance", fetch=False)

    with pytest.raises(reconciler.ReconciliationError, match="requires"):
        reconciler.build_closeout_evidence(
            report, "compliance/obsolete", "superseded"
        )
    evidence = reconciler.build_closeout_evidence(
        report,
        "compliance/obsolete",
        "superseded",
        evidence_ref="compliance-owner-disposition",
        supersession="Replaced by compliance/current.",
    )
    assert evidence.terminal
    assert evidence.disposition == "superseded"


def test_closeout_rejects_another_owner_and_dirty_branch_worktree(
    tmp_path: Path,
) -> None:
    root, _ = _repository(tmp_path)
    path = root / ".worktrees" / "domain-example"
    _git(root, "worktree", "add", "-q", "-b", "domain/example", str(path))

    wrong_owner_report = reconciler.inspect_repository(
        root,
        agent="core",
        fetch=False,
    )
    with pytest.raises(reconciler.ReconciliationError, match="belongs to domain"):
        reconciler.build_closeout_evidence(
            wrong_owner_report,
            "domain/example",
            "landed",
        )

    _write(path, "untracked.txt", "uncommitted\n")
    owner_report = reconciler.inspect_repository(
        root,
        agent="domain",
        fetch=False,
    )
    with pytest.raises(reconciler.ReconciliationError, match="must be clean"):
        reconciler.build_closeout_evidence(
            owner_report,
            "domain/example",
            "landed",
        )


def test_sync_main_fast_forwards_clean_behind_only_primary(tmp_path: Path) -> None:
    root, remote = _repository(tmp_path)
    updater = tmp_path / "updater"
    _git(tmp_path, "clone", "-q", str(remote), str(updater))
    _git(updater, "config", "user.email", "test@example.invalid")
    _git(updater, "config", "user.name", "Test User")
    target = _commit(updater, "remote advance", "remote.txt", "remote\n")
    _git(updater, "push", "-q", "origin", "master")
    before = _git(root, "rev-parse", "HEAD")

    result = reconciler.sync_primary_master(root, agent="core")

    assert result.action == "fast_forwarded"
    assert result.before_head == before
    assert result.target_head == target
    assert result.after_head == target
    assert _git(root, "status", "--porcelain") == ""


@pytest.mark.parametrize("agent", ["interface", "domain", "compliance", "audit"])
def test_sync_main_rejects_non_core_agents(tmp_path: Path, agent: str) -> None:
    root, _ = _repository(tmp_path)

    with pytest.raises(reconciler.SafetyError, match="only Core"):
        reconciler.sync_primary_master(root, agent=agent)


def test_sync_main_rejects_dirty_primary_local_only_and_non_master_states(
    tmp_path: Path,
) -> None:
    root, _ = _repository(tmp_path)
    _write(root, "dirty.txt", "dirty\n")
    with pytest.raises(reconciler.SafetyError, match="not clean"):
        reconciler.sync_primary_master(root, agent="core")
    (root / "dirty.txt").unlink()

    _commit(root, "local only", "local.txt", "local\n")
    with pytest.raises(reconciler.SafetyError, match="absent from origin/master"):
        reconciler.sync_primary_master(root, agent="core")

    _git(root, "reset", "--hard", "-q", "origin/master")
    _git(root, "switch", "-q", "-c", "core/not-master")
    with pytest.raises(reconciler.SafetyError, match="not checked out on master"):
        reconciler.sync_primary_master(root, agent="core")


def test_sync_main_rejects_active_git_operation(tmp_path: Path) -> None:
    root, _ = _repository(tmp_path)
    (root / ".git" / "BISECT_LOG").write_text("fixture\n", encoding="utf-8")

    with pytest.raises(reconciler.SafetyError, match="active Git operation"):
        reconciler.sync_primary_master(root, agent="core")


def test_cli_inspection_is_deterministic_and_does_not_write_repository_files(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root, _ = _repository(tmp_path)
    before = _git(root, "status", "--porcelain=v1", "--untracked-files=all")

    first_exit = reconciler.main(
        [
            "inspect",
            "--agent",
            "core",
            "--repo",
            str(root),
            "--no-fetch",
            "--format",
            "json",
        ]
    )
    first = capsys.readouterr().out
    second_exit = reconciler.main(
        [
            "inspect",
            "--agent",
            "core",
            "--repo",
            str(root),
            "--no-fetch",
            "--format",
            "json",
        ]
    )
    second = capsys.readouterr().out

    assert first_exit == second_exit == 0
    assert first == second
    assert json.loads(first)["schema_version"] == reconciler.REPORT_SCHEMA_VERSION
    assert _git(root, "status", "--porcelain=v1", "--untracked-files=all") == before


def test_cli_core_inbox_is_deterministic_versioned_and_nonterminal(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root, _ = _repository(tmp_path)
    _git(root, "switch", "-q", "-c", "interface/core-request")
    _commit(root, "interface request", "interface-request.md", "request\n")
    _git(root, "push", "-q", "-u", "origin", "interface/core-request")
    _git(root, "switch", "-q", "master")
    argv = [
        "inbox",
        "--agent",
        "core",
        "--repo",
        str(root),
        "--no-fetch",
        "--format",
        "json",
    ]

    first_exit = reconciler.main(argv)
    first = capsys.readouterr().out
    second_exit = reconciler.main(argv)
    second = capsys.readouterr().out

    assert first_exit == second_exit == 2
    assert first == second
    payload = json.loads(first)
    assert payload["schema_version"] == reconciler.INBOX_SCHEMA_VERSION
    assert payload["items"][0]["branch"] == "interface/core-request"


def test_cli_inbox_rejects_non_core_agent(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root, _ = _repository(tmp_path)

    exit_code = reconciler.main(
        [
            "inbox",
            "--agent",
            "compliance",
            "--repo",
            str(root),
            "--no-fetch",
        ]
    )

    assert exit_code == 3
    assert "available only to Core" in capsys.readouterr().err


def test_output_path_must_remain_under_repository_tmp(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root, _ = _repository(tmp_path)

    exit_code = reconciler.main(
        [
            "inspect",
            "--agent",
            "core",
            "--repo",
            str(root),
            "--no-fetch",
            "--output",
            "report.json",
        ]
    )

    assert exit_code == 3
    assert "must be placed under repository tmp" in capsys.readouterr().err
    assert not (root / "report.json").exists()


def _diagnostic_tuple(
    report: reconciler.RepositoryInspection,
) -> tuple[tuple[str, str], ...]:
    return tuple((item.code, item.subject) for item in report.diagnostics)
