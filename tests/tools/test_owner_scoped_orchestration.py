from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TOOLS = PROJECT_ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import owner_scoped_orchestration as orchestration  # noqa: E402


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "configs").mkdir(parents=True)
    shutil.copy2(
        PROJECT_ROOT / "configs/owner_scoped_orchestration_v1.json",
        root / "configs/owner_scoped_orchestration_v1.json",
    )
    for source in ("configs/owners_v1.json", "configs/path_ownership_v1.json", "configs/runner_channel_workaround_v1.json"):
        shutil.copy2(PROJECT_ROOT / source, root / source)
    for source in (
        "roles/shared/OWNER_ORCHESTRATOR_PROMPT.md",
        "roles/shared/IMPLEMENTER_PROMPT.md",
        "roles/shared/VERIFICATION_RUNNER_PROMPT.md",
        "roles/core/orchestration_profile.json",
        "future_owners/example-feature-owner/orchestration_profile.json",
        "future_owners/owner-template/orchestration_profile.json",
    ):
        target = root / source
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(PROJECT_ROOT / source, target)
    profile_path = root / "roles/core/orchestration_profile.json"
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    profile["continuity_receipts_root"] = "receipts"
    profile_path.write_text(json.dumps(profile), encoding="utf-8")
    for field in ("role_instruction_path", "bootstrap_prompt_path", "continuity_moc_path"):
        reference = root / profile[field]
        reference.parent.mkdir(parents=True, exist_ok=True)
        reference.write_text("reference\n", encoding="utf-8")
    return root


def _prospective_profile(root: Path, *, malformed: bool = False, mismatched: bool = False) -> Path:
    """Write a example feature adoption profile using the local reference fixtures."""

    source = root / "roles/core/orchestration_profile.json"
    profile = json.loads(source.read_text(encoding="utf-8"))
    profile["owner"] = "wrong" if mismatched else "example_feature"
    profile["branch_prefix"] = "wrong/" if mismatched else "feature-example/"
    target = root / "future_owners/example-feature-owner/orchestration_profile.json"
    target.write_text("{" if malformed else json.dumps(profile), encoding="utf-8")
    return target


def _packet(root: Path, *, task_id: str = "task-1", branch: str = "core/task-1", description: str = "bounded source change", worktree: str = ".worktrees/task-1", allowed: list[str] | None = None, prohibited: list[str] | None = None, requested_tier: str | None = None, subordinate_task_ids: dict[str, object] | None = None, runner_checks: list[str] | None = None) -> dict[str, object]:
    allowed_paths = allowed if allowed is not None else ["tools/"]
    tiers = ("orchestrator_only", "orchestrator_plus_implementer", "full_team")
    selected = orchestration.classify_task(description, allowed_paths)["tier"]
    if requested_tier:
        selected = max((selected, requested_tier), key=tiers.index)
    execution_lane = selected != "orchestrator_only"
    selected_runner_checks = runner_checks if runner_checks is not None else ([orchestration.LUNA_FULL_COMMAND] if selected == "full_team" else [])
    if subordinate_task_ids is None:
        subordinate_task_ids = {}
        if selected != "orchestrator_only":
            subordinate_task_ids["implementer"] = {"primary": f"host-primary-{task_id}", "bounded_correction": f"host-correction-{task_id}"}
        if selected == "full_team":
            subordinate_task_ids["runner"] = f"host-runner-{task_id}"
    return orchestration.make_packet(
        owner="core", task_id=task_id, approval_ref="user:approved", baseline="a" * 40,
        branch=branch, worktree=worktree, allowed_paths=allowed_paths,
        prohibited_paths=prohibited if prohibited is not None else ["governance_bootstrap/private/"], evidence_refs=["test:evidence"],
        focused_checks=["focused"] if execution_lane else [], broad_checks=["broad"] if execution_lane else [], runner_checks=selected_runner_checks, description=description, requested_tier=requested_tier,
        subordinate_task_ids=subordinate_task_ids, repo=root,
    )


def _checks(command: str) -> list[dict[str, str]]:
    return [{"command": command, "outcome": "passed"}]


def _turn_context(packet: dict[str, object]) -> dict[str, object]:
    return {"source": "host_recorded", "channel": "saved_project_reusable_chat", "project_context": "matching_saved_project", "thread_id": packet["subordinate_task_ids"]["runner"], "model": {"model": "gpt-5.6-luna", "reasoning_effort": "xhigh"}}


def _bind_runner(packet: dict[str, object], implementer: dict[str, object], candidate: str, root: Path) -> dict[str, object]:
    return orchestration.bind_runner(packet, implementer, candidate, root, turn_context=_turn_context(packet))


def _implementer(packet: dict[str, object], candidate: str = "b" * 40) -> dict[str, object]:
    commands = [*packet["focused_checks"], orchestration.TERRA_AFFECTED_COMMAND, *packet["broad_checks"]]
    return {"schema_version": orchestration.IMPLEMENTER_RECEIPT_SCHEMA, "owner": packet["owner"], "task_id": packet["task_id"], "packet_hash": packet["canonical_hash"], "implementer_type": "primary", "subordinate_task_id": packet["subordinate_task_ids"]["implementer"]["primary"], "model": {"model": "gpt-5.6-terra", "reasoning_effort": "high"}, "base_candidate_commit": packet["baseline"], "candidate_commit": candidate, "changed_paths": ["tools/example.py"], "actions": ["write", "commit", "test"], "checks": [{"command": command, "outcome": "passed"} for command in commands], "residual_issues": [], "outcome": "passed"}


def _bounded_correction(packet: dict[str, object], primary: dict[str, object], candidate: str = "c" * 40) -> dict[str, object]:
    receipt = _implementer(packet, candidate)
    receipt["implementer_type"] = "bounded_correction"
    receipt["subordinate_task_id"] = packet["subordinate_task_ids"]["implementer"]["bounded_correction"]
    receipt["model"] = {"model": "gpt-5.6-terra", "reasoning_effort": "low"}
    receipt["base_candidate_commit"] = primary["candidate_commit"]
    return receipt


def _runner(packet: dict[str, object], binding: dict[str, object], candidate: str = "b" * 40) -> dict[str, object]:
    return {"schema_version": orchestration.RUNNER_RECEIPT_SCHEMA, "owner": packet["owner"], "task_id": packet["task_id"], "packet_hash": packet["canonical_hash"], "runner_binding_hash": binding["canonical_hash"], "model": {"model": "gpt-5.6-luna", "reasoning_effort": "xhigh"}, "candidate_commit": candidate, "actions": ["inspect", "test"], "checks": [{"command": command, "outcome": "passed"} for command in packet["runner_checks"]], "environment_preflight": {"candidate_commit_verified": True, "model_binding_verified": True, "initial_worktree_clean": True}, "git_status": {"initial": "clean", "final": "clean"}, "reconciler_evidence": {"target": "origin/master", "candidate_commit": candidate, "state": "pre_publication_unlanded"}, "diagnostics": [], "residual_issues": [], "outcome": "passed"}


def _sol(packet: dict[str, object]) -> dict[str, object]:
    return {"schema_version": orchestration.SOL_DISPOSITION_SCHEMA, "owner": packet["owner"], "task_id": packet["task_id"], "packet_hash": packet["canonical_hash"], "model": {"model": "gpt-5.6-sol", "reasoning_effort": "xhigh"}, "disposition": "analysis complete", "residual_issues": [], "outcome": "passed"}


def _archive_acknowledgment(manifest: dict[str, object]) -> dict[str, object]:
    payload = {
        "schema_version": orchestration.ARCHIVE_ACKNOWLEDGMENT_SCHEMA,
        "owner": manifest["owner"],
        "task_id": manifest["task_id"],
        "packet_hash": manifest["packet_hash"],
        "archive_manifest_hash": manifest["canonical_hash"],
        "acknowledged_by": "owner_orchestrator",
        "correction_pending": False,
        "lane_dispositions": [
            {"lane": lane["lane"], "implementer_type": lane["implementer_type"], "subordinate_task_id": lane["subordinate_task_id"], "disposition": "unused_no_correction_requested" if lane["implementer_type"] == "bounded_correction" and lane["receipt_hash"] is None else "archived", "supersession_ref": None}
            for lane in manifest["lanes"]
        ],
    }
    return {**payload, "canonical_hash": orchestration.sha256_canonical(payload)}


def _delivery_evidence(packet: dict[str, object], implementer: dict[str, object], binding: dict[str, object], runner: dict[str, object], record: dict[str, object]) -> dict[str, object]:
    payload = {
        "schema_version": orchestration.CLOSEOUT_DELIVERY_EVIDENCE_SCHEMA,
        "owner": packet["owner"],
        "task_id": packet["task_id"],
        "packet_hash": packet["canonical_hash"],
        "branch": packet["branch"],
        "candidate_commit": implementer["candidate_commit"],
        "receipt_record_hash": record["canonical_hash"],
        "captured_receipt_hashes": {
            "primary": orchestration._payload_hash(implementer),
            "bounded_correction": None,
            "runner_binding": binding["canonical_hash"],
            "runner": orchestration._payload_hash(runner),
        },
        "terminal_reconciliation": {"target": "origin/master", "disposition": "landed", "evidence_ref": "reconciler:landed"},
        "primary_branch_sync": {"verified": True, "evidence_ref": "reconciler:sync-main"},
        "worktree_removal": {"worktree": packet["worktree"], "removed": True, "evidence_ref": "git:worktree-list"},
        "acknowledged_by": "owner_orchestrator",
    }
    return {**payload, "canonical_hash": orchestration.sha256_canonical(payload)}


def _legacy_v3_artifacts(root: Path, task_id: str = "legacy-v3") -> tuple[dict[str, object], dict[str, object], dict[str, object], dict[str, object], dict[str, object]]:
    packet = _packet(root, task_id=task_id, description="runtime change")
    packet["schema_version"] = "owner_scoped_task_packet_v3"
    packet["lane_models"] = {"owner_orchestrator": {"model": "gpt-5.6-sol", "reasoning_effort": "xhigh"}, "implementer": {"model": "gpt-5.6-terra", "reasoning_effort": "high"}, "runner": {"model": "gpt-5.6-luna", "reasoning_effort": "xhigh"}}
    packet["responsibilities"] = {"owner_orchestrator": "classify and publish", "implementer": "bounded candidate only", "runner": "inspect and test only"}
    packet["subordinate_task_ids"] = {"implementer": f"legacy-terra-{task_id}", "runner": f"legacy-luna-{task_id}"}
    packet["canonical_hash"] = orchestration.sha256_canonical({key: value for key, value in packet.items() if key != "canonical_hash"})
    commands = [*packet["focused_checks"], orchestration.TERRA_AFFECTED_COMMAND, *packet["broad_checks"]]
    implementer = {"schema_version": "owner_scoped_implementer_receipt_v2", "owner": packet["owner"], "task_id": packet["task_id"], "packet_hash": packet["canonical_hash"], "model": {"model": "gpt-5.6-terra", "reasoning_effort": "high"}, "candidate_commit": "b" * 40, "changed_paths": ["tools/example.py"], "actions": ["write", "commit", "test"], "checks": [{"command": command, "outcome": "passed"} for command in commands], "residual_issues": [], "outcome": "passed"}
    binding_payload = {"schema_version": "owner_scoped_runner_binding_v4", "owner": packet["owner"], "task_id": packet["task_id"], "packet_hash": packet["canonical_hash"], "implementer_receipt_hash": orchestration._payload_hash(implementer), "candidate_commit": implementer["candidate_commit"], "candidate_posture": "sol_declared_final", "runner_model": {"model": "gpt-5.6-luna", "reasoning_effort": "xhigh"}, "runner_task_id": packet["subordinate_task_ids"]["runner"], "turn_context": {"source": "host_recorded", "channel": "saved_project_reusable_chat", "project_context": "matching_saved_project", "thread_id": packet["subordinate_task_ids"]["runner"], "model": {"model": "gpt-5.6-luna", "reasoning_effort": "xhigh"}}}
    binding = {**binding_payload, "canonical_hash": orchestration.sha256_canonical(binding_payload)}
    runner = _runner(packet, binding)
    record_payload = {"schema_version": "owner_scoped_orchestration_record_v2", "owner": packet["owner"], "task_id": packet["task_id"], "packet_hash": packet["canonical_hash"], "tier": "full_team", "implementer_receipt_hash": orchestration._payload_hash(implementer), "runner_binding_hash": binding["canonical_hash"], "runner_receipt_hash": orchestration._payload_hash(runner), "sol_disposition_hash": "", "archive_manifest_hash": ""}
    lanes = [{"lane": "implementer", "subordinate_task_id": packet["subordinate_task_ids"]["implementer"], "receipt_hash": orchestration._payload_hash(implementer), "action": "archive", "status": "ready_after_owner_receipt_capture"}, {"lane": "runner", "subordinate_task_id": packet["subordinate_task_ids"]["runner"], "receipt_hash": orchestration._payload_hash(runner), "action": "archive", "status": "ready_after_owner_receipt_capture"}]
    manifest_payload = {"schema_version": "owner_scoped_subordinate_archive_manifest_v2", "owner": packet["owner"], "task_id": packet["task_id"], "packet_hash": packet["canonical_hash"], "authority": "owner_orchestrator", "transport": "host_task_management_surface", "runner_binding_hash": binding["canonical_hash"], "lanes": lanes}
    manifest = {**manifest_payload, "canonical_hash": orchestration.sha256_canonical(manifest_payload)}
    record_payload["archive_manifest_hash"] = manifest["canonical_hash"]
    record = {**record_payload, "canonical_hash": orchestration.sha256_canonical(record_payload)}
    acknowledgment_payload = {"schema_version": "owner_scoped_subordinate_archive_acknowledgment_v1", "owner": packet["owner"], "task_id": packet["task_id"], "packet_hash": packet["canonical_hash"], "archive_manifest_hash": manifest["canonical_hash"], "acknowledged_by": "owner_orchestrator", "correction_pending": False, "lane_dispositions": [{"lane": item["lane"], "subordinate_task_id": item["subordinate_task_id"], "disposition": "archived", "supersession_ref": ""} for item in lanes]}
    acknowledgment = {**acknowledgment_payload, "canonical_hash": orchestration.sha256_canonical(acknowledgment_payload)}
    delivery_payload = {"schema_version": "owner_scoped_closeout_delivery_evidence_v1", "owner": packet["owner"], "task_id": packet["task_id"], "packet_hash": packet["canonical_hash"], "branch": packet["branch"], "candidate_commit": implementer["candidate_commit"], "receipt_record_hash": record["canonical_hash"], "captured_receipt_hashes": {"implementer": orchestration._payload_hash(implementer), "runner_binding": binding["canonical_hash"], "runner": orchestration._payload_hash(runner)}, "terminal_reconciliation": {"target": "origin/master", "disposition": "landed", "evidence_ref": "test:landed"}, "primary_branch_sync": {"verified": True, "evidence_ref": "test:sync"}, "worktree_removal": {"worktree": packet["worktree"], "removed": True, "evidence_ref": "test:worktree"}, "acknowledged_by": "owner_orchestrator"}
    delivery = {**delivery_payload, "canonical_hash": orchestration.sha256_canonical(delivery_payload)}
    bundle = root / "receipts" / packet["task_id"] / packet["canonical_hash"]
    bundle.mkdir(parents=True)
    for name, value in {"packet.json": packet, "implementer_receipt.json": implementer, "runner_binding.json": binding, "runner_receipt.json": runner, "subordinate_archive_manifest.json": manifest, "record.json": record}.items():
        (bundle / name).write_bytes((orchestration.canonical_json(value) + "\n").encode("utf-8"))
    return packet, manifest, acknowledgment, record, delivery


def test_registry_and_exact_sol_prompt_composition(tmp_path: Path) -> None:
    root = _repo(tmp_path); registry = orchestration.load_registry(root); packet = _packet(root)
    assert registry["model_binding"]["owner_orchestrator"] == {"model": "gpt-5.6-sol", "reasoning_effort": "xhigh"}
    assert set(registry["owners"]) == {"core", "example_feature", "owner_template"}
    assert registry["owners"]["example_feature"]["status"] == "owner_adoption_required"
    assert registry["owners"]["owner_template"]["status"] == "owner_adoption_required"
    composition = orchestration.compose_prompt("core", packet, root)
    assert composition["shared_sol_base"] == "roles/shared/OWNER_ORCHESTRATOR_PROMPT.md"
    assert composition["shared_implementer_base"] == "roles/shared/IMPLEMENTER_PROMPT.md"
    assert composition["shared_runner_base"] == "roles/shared/VERIFICATION_RUNNER_PROMPT.md"
    assert composition["shared_prompt_templates"] == registry["prompt_templates"]
    assert (composition["owner"], composition["git_owner"], composition["branch_prefix"]) == ("core", "core", "core/")


def test_registry_fails_closed_when_a_shared_lane_prompt_is_missing(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / "roles/shared/IMPLEMENTER_PROMPT.md").unlink()
    with pytest.raises(orchestration.OrchestrationError, match="prompt template is missing for implementer"):
        orchestration.load_registry(root)


def test_packet_binds_description_models_and_active_profile(tmp_path: Path) -> None:
    root = _repo(tmp_path); packet = _packet(root, description="approved bounded work")
    assert packet["task_description"] == "approved bounded work"
    assert set(packet["lane_models"]) == {"owner_orchestrator", "implementer", "runner"}
    assert packet["owner_profile_ref"].endswith("orchestration_profile.json") and len(packet["owner_profile_hash"]) == 64
    tampered = dict(packet); tampered["lane_models"] = {}; tampered["canonical_hash"] = orchestration.sha256_canonical({key: value for key, value in tampered.items() if key != "canonical_hash"})
    with pytest.raises(orchestration.OrchestrationError, match="lane model"): orchestration.validate_packet(tampered, root)
    tampered = dict(packet); tampered["owner_profile_hash"] = "0" * 64; tampered["canonical_hash"] = orchestration.sha256_canonical({key: value for key, value in tampered.items() if key != "canonical_hash"})
    with pytest.raises(orchestration.OrchestrationError, match="profile identity"): orchestration.validate_packet(tampered, root)


def test_typed_implementer_binding_uses_low_candidate_only_when_accepted(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    packet = _packet(root, description="runtime change")
    primary = _implementer(packet)
    no_correction = _bind_runner(packet, primary, "b" * 40, root)
    assert no_correction["implementer_receipt_hashes"] == {"primary": orchestration._payload_hash(primary), "bounded_correction": None}
    correction = _bounded_correction(packet, primary)
    binding = orchestration.bind_runner(packet, primary, "c" * 40, root, turn_context=_turn_context(packet), bounded_correction_receipt=correction)
    assert binding["candidate_commit"] == correction["candidate_commit"]
    assert binding["implementer_receipt_hashes"]["bounded_correction"] == orchestration._payload_hash(correction)
    correction["base_candidate_commit"] = "d" * 40
    with pytest.raises(orchestration.OrchestrationError, match="base_candidate_commit"):
        orchestration.bind_runner(packet, primary, "c" * 40, root, turn_context=_turn_context(packet), bounded_correction_receipt=correction)


def test_typed_implementer_receipts_bind_low_final_candidate_with_exact_base(tmp_path: Path) -> None:
    root = _repo(tmp_path); packet = _packet(root, description="runtime change"); primary = _implementer(packet); low = _bounded_correction(packet, primary)
    assert low["subordinate_task_id"] == packet["subordinate_task_ids"]["implementer"]["bounded_correction"]
    assert low["base_candidate_commit"] == primary["candidate_commit"]
    with pytest.raises(orchestration.OrchestrationError, match="type mismatch"):
        bad = dict(low); bad["implementer_type"] = "primary"; orchestration.bind_runner(packet, primary, "c" * 40, root, turn_context=_turn_context(packet), bounded_correction_receipt=bad)


@pytest.mark.parametrize("field,value", [("implementer_type", "wrong"), ("subordinate_task_id", "wrong-task"), ("model", {"model": "wrong", "reasoning_effort": "high"})])
def test_typed_implementer_receipt_rejects_type_task_and_model_mismatch(tmp_path: Path, field: str, value: object) -> None:
    root = _repo(tmp_path); packet = _packet(root, description="runtime change"); primary = _implementer(packet); bad = dict(primary); bad[field] = value
    with pytest.raises(orchestration.OrchestrationError):
        orchestration.bind_runner(packet, bad, "b" * 40, root, turn_context=_turn_context(packet))


def test_typed_packet_rejects_missing_duplicate_and_swapped_task_ids(tmp_path: Path) -> None:
    root = _repo(tmp_path); packet = _packet(root, description="runtime change")
    for tasks in ({"implementer": {"primary": "a"}}, {"implementer": {"primary": "same", "bounded_correction": "same"}, "runner": "runner"}):
        bad = dict(packet); bad["subordinate_task_ids"] = tasks; bad["canonical_hash"] = orchestration.sha256_canonical({key: value for key, value in bad.items() if key != "canonical_hash"})
        with pytest.raises(orchestration.OrchestrationError): orchestration.validate_packet(bad, root)


@pytest.mark.parametrize("field,value", [("subordinate_task_id", "wrong-low-task"), ("model", {"model": "wrong", "reasoning_effort": "low"}), ("model", {"model": "gpt-5.6-terra", "reasoning_effort": "high"}), ("base_candidate_commit", "d" * 40)])
def test_low_receipt_rejects_task_model_effort_and_base_mismatch(tmp_path: Path, field: str, value: object) -> None:
    root = _repo(tmp_path); packet = _packet(root, description="runtime change"); primary = _implementer(packet); low = _bounded_correction(packet, primary); low[field] = value
    with pytest.raises(orchestration.OrchestrationError):
        orchestration.bind_runner(packet, primary, "c" * 40, root, turn_context=_turn_context(packet), bounded_correction_receipt=low)


def test_primary_receipt_rejects_wrong_base_and_swapped_packet_task_ids(tmp_path: Path) -> None:
    root = _repo(tmp_path); packet = _packet(root, description="runtime change"); primary = _implementer(packet); primary["base_candidate_commit"] = "d" * 40
    with pytest.raises(orchestration.OrchestrationError, match="base_candidate_commit"):
        orchestration.bind_runner(packet, primary, "b" * 40, root, turn_context=_turn_context(packet))
    packet = _packet(root, task_id="swapped", description="runtime change"); primary = _implementer(packet); swapped = dict(packet); ids = dict(packet["subordinate_task_ids"]); ids["implementer"] = {"primary": ids["implementer"]["bounded_correction"], "bounded_correction": ids["implementer"]["primary"]}; swapped["subordinate_task_ids"] = ids; swapped["canonical_hash"] = orchestration.sha256_canonical({key: value for key, value in swapped.items() if key != "canonical_hash"})
    with pytest.raises(orchestration.OrchestrationError, match="task ID"):
        orchestration.bind_runner(swapped, primary, "b" * 40, root, turn_context={**_turn_context(packet), "thread_id": swapped["subordinate_task_ids"]["runner"]})


def test_typed_closeout_distinguishes_unused_low_and_primary_supersession(tmp_path: Path) -> None:
    root = _repo(tmp_path); packet = _packet(root, description="runtime change"); primary = _implementer(packet); binding = _bind_runner(packet, primary, "b" * 40, root); runner = _runner(packet, binding)
    manifest = orchestration.build_subordinate_archive_manifest(packet, primary, binding, runner, root)
    acknowledgment = _archive_acknowledgment(manifest)
    assert acknowledgment["lane_dispositions"][1]["disposition"] == "unused_no_correction_requested"
    acknowledgment["lane_dispositions"][1].update({"disposition": "superseded_by_primary", "supersession_ref": orchestration._payload_hash(primary)})
    acknowledgment["canonical_hash"] = orchestration.sha256_canonical({key: value for key, value in acknowledgment.items() if key != "canonical_hash"})
    orchestration.validate_archive_acknowledgment(acknowledgment, manifest)


def test_accepted_cumulative_low_receipt_flows_through_full_closeout(tmp_path: Path) -> None:
    root = _repo(tmp_path); packet = _packet(root, task_id="low-closeout", description="runtime change"); primary = _implementer(packet); low = _bounded_correction(packet, primary)
    binding = orchestration.bind_runner(packet, primary, low["candidate_commit"], root, turn_context=_turn_context(packet), bounded_correction_receipt=low); runner = _runner(packet, binding, low["candidate_commit"])
    record = orchestration.record_bundle(packet, primary, binding, runner, repo=root, bounded_correction_receipt=low)
    manifest = json.loads((root / "receipts" / packet["task_id"] / packet["canonical_hash"] / "subordinate_archive_manifest.json").read_text(encoding="utf-8")); acknowledgment = _archive_acknowledgment(manifest)
    payload = {"schema_version": orchestration.CLOSEOUT_DELIVERY_EVIDENCE_SCHEMA, "owner": packet["owner"], "task_id": packet["task_id"], "packet_hash": packet["canonical_hash"], "branch": packet["branch"], "candidate_commit": low["candidate_commit"], "receipt_record_hash": record["canonical_hash"], "captured_receipt_hashes": {"primary": orchestration._payload_hash(primary), "bounded_correction": orchestration._payload_hash(low), "runner_binding": binding["canonical_hash"], "runner": orchestration._payload_hash(runner)}, "terminal_reconciliation": {"target": "origin/master", "disposition": "landed", "evidence_ref": "test:landed"}, "primary_branch_sync": {"verified": True, "evidence_ref": "test:sync"}, "worktree_removal": {"worktree": packet["worktree"], "removed": True, "evidence_ref": "test:worktree"}, "acknowledged_by": "owner_orchestrator"}; delivery = {**payload, "canonical_hash": orchestration.sha256_canonical(payload)}
    finalization = orchestration.finalize_closeout(packet, primary, binding, runner, manifest, acknowledgment, record, delivery, root, bounded_correction_receipt=low)
    assert binding["implementer_receipt_hashes"] == {"primary": orchestration._payload_hash(primary), "bounded_correction": orchestration._payload_hash(low)}
    assert finalization["captured_receipt_hashes"]["bounded_correction"] == orchestration._payload_hash(low)


def test_replacement_primary_finalization_marks_unused_low_superseded(tmp_path: Path) -> None:
    root = _repo(tmp_path); packet = _packet(root, task_id="primary-replacement", description="runtime change"); primary = _implementer(packet, "c" * 40); binding = _bind_runner(packet, primary, "c" * 40, root); runner = _runner(packet, binding, "c" * 40); record = orchestration.record_bundle(packet, primary, binding, runner, repo=root)
    manifest = json.loads((root / "receipts" / packet["task_id"] / packet["canonical_hash"] / "subordinate_archive_manifest.json").read_text(encoding="utf-8")); acknowledgment = _archive_acknowledgment(manifest); acknowledgment["lane_dispositions"][1].update({"disposition": "superseded_by_primary", "supersession_ref": orchestration._payload_hash(primary)}); acknowledgment["canonical_hash"] = orchestration.sha256_canonical({key: value for key, value in acknowledgment.items() if key != "canonical_hash"})
    delivery = _delivery_evidence(packet, primary, binding, runner, record); finalization = orchestration.finalize_closeout(packet, primary, binding, runner, manifest, acknowledgment, record, delivery, root)
    assert finalization["subordinate_task_dispositions"][1]["disposition"] == "superseded_by_primary"


def test_new_work_rejects_v3_packet_but_explicit_legacy_finalization_closes_recorded_bundle(tmp_path: Path) -> None:
    root = _repo(tmp_path); packet, manifest, acknowledgment, record, delivery = _legacy_v3_artifacts(root)
    with pytest.raises(orchestration.OrchestrationError, match="issue a v4 packet"):
        orchestration.validate_packet(packet, root)
    finalization = orchestration.finalize_legacy_v3_closeout(packet, manifest, acknowledgment, record, delivery, root)
    path = root / "receipts" / packet["task_id"] / "legacy_v3_finalizations" / finalization["canonical_hash"] / "legacy_closeout_finalization.json"
    assert path.is_file()
    with pytest.raises(orchestration.OrchestrationError, match="no-overwrite"):
        orchestration.finalize_legacy_v3_closeout(packet, manifest, acknowledgment, record, delivery, root)


def test_legacy_closeout_rejects_missing_and_mutated_recorded_bundle(tmp_path: Path) -> None:
    root = _repo(tmp_path); packet, manifest, acknowledgment, record, delivery = _legacy_v3_artifacts(root, "legacy-mutate")
    bundle = root / "receipts" / packet["task_id"] / packet["canonical_hash"]
    (bundle / "runner_receipt.json").unlink()
    with pytest.raises(orchestration.OrchestrationError, match="runner_receipt.json"):
        orchestration.finalize_legacy_v3_closeout(packet, manifest, acknowledgment, record, delivery, root)
    packet, manifest, acknowledgment, record, delivery = _legacy_v3_artifacts(root, "legacy-bytes")
    packet_path = root / "receipts" / "legacy-bytes" / packet["canonical_hash"] / "packet.json"
    packet_path.write_text("{}", encoding="utf-8")
    with pytest.raises(orchestration.OrchestrationError, match="canonical bundle bytes"):
        orchestration.finalize_legacy_v3_closeout(packet, manifest, acknowledgment, record, delivery, root)


@pytest.mark.parametrize("section,field,value", [("terminal_reconciliation", "disposition", "superseded"), ("primary_branch_sync", "verified", False), ("worktree_removal", "worktree", ".worktrees/wrong")])
def test_legacy_closeout_rejects_terminal_delivery_mutations(tmp_path: Path, section: str, field: str, value: object) -> None:
    root = _repo(tmp_path); packet, manifest, acknowledgment, record, delivery = _legacy_v3_artifacts(root, f"legacy-{field}")
    delivery[section][field] = value; delivery["canonical_hash"] = orchestration.sha256_canonical({key: item for key, item in delivery.items() if key != "canonical_hash"})
    with pytest.raises(orchestration.OrchestrationError):
        orchestration.finalize_legacy_v3_closeout(packet, manifest, acknowledgment, record, delivery, root)


def test_legacy_closeout_rejects_unsafe_acknowledgment_and_cross_hash(tmp_path: Path) -> None:
    root = _repo(tmp_path); packet, manifest, acknowledgment, record, delivery = _legacy_v3_artifacts(root, "legacy-ack")
    acknowledgment["correction_pending"] = True; acknowledgment["canonical_hash"] = orchestration.sha256_canonical({key: item for key, item in acknowledgment.items() if key != "canonical_hash"})
    with pytest.raises(orchestration.OrchestrationError, match="acknowledgment"):
        orchestration.finalize_legacy_v3_closeout(packet, manifest, acknowledgment, record, delivery, root)
    packet, manifest, acknowledgment, record, delivery = _legacy_v3_artifacts(root, "legacy-hash")
    record["runner_receipt_hash"] = "0" * 64; record["canonical_hash"] = orchestration.sha256_canonical({key: item for key, item in record.items() if key != "canonical_hash"})
    with pytest.raises(orchestration.OrchestrationError, match="differs|cross-hashes"):
        orchestration.finalize_legacy_v3_closeout(packet, manifest, acknowledgment, record, delivery, root)


def test_legacy_closeout_rejects_extra_binding_or_delivery_fields(tmp_path: Path) -> None:
    root = _repo(tmp_path); packet, manifest, acknowledgment, record, delivery = _legacy_v3_artifacts(root, "legacy-extra")
    bundle = root / "receipts" / packet["task_id"] / packet["canonical_hash"]; binding_path = bundle / "runner_binding.json"; binding = json.loads(binding_path.read_text(encoding="utf-8")); binding["extra"] = True; binding["canonical_hash"] = orchestration.sha256_canonical({key: item for key, item in binding.items() if key != "canonical_hash"}); binding_path.write_bytes((orchestration.canonical_json(binding) + "\n").encode("utf-8"))
    with pytest.raises(orchestration.OrchestrationError, match="runner binding"):
        orchestration.finalize_legacy_v3_closeout(packet, manifest, acknowledgment, record, delivery, root)
    packet, manifest, acknowledgment, record, delivery = _legacy_v3_artifacts(root, "legacy-delivery-extra")
    delivery["terminal_reconciliation"]["extra"] = True; delivery["canonical_hash"] = orchestration.sha256_canonical({key: item for key, item in delivery.items() if key != "canonical_hash"})
    with pytest.raises(orchestration.OrchestrationError):
        orchestration.finalize_legacy_v3_closeout(packet, manifest, acknowledgment, record, delivery, root)


def test_packet_shape_task_id_and_static_risk_cannot_be_self_hashed_away(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    assert _packet(root, task_id="a" * 128)["task_id"] == "a" * 128
    for task_id in ("../escape", "nested/task", ".hidden", "trailing-", "UPPER", "a" * 129):
        with pytest.raises(orchestration.OrchestrationError, match="task_id"):
            _packet(root, task_id=task_id)
    packet = _packet(root, description="runtime change")
    downgraded = dict(packet); downgraded["classification"] = {**packet["classification"], "tier": "orchestrator_only"}; downgraded["canonical_hash"] = orchestration.sha256_canonical({key: value for key, value in downgraded.items() if key != "canonical_hash"})
    with pytest.raises(orchestration.OrchestrationError, match="downgrades"):
        orchestration.validate_packet(downgraded, root)
    malicious = dict(packet); malicious["task_id"] = "../escape"; malicious["canonical_hash"] = orchestration.sha256_canonical({key: value for key, value in malicious.items() if key != "canonical_hash"})
    with pytest.raises(orchestration.OrchestrationError, match="task_id"):
        orchestration.record_bundle(malicious, _implementer(malicious), repo=root)
    assert not (root / "escape").exists()
    for mutate, message in ((lambda value: value.__setitem__("unexpected", "x"), "forbidden"), (lambda value: value.pop("evidence_refs"), "missing"), (lambda value: value.__setitem__("user_approval_ref", ""), "required")):
        invalid = dict(packet); mutate(invalid); invalid["canonical_hash"] = orchestration.sha256_canonical({key: value for key, value in invalid.items() if key != "canonical_hash"})
        with pytest.raises(orchestration.OrchestrationError, match=message): orchestration.validate_packet(invalid, root)
    for unsafe_description, message in (("token=private", "credentials"), ("C:/private/path", "filesystem path")):
        with pytest.raises(orchestration.OrchestrationError, match=message):
            _packet(root, description=unsafe_description)


def test_registry_allows_future_owner_profile_before_activation(tmp_path: Path) -> None:
    root = _repo(tmp_path); registry_path = root / "configs/owner_scoped_orchestration_v1.json"; registry = json.loads(registry_path.read_text(encoding="utf-8"))
    registry["owners"]["future"] = {"status": "owner_adoption_required", "git_owner": "future", "branch_prefix": "future/", "profile_path": "future_owners/future-owner/orchestration_profile.json"}
    registry_path.write_text(json.dumps(registry), encoding="utf-8")
    profile = json.loads((root / "roles/core/orchestration_profile.json").read_text(encoding="utf-8")); profile["owner"] = "future"; profile["branch_prefix"] = "future/"; profile["path_rules"] = ["future_owners/future-owner"]
    profile_path = root / "future_owners/future-owner/orchestration_profile.json"; profile_path.parent.mkdir(parents=True); profile_path.write_text(json.dumps(profile), encoding="utf-8")
    assert orchestration.load_owner_profile("future", root)["owner"] == "future"
    with pytest.raises(orchestration.InactiveOwnerError): orchestration.load_owner_profile("future", root, require_active=True)
    owners_path = root / "configs/owners_v1.json"; owners = json.loads(owners_path.read_text(encoding="utf-8")); owners["owners"]["future"] = {"active": True}; owners_path.write_text(json.dumps(owners), encoding="utf-8")
    paths_path = root / "configs/path_ownership_v1.json"; paths = json.loads(paths_path.read_text(encoding="utf-8")); paths["rules"].append({"kind": "directory_prefix", "path": "future_owners/future-owner", "authority": "owner", "owner": "future"}); paths_path.write_text(json.dumps(paths), encoding="utf-8")
    registry["owners"]["future"]["status"] = "active"; registry_path.write_text(json.dumps(registry), encoding="utf-8")
    assert orchestration.load_owner_profile("future", root, require_active=True)["owner"] == "future"


def test_registry_rejects_nested_owner_branch_prefixes(tmp_path: Path) -> None:
    root = _repo(tmp_path); registry_path = root / "configs/owner_scoped_orchestration_v1.json"; registry = json.loads(registry_path.read_text(encoding="utf-8"))
    registry["owners"]["nested"] = {"status": "owner_adoption_required", "git_owner": "nested", "branch_prefix": "core/sub/", "profile_path": "future_owners/nested-owner/orchestration_profile.json"}
    registry_path.write_text(json.dumps(registry), encoding="utf-8")
    with pytest.raises(orchestration.OrchestrationError, match="branch_prefix|prefixes"):
        orchestration.load_registry(root)


@pytest.mark.parametrize("branch_prefix", ("", "/core/", "core", "core//sub/", "core\\sub/", "Core/", "core/../sub/"))
def test_registry_rejects_unsafe_branch_prefixes(tmp_path: Path, branch_prefix: str) -> None:
    root = _repo(tmp_path); registry_path = root / "configs/owner_scoped_orchestration_v1.json"; registry = json.loads(registry_path.read_text(encoding="utf-8"))
    registry["owners"]["future"] = {"status": "owner_adoption_required", "git_owner": "future", "branch_prefix": branch_prefix, "profile_path": "future_owners/future-owner/orchestration_profile.json"}
    registry_path.write_text(json.dumps(registry), encoding="utf-8")
    with pytest.raises(orchestration.OrchestrationError, match="branch_prefix|prefixes"):
        orchestration.load_registry(root)


@pytest.mark.parametrize("branch", ("core/", "core//nested", "core/../nested", "core/nested/", "core/nested\\name", "core/Nested"))
def test_packet_rejects_empty_or_unsafe_branch_suffixes(tmp_path: Path, branch: str) -> None:
    with pytest.raises(orchestration.OrchestrationError, match="branch"):
        _packet(_repo(tmp_path), branch=branch)


def test_fail_closed_owner_profile_and_model_binding(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    with pytest.raises(orchestration.InactiveOwnerError): orchestration.owner_config("example_feature", root, active=True)
    profile = root / "roles/core/orchestration_profile.json"; profile.unlink()
    with pytest.raises(orchestration.OrchestrationError, match="missing"): orchestration.load_active_owner_profile("core", root)
    root = _repo(tmp_path / "other"); registry_path = root / "configs/owner_scoped_orchestration_v1.json"; registry = json.loads(registry_path.read_text(encoding="utf-8")); registry["model_binding"]["runner"]["model"] = "wrong"; registry_path.write_text(json.dumps(registry), encoding="utf-8")
    with pytest.raises(orchestration.OrchestrationError, match="binding"): _packet(root)


def test_check_owner_validates_prospective_profiles_without_activating(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = _repo(tmp_path); target = _prospective_profile(root)
    assert orchestration.main(["--repo", str(root), "check-owner", "--owner", "example_feature"]) == 0
    assert orchestration.main(["--repo", str(root), "check-owner", "--owner", "example_feature", "--active"]) == 2
    target.unlink()
    assert orchestration.main(["--repo", str(root), "check-owner", "--owner", "example_feature"]) == 3
    _prospective_profile(root, malformed=True)
    assert orchestration.main(["--repo", str(root), "check-owner", "--owner", "example_feature"]) == 3
    _prospective_profile(root, mismatched=True)
    assert orchestration.main(["--repo", str(root), "check-owner", "--owner", "example_feature"]) == 3
    assert orchestration.main(["--repo", str(root), "check-owner", "--owner", "core", "--active"]) == 0
    capsys.readouterr()


@pytest.mark.parametrize(("description", "paths", "tier"), [("analysis", [], "orchestrator_only"), ("A2A note", ["Project_Obsidian_Vault/40_Coordination/Threads/note.md"], "orchestrator_only"), ("continuity note", ["Project_Obsidian_Vault/30_Core/Continuity/Topics/note.md"], "orchestrator_only"), ("low-risk documentation", ["docs/note.md"], "orchestrator_only"), ("bounded", ["tools/x.py"], "orchestrator_plus_implementer"), ("canonical", ["Project_Obsidian_Vault/00_Canonical/SPEC.md"], "full_team"), ("policy", ["AGENTS.md"], "full_team"), ("runtime public contract", ["src/x.py"], "full_team")])
def test_risk_tiers(description: str, paths: list[str], tier: str) -> None:
    assert orchestration.classify_task(description, paths)["tier"] == tier


def test_requested_tier_escalates_and_never_downgrades(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    assert _packet(root, description="low-risk documentation", allowed=["docs/note.md"], requested_tier="full_team")["classification"]["tier"] == "full_team"
    assert _packet(root, description="runtime change", requested_tier="orchestrator_only")["classification"]["tier"] == "full_team"


@pytest.mark.parametrize("worktree", ["/absolute", "../escape", ".git/worktree", "other/task"])
def test_worktree_safety(tmp_path: Path, worktree: str) -> None:
    with pytest.raises(orchestration.OrchestrationError, match="worktree"):
        _packet(_repo(tmp_path), worktree=worktree)


def test_path_scope_overlap_and_changed_scope_rejection(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    with pytest.raises(orchestration.OrchestrationError, match="overlap"):
        _packet(root, allowed=["tools/"], prohibited=["tools/private/"])
    with pytest.raises(orchestration.OrchestrationError, match="unsafe"):
        _packet(root, allowed=[".git/config"])
    packet = _packet(root); receipt = _implementer(packet); receipt["changed_paths"] = ["docs/outside.md"]
    with pytest.raises(orchestration.OrchestrationError, match="outside"):
        orchestration.validate_receipts(packet, receipt, repo=root)


def test_path_ownership_nested_override_duplicate_rejection_and_shared_routing(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    owners_path = root / "configs/owners_v1.json"
    owners = json.loads(owners_path.read_text(encoding="utf-8"))
    owners["owners"]["feature"] = {"active": True}
    owners_path.write_text(json.dumps(owners), encoding="utf-8")
    orchestration_path = root / "configs/owner_scoped_orchestration_v1.json"
    registry = json.loads(orchestration_path.read_text(encoding="utf-8"))
    registry["owners"]["feature"] = {"status": "active", "git_owner": "feature", "branch_prefix": "feature/", "profile_path": "future_owners/feature/orchestration_profile.json"}
    orchestration_path.write_text(json.dumps(registry), encoding="utf-8")
    paths_path = root / "configs/path_ownership_v1.json"
    paths = json.loads(paths_path.read_text(encoding="utf-8"))
    paths["rules"].append({"kind": "directory_prefix", "path": "tools/feature", "authority": "owner", "owner": "feature"})
    paths_path.write_text(json.dumps(paths), encoding="utf-8")
    assert orchestration.resolve_path_ownership("tools/feature/worker.py", root)["owner"] == "feature"
    assert orchestration.resolve_path_ownership("AGENTS.md", root)["kind"] == "exact_file"
    assert orchestration.resolve_path_ownership("coordination/request.md", root)["authority"] == "shared_routed"
    paths["rules"].append({"kind": "directory_prefix", "path": "tools/feature", "authority": "owner", "owner": "feature"})
    paths_path.write_text(json.dumps(paths), encoding="utf-8")
    with pytest.raises(orchestration.OrchestrationError, match="ambiguously"):
        orchestration.load_path_ownership_registry(root)


def test_path_ownership_rejects_unknown_shared_and_inactive_owner_packet_paths(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    with pytest.raises(orchestration.OrchestrationError, match="unknown path ownership"):
        _packet(root, allowed=["unregistered/path.py"])
    with pytest.raises(orchestration.OrchestrationError, match="shared and routed"):
        _packet(root, allowed=["coordination/request.md"])
    owners_path = root / "configs/owners_v1.json"; owners = json.loads(owners_path.read_text(encoding="utf-8")); owners["owners"]["core"]["active"] = False; owners_path.write_text(json.dumps(owners), encoding="utf-8")
    with pytest.raises(orchestration.OrchestrationError, match="exist and be active"):
        orchestration.load_path_ownership_registry(root)


def test_every_tracked_path_has_exactly_one_owner_or_shared_route() -> None:
    tracked = subprocess.run(["git", "ls-files"], cwd=PROJECT_ROOT, capture_output=True, text=True, check=True).stdout.splitlines()
    resolutions = [orchestration.resolve_path_ownership(path, PROJECT_ROOT) for path in tracked]
    assert len(resolutions) == len(tracked)
    assert all(rule["authority"] in {"owner", "shared_routed"} for rule in resolutions)


def test_runner_channel_workaround_requires_reusable_saved_project_route(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    packet = _packet(root, description="runtime change")
    requirement = orchestration.load_runner_channel_workaround(root)
    assert requirement["locally_verified_resolved"] is False
    assert requirement["creation_per_cycle"] == "one_fresh_luna_chat_inside_matching_saved_project"
    assert requirement["ordered_lifecycle"] == ["create_fresh_saved_project_luna_chat", "bind_gpt_5_6_luna_xhigh", "reuse_exact_thread_id_for_verification_and_reverification", "reassert_model_and_reasoning_effort_on_every_continuation", "archive_only_after_receipt_capture_push_integration_primary_sync_terminal_reconciliation_worktree_removal_and_finalization", "keep_failed_blocked_and_user_input_needed_visible"]
    assert requirement["host_turn_context"] == {"source": "host_recorded", "required_fields": ["channel", "project_context", "thread_id", "model"]}
    orchestration.validate_runner_channel(_turn_context(packet), packet["subordinate_task_ids"]["runner"], packet["subordinate_task_ids"]["runner"], {"model": "gpt-5.6-luna", "reasoning_effort": "xhigh"}, root)
    with pytest.raises(orchestration.OrchestrationError, match="route_integrity_failed"):
        orchestration.validate_runner_channel({**_turn_context(packet), "source": "agent_reported"}, packet["subordinate_task_ids"]["runner"], packet["subordinate_task_ids"]["runner"], {"model": "gpt-5.6-luna", "reasoning_effort": "xhigh"}, root)


def test_implementer_receipt_exact_shape_actions_and_checks(tmp_path: Path) -> None:
    root = _repo(tmp_path); packet = _packet(root); receipt = _implementer(packet)
    orchestration.validate_receipts(packet, receipt, repo=root)
    receipt["prompt"] = "private"
    with pytest.raises(orchestration.OrchestrationError, match="forbidden"): orchestration.validate_receipts(packet, receipt, repo=root)
    receipt = _implementer(packet); receipt["actions"] = ["push"]
    with pytest.raises(orchestration.OrchestrationError, match="forbidden Git"): orchestration.validate_receipts(packet, receipt, repo=root)
    valid = _implementer(packet)["checks"]
    for checks, error in [([], "exactly once"), ([*valid, valid[0]], "exactly once"), ([valid[1], valid[0], valid[2]], "exactly once"), ([{"command": valid[0]["command"], "outcome": "failed"}], "failed")]:
        receipt = _implementer(packet); receipt["checks"] = checks
        with pytest.raises(orchestration.OrchestrationError if error != "failed" else orchestration.InactiveOwnerError, match=error): orchestration.validate_receipts(packet, receipt, repo=root)
    receipt = _implementer(packet); receipt["residual_issues"] = ["token=private"]
    with pytest.raises(orchestration.OrchestrationError, match="credentials"): orchestration.validate_receipts(packet, receipt, repo=root)


def test_full_team_requires_final_candidate_and_one_luna_full_check(tmp_path: Path) -> None:
    root = _repo(tmp_path); packet = _packet(root, description="runtime change"); implementer = _implementer(packet); binding = _bind_runner(packet, implementer, "b" * 40, root); runner = _runner(packet, binding)
    assert packet["runner_checks"] == ["python tools/test_runner.py full"]
    assert binding["candidate_posture"] == "sol_declared_final"
    orchestration.validate_receipts(packet, implementer, binding, runner, repo=root)
    with pytest.raises(orchestration.OrchestrationError, match="full command exactly once"):
        _packet(root, description="runtime change", runner_checks=[])
    binding["implementer_receipt_hashes"] = {"primary": "0" * 64, "bounded_correction": None}; binding["canonical_hash"] = orchestration.sha256_canonical({key: value for key, value in binding.items() if key != "canonical_hash"})
    with pytest.raises(orchestration.OrchestrationError, match="implementer receipt hash"): orchestration.validate_receipts(packet, implementer, binding, runner, repo=root)
    binding = _bind_runner(packet, implementer, "b" * 40, root); binding["turn_context"]["channel"] = "projectless_task"; binding["canonical_hash"] = orchestration.sha256_canonical({key: value for key, value in binding.items() if key != "canonical_hash"})
    with pytest.raises(orchestration.OrchestrationError, match="route_integrity_failed"): orchestration.validate_receipts(packet, implementer, binding, runner, repo=root)
    binding = _bind_runner(packet, implementer, "b" * 40, root); runner = _runner(packet, binding); runner["runner_binding_hash"] = "0" * 64
    with pytest.raises(orchestration.OrchestrationError, match="binding hash"): orchestration.validate_receipts(packet, implementer, binding, runner, repo=root)
    runner = _runner(packet, binding); runner["actions"] = ["commit"]
    with pytest.raises(orchestration.OrchestrationError, match="write action"): orchestration.validate_receipts(packet, implementer, binding, runner, repo=root)
    runner = _runner(packet, binding); runner["checks"] = [{"command": orchestration.LUNA_FULL_COMMAND, "outcome": "failed"}]
    with pytest.raises(orchestration.InactiveOwnerError, match="failed"): orchestration.validate_receipts(packet, implementer, binding, runner, repo=root)
    binding = _bind_runner(packet, implementer, "b" * 40, root); binding["candidate_posture"] = "candidate"; binding["canonical_hash"] = orchestration.sha256_canonical({key: value for key, value in binding.items() if key != "canonical_hash"})
    with pytest.raises(orchestration.OrchestrationError, match="declared final candidate"): orchestration.validate_receipts(packet, implementer, binding, _runner(packet, binding), repo=root)
    binding = _bind_runner(packet, implementer, "b" * 40, root)
    runner = _runner(packet, binding); runner["environment_preflight"]["initial_worktree_clean"] = False
    with pytest.raises(orchestration.OrchestrationError, match="environment_preflight"): orchestration.validate_receipts(packet, implementer, binding, runner, repo=root)
    runner = _runner(packet, binding); runner["git_status"]["final"] = "dirty"
    with pytest.raises(orchestration.OrchestrationError, match="git_status"): orchestration.validate_receipts(packet, implementer, binding, runner, repo=root)
    runner = _runner(packet, binding); runner["reconciler_evidence"]["candidate_commit"] = "c" * 40
    with pytest.raises(orchestration.OrchestrationError, match="reconciler_evidence"): orchestration.validate_receipts(packet, implementer, binding, runner, repo=root)
    runner = _runner(packet, binding); runner["diagnostics"] = ["C:/private/path"]
    with pytest.raises(orchestration.OrchestrationError, match="filesystem path"): orchestration.validate_receipts(packet, implementer, binding, runner, repo=root)


def test_tier_correct_records_and_new_candidate_rebinding(tmp_path: Path) -> None:
    root = _repo(tmp_path); tier_one = _packet(root, task_id="tier-one", description="analysis", allowed=[])
    with pytest.raises(orchestration.OrchestrationError, match="Sol disposition"):
        orchestration.record_bundle(tier_one, repo=root)
    record = orchestration.record_bundle(tier_one, sol_disposition=_sol(tier_one), repo=root)
    bundle = root / "receipts/tier-one" / tier_one["canonical_hash"]
    assert (bundle / "sol_disposition.json").exists() and not (bundle / "runner_receipt.json").exists() and record["tier"] == "orchestrator_only"
    tier_two = _packet(root, task_id="tier-two"); orchestration.record_bundle(tier_two, _implementer(tier_two), repo=root)
    assert not (root / "receipts/tier-two" / tier_two["canonical_hash"] / "runner_receipt.json").exists()
    full = _packet(root, task_id="full", description="runtime change"); first = _implementer(full); first_binding = _bind_runner(full, first, "b" * 40, root); second = _implementer(full, "c" * 40)
    with pytest.raises(orchestration.OrchestrationError, match="candidate"): orchestration.validate_receipts(full, second, first_binding, _runner(full, first_binding), repo=root)
    second_binding = _bind_runner(full, second, "c" * 40, root); runner = _runner(full, second_binding, "c" * 40); orchestration.validate_receipts(full, second, second_binding, runner, repo=root)
    orchestration.record_bundle(full, second, second_binding, runner, repo=root)
    full_bundle = root / "receipts/full" / full["canonical_hash"]
    assert {path.name for path in full_bundle.iterdir()} == {"packet.json", "implementer_receipt.json", "runner_binding.json", "runner_receipt.json", "subordinate_archive_manifest.json", "record.json"}


def test_closeout_requires_exact_receipts_reconciliation_cleanup_and_archival(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    packet = _packet(root, task_id="finalize", description="runtime change")
    implementer = _implementer(packet)
    binding = _bind_runner(packet, implementer, "b" * 40, root)
    runner = _runner(packet, binding)
    record = orchestration.record_bundle(packet, implementer, binding, runner, repo=root)
    bundle = root / "receipts/finalize" / packet["canonical_hash"]
    manifest = json.loads((bundle / "subordinate_archive_manifest.json").read_text(encoding="utf-8"))
    acknowledgment = _archive_acknowledgment(manifest)
    evidence = _delivery_evidence(packet, implementer, binding, runner, record)

    finalization = orchestration.finalize_closeout(packet, implementer, binding, runner, manifest, acknowledgment, record, evidence, root)

    assert finalization["outcome"] == "closed"
    assert finalization["captured_receipt_hashes"] == evidence["captured_receipt_hashes"]
    assert finalization["subordinate_task_dispositions"] == [
        {"lane": item["lane"], "implementer_type": item["implementer_type"], "subordinate_task_id": item["subordinate_task_id"], "disposition": item["disposition"]}
        for item in acknowledgment["lane_dispositions"]
    ]
    assert finalization["terminal_reconciliation"]["disposition"] == "landed"
    assert finalization["primary_branch_sync"]["verified"] is True
    assert finalization["worktree_removal"]["removed"] is True


@pytest.mark.parametrize(
    ("field", "replacement", "message"),
    [
        ("terminal_reconciliation", {"target": "origin/master", "disposition": "awaiting_named_integrator", "evidence_ref": "reconciler:pending"}, "terminal branch reconciliation"),
        ("primary_branch_sync", {"verified": False, "evidence_ref": "reconciler:dirty"}, "primary-branch synchronization"),
        ("worktree_removal", {"worktree": ".worktrees/finalize", "removed": False, "evidence_ref": "git:retained"}, "worktree removal"),
    ],
)
def test_closeout_rejects_nonterminal_delivery_state(tmp_path: Path, field: str, replacement: object, message: str) -> None:
    root = _repo(tmp_path)
    packet = _packet(root, task_id="finalize", description="runtime change")
    implementer = _implementer(packet)
    binding = _bind_runner(packet, implementer, "b" * 40, root)
    runner = _runner(packet, binding)
    record = orchestration.record_bundle(packet, implementer, binding, runner, repo=root)
    bundle = root / "receipts/finalize" / packet["canonical_hash"]
    manifest = json.loads((bundle / "subordinate_archive_manifest.json").read_text(encoding="utf-8"))
    acknowledgment = _archive_acknowledgment(manifest)
    evidence = _delivery_evidence(packet, implementer, binding, runner, record)
    evidence[field] = replacement
    evidence["canonical_hash"] = orchestration.sha256_canonical({key: value for key, value in evidence.items() if key != "canonical_hash"})

    with pytest.raises(orchestration.OrchestrationError, match=message):
        orchestration.finalize_closeout(packet, implementer, binding, runner, manifest, acknowledgment, record, evidence, root)


def test_record_failure_cleans_exact_temp_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _repo(tmp_path); packet = _packet(root, task_id="atomic"); receipt = _implementer(packet)
    original = orchestration._exclusive_write
    def fail(path: Path, value: object) -> None:
        if path.name == "record.json": raise OSError("injected")
        original(path, value)
    monkeypatch.setattr(orchestration, "_exclusive_write", fail)
    with pytest.raises(OSError): orchestration.record_bundle(packet, receipt, repo=root)
    task_root = root / "receipts/atomic"
    assert not task_root.exists() or not any(task_root.iterdir())
    staging_root = root / "tmp/owner_scoped_orchestration_receipts"
    assert not staging_root.exists() or not any(staging_root.iterdir())
    monkeypatch.setattr(orchestration, "_exclusive_write", original)
    assert orchestration.record_bundle(packet, receipt, repo=root)["task_id"] == "atomic"


def test_long_windows_receipt_path_publishes_atomically_without_overwrite(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    profile_path = root / "roles/core/orchestration_profile.json"
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    profile["continuity_receipts_root"] = "Project_Obsidian_Vault/30_Core/Continuity/Orchestration Receipts"
    profile_path.write_text(json.dumps(profile), encoding="utf-8")
    packet = _packet(root, task_id="core-owner-scoped-orchestration-20260806")
    receipt = _implementer(packet)
    bundle_path = root / profile["continuity_receipts_root"] / packet["task_id"] / packet["canonical_hash"]
    assert len(str(bundle_path)) > 260
    record = orchestration.record_bundle(packet, receipt, repo=root)
    record_path = bundle_path / "record.json"
    with open(orchestration._filesystem_path(record_path), "rb") as record_file:
        original_record = record_file.read()
    assert record["canonical_hash"] == json.loads(original_record.decode("utf-8"))["canonical_hash"]
    with pytest.raises(orchestration.OrchestrationError, match="task IDs are unique"):
        orchestration.record_bundle(packet, receipt, repo=root)
    with open(orchestration._filesystem_path(record_path), "rb") as record_file:
        assert record_file.read() == original_record
    staging_root = root / "tmp/owner_scoped_orchestration_receipts"
    assert not staging_root.exists() or not any(staging_root.iterdir())


def test_same_owner_rejects_second_packet_with_same_task_id(tmp_path: Path) -> None:
    root = _repo(tmp_path); first = _packet(root, task_id="unique-task"); orchestration.record_bundle(first, _implementer(first), repo=root)
    second = dict(first); second["user_approval_ref"] = "user:corrected"; second["canonical_hash"] = orchestration.sha256_canonical({key: value for key, value in second.items() if key != "canonical_hash"})
    with pytest.raises(orchestration.OrchestrationError, match="task IDs are unique"):
        orchestration.record_bundle(second, _implementer(second), repo=root)


def test_read_only_cli_and_tmp_only_writes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = _repo(tmp_path); before = sorted(path.relative_to(root).as_posix() for path in root.rglob("*"))
    assert orchestration.main(["--repo", str(root), "check-owner", "--owner", "core"]) == 0
    assert orchestration.main(["--repo", str(root), "classify", "--owner", "core", "--description", "analysis"]) == 0
    assert sorted(path.relative_to(root).as_posix() for path in root.rglob("*")) == before
    packet = _packet(root); packet_path = root / "packet.json"; receipt_path = root / "receipt.json"; context_path = root / "turn_context.json"; packet_path.write_text(json.dumps(packet), encoding="utf-8"); receipt_path.write_text(json.dumps(_implementer(packet)), encoding="utf-8"); context_path.write_text(json.dumps({"source": "host_recorded", "channel": "saved_project_reusable_chat", "project_context": "matching_saved_project", "thread_id": "host-runner", "model": {"model": "gpt-5.6-luna", "reasoning_effort": "xhigh"}}), encoding="utf-8")
    before_validate = sorted(path.relative_to(root).as_posix() for path in root.rglob("*"))
    assert orchestration.main(["--repo", str(root), "validate", "--packet", str(packet_path), "--implementer-receipt", str(receipt_path)]) == 0
    assert sorted(path.relative_to(root).as_posix() for path in root.rglob("*")) == before_validate
    assert orchestration.main(["--repo", str(root), "bind-runner", "--packet", str(packet_path), "--implementer-receipt", str(receipt_path), "--candidate-commit", "b" * 40, "--turn-context", str(context_path), "--output", "outside.json"]) == 3
    assert not (root / "outside.json").exists(); capsys.readouterr()


def test_direct_cli_bootstraps_its_worktree_before_foreign_checkout(tmp_path: Path) -> None:
    foreign_checkout = tmp_path / "foreign_checkout"
    foreign_platform = foreign_checkout / "repo_support/platform"
    foreign_platform.mkdir(parents=True)
    (foreign_checkout / "repo_support/__init__.py").write_text("", encoding="utf-8")
    (foreign_platform / "__init__.py").write_text("", encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, str(TOOLS / "owner_scoped_orchestration.py"), "--repo", str(PROJECT_ROOT), "check-owner", "--owner", "core"],
        cwd=foreign_checkout,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr


def test_tmp_outputs_are_immutable(tmp_path: Path) -> None:
    root = _repo(tmp_path); output = orchestration._write_tmp(root, "tmp/packet.json", {"value": 1})
    with pytest.raises(orchestration.OrchestrationError, match="no-overwrite"):
        orchestration._write_tmp(root, "tmp/packet.json", {"value": 2})
    assert json.loads(output.read_text(encoding="utf-8")) == {"value": 1}
