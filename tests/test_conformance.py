from __future__ import annotations

import json
from pathlib import Path

from governance_bootstrap.conformance import check_repository, validate_documentation_system


ROOT = Path(__file__).resolve().parents[1]


def test_complete_repository_conforms_to_six_plane_architecture() -> None:
    assert check_repository(ROOT) == []


def test_research_is_the_first_cold_start_evidence_lane() -> None:
    policy = json.loads((ROOT / "configs/conformance_v1.json").read_text(encoding="utf-8"))
    owners = json.loads((ROOT / "configs/owners_v1.json").read_text(encoding="utf-8"))["owners"]
    assert (ROOT / policy["research_first"]["research_dir"] / "records").is_dir()
    assert list((ROOT / "research/records").glob("*.md"))
    assert [name for name, item in owners.items() if item["active"]] == ["core"]
    assert policy["research_first"]["cold_start_sequence"][:3] == ["research_intake", "research_organization", "core_canonicalization"]


def test_orchestration_has_exact_model_bindings_and_separate_sol_finalization() -> None:
    orchestration = json.loads((ROOT / "configs/owner_scoped_orchestration_v1.json").read_text(encoding="utf-8"))
    bindings = orchestration["model_binding"]
    assert bindings["owner_orchestrator"] == {"model": "gpt-5.6-sol", "reasoning_effort": "xhigh"}
    assert bindings["implementer"] == {"model": "gpt-5.6-terra", "reasoning_effort": "high"}
    assert bindings["runner"] == {"model": "gpt-5.6-luna", "reasoning_effort": "max"}
    assert orchestration["subordinate_task_lifecycle"]["archive_owner"] == "owner_orchestrator"
    assert orchestration["subordinate_task_lifecycle"]["reuse_runner_thread_per_cycle"] is True


def test_owner_dependency_profiles_keep_examples_inactive_and_non_authorizing() -> None:
    owners = json.loads((ROOT / "configs/owners_v1.json").read_text(encoding="utf-8"))["owners"]
    for name in ("future-owner-template", "example-feature-owner"):
        profile = json.loads((ROOT / owners[name]["profile"]).read_text(encoding="utf-8"))
        assert owners[name]["active"] is False
        assert profile["lifecycle_state"] != "active"
        assert profile["no_ownership_grant"] is True
        assert profile["branch_prefix"] and profile["worktree_prefix"]


def test_no_project_specific_markers_or_absolute_paths() -> None:
    policy = json.loads((ROOT / "configs/conformance_v1.json").read_text(encoding="utf-8"))
    assert not [item for item in check_repository(ROOT) if item.startswith("neutrality:")]
    assert "C:" not in (ROOT / "README.md").read_text(encoding="utf-8")
    assert policy["forbidden_project_markers"]


def test_documentation_system_preserves_operational_equivalence() -> None:
    manifest = json.loads(
        (ROOT / "configs/documentation_system_v1.json").read_text(encoding="utf-8")
    )
    assert validate_documentation_system(ROOT) == []
    classifications = {item["classification"] for item in manifest["surfaces"]}
    assert classifications == {"operational_equivalent", "generic_adaptation"}
    assert {
        "AGENTS.md",
        "docs/GIT_RECONCILIATION.md",
        "Project_Obsidian_Vault/30_Core/Core Bootstrap.md",
        "Project_Obsidian_Vault/30_Core/Continuity/Core Continuity MOC.md",
    } <= {item["path"] for item in manifest["surfaces"]}


def test_core_bootstrap_has_complete_rehydration_and_closeout_contract() -> None:
    bootstrap = (ROOT / "Project_Obsidian_Vault/30_Core/Core Bootstrap.md").read_text(
        encoding="utf-8"
    )
    for phrase in (
        "Required starting order:",
        "Authority order:",
        "For discovery or next-step work:",
        "For authorized implementation:",
        "Before completing substantial Core work:",
        "Your first response is a concise rehydration report",
    ):
        assert phrase in bootstrap


def test_git_guide_covers_reconciliation_delivery_and_recovery() -> None:
    guide = (ROOT / "docs/GIT_RECONCILIATION.md").read_text(encoding="utf-8")
    for phrase in (
        "awaiting_named_integrator",
        "git merge --ff-only",
        "inspection_failed",
        "stable patch-ID",
        "git worktree remove",
    ):
        assert phrase in guide
