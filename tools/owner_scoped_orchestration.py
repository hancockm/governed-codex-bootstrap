"""Validate owner-scoped development-orchestration packets and receipts.

It governs development lanes only; it neither invokes models nor executes Git
commands.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))
if str(REPOSITORY_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from governance_bootstrap.common import (
    canonical_json,
    sha256_canonical,
    validate_safe_diagnostic,
)


REGISTRY_SCHEMA = "owner_scoped_orchestration_v1"
PROFILE_SCHEMA = "owner_scoped_orchestration_owner_profile_v1"
PACKET_SCHEMA = "owner_scoped_task_packet_v2"
LEGACY_PACKET_SCHEMA = "owner_scoped_task_packet_v1"
IMPLEMENTER_RECEIPT_SCHEMA = "owner_scoped_implementer_receipt_v1"
RUNNER_BINDING_SCHEMA = "owner_scoped_runner_binding_v2"
RUNNER_RECEIPT_SCHEMA = "owner_scoped_runner_receipt_v1"
SOL_DISPOSITION_SCHEMA = "owner_scoped_sol_disposition_v1"
RECORD_SCHEMA = "owner_scoped_orchestration_record_v2"
ARCHIVE_MANIFEST_SCHEMA = "owner_scoped_subordinate_archive_manifest_v2"
ARCHIVE_ACKNOWLEDGMENT_SCHEMA = "owner_scoped_subordinate_archive_acknowledgment_v1"
CLOSEOUT_DELIVERY_EVIDENCE_SCHEMA = "owner_scoped_closeout_delivery_evidence_v1"
CLOSEOUT_FINALIZATION_SCHEMA = "owner_scoped_closeout_finalization_v2"
DEFAULT_REGISTRY = Path("configs/owner_scoped_orchestration_v1.json")
HEX40 = re.compile(r"^[0-9a-f]{40}$")
TASK_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:[-_][a-z0-9]+)*$")
BRANCH_SEGMENT_PATTERN = re.compile(r"^[a-z0-9]+(?:[-_][a-z0-9]+)*$")
MAX_TASK_ID_LENGTH = 128
MAX_SUBORDINATE_TASK_ID_LENGTH = 256
OPAQUE_TASK_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")
RISK_TRIGGERS = {
    "runtime": ("runtime", "execution loop", "provider"),
    "public_contract": ("public contract", "public api", "public symbol"),
    "canonical_doctrine": ("canonical doctrine", "core thesis", "architecture", "specification"),
    "persistence": ("persistence", "sqlite", "database", "migration"),
    "security_privacy": ("security", "privacy", "secret", "credential"),
    "math": ("math", "kernel", "rkhs", "spectral"),
    "external_adapter": ("external adapter", "adapter", "mcp", "api client"),
    "migration": ("migration",),
    "user_facing": ("user-facing", "ui", "frontend"),
    "legal_release": ("legal release", "release"),
    "cross_owner_integration": ("cross-owner", "cross owner", "integration"),
    "full_suite": ("full suite", "full-suite"),
}
RUNNER_WRITE_ACTIONS = frozenset({"write", "commit", "push", "merge", "rebase", "reset", "delete", "touch_master"})
IMPLEMENTER_FORBIDDEN_ACTIONS = frozenset({"push", "merge", "rebase", "reset", "delete", "touch_master"})
IMPLEMENTER_KEYS = frozenset({"schema_version", "owner", "task_id", "packet_hash", "model", "candidate_commit", "changed_paths", "actions", "checks", "residual_issues", "outcome"})
RUNNER_KEYS = frozenset({"schema_version", "owner", "task_id", "packet_hash", "runner_binding_hash", "model", "candidate_commit", "actions", "checks", "environment_preflight", "git_status", "reconciler_evidence", "diagnostics", "residual_issues", "outcome"})
SOL_KEYS = frozenset({"schema_version", "owner", "task_id", "packet_hash", "model", "disposition", "residual_issues", "outcome"})
PACKET_KEYS = frozenset({"schema_version", "owner", "task_id", "user_approval_ref", "task_description", "baseline", "branch", "worktree", "allowed_paths", "prohibited_paths", "lane_models", "owner_profile_ref", "owner_profile_hash", "evidence_refs", "focused_checks", "broad_checks", "responsibilities", "git_requirements", "continuity_requirements", "classification", "subordinate_task_ids", "canonical_hash"})
PACKET_RESPONSIBILITIES = {"owner_orchestrator": "classify and publish", "implementer": "bounded candidate only", "runner": "inspect and test only"}


class OrchestrationError(RuntimeError):
    """Raised for a schema, safety, or packet validation failure."""


def repository_root(repo: str | Path | None = None) -> Path:
    """Return the resolved repository root without performing Git operations."""

    return Path(repo or REPOSITORY_ROOT).resolve()


def load_registry(repo: str | Path | None = None) -> dict[str, Any]:
    """Load the authoritative development-orchestration registry."""

    root = repository_root(repo)
    try:
        value = json.loads((root / DEFAULT_REGISTRY).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OrchestrationError("cannot load owner-scoped orchestration registry") from exc
    if not isinstance(value, dict) or value.get("schema_version") != REGISTRY_SCHEMA:
        raise OrchestrationError(f"registry must use {REGISTRY_SCHEMA}")
    if value.get("topology") != "hybrid" or value.get("model_binding", {}).get("enforcement") != "fail_closed":
        raise OrchestrationError("registry must declare hybrid fail-closed model binding")
    if value.get("git", {}).get("master_integration_owner") != "core":
        raise OrchestrationError("only Core may be configured for master integration")
    owners = value.get("owners")
    if not isinstance(owners, dict):
        raise OrchestrationError("registry owners must be an object")
    required = {"core"}
    if not required.issubset(owners):
        raise OrchestrationError("registry owner set is missing the required Core owner")
    branch_prefixes: set[str] = set()
    profile_paths: set[str] = set()
    for name, entry in owners.items():
        if not isinstance(name, str) or not name or not isinstance(entry, dict):
            raise OrchestrationError("registry owner entries must be named objects")
        if entry.get("status") not in {"active", "owner_adoption_required"}:
            raise OrchestrationError(f"registry owner {name!r} has an invalid status")
        for field in ("git_owner", "branch_prefix", "profile_path"):
            if not isinstance(entry.get(field), str) or not entry[field]:
                raise OrchestrationError(f"registry owner {name!r} requires {field}")
        if not _is_safe_branch_prefix(entry["branch_prefix"]) or any(_branch_prefixes_overlap(entry["branch_prefix"], prefix) for prefix in branch_prefixes):
            raise OrchestrationError("registry owner branch prefixes must be unique and conservative")
        branch_prefixes.add(entry["branch_prefix"])
        _repo_relative_path(root, entry["profile_path"], f"owner {name} profile_path")
        if entry["profile_path"] in profile_paths:
            raise OrchestrationError("registry owner profile paths must be unique")
        profile_paths.add(entry["profile_path"])
    aliases = value.get("aliases", {})
    if not isinstance(aliases, dict) or any(
        not isinstance(alias, str) or not isinstance(target, str) or alias in owners or target not in owners
        for alias, target in aliases.items()
    ):
        raise OrchestrationError("registry aliases must be non-colliding registered-owner aliases")
    _require_lane_bindings(value)
    _require_subordinate_lifecycle(value)
    return value


def _require_lane_bindings(registry: Mapping[str, Any]) -> None:
    expected = {
        "owner_orchestrator": ("gpt-5.6-sol", "xhigh"),
        "implementer": ("gpt-5.6-terra", "high"),
        "runner": ("gpt-5.6-luna", "max"),
    }
    bindings = registry.get("model_binding", {})
    for lane, (model, effort) in expected.items():
        configured = bindings.get(lane, {})
        if configured.get("model") != model or configured.get("reasoning_effort") != effort:
            raise OrchestrationError(f"invalid fail-closed model binding for {lane}")


def _require_subordinate_lifecycle(registry: Mapping[str, Any]) -> None:
    """Require the complete Sol-owned subordinate finalization lifecycle."""

    lifecycle = registry.get("subordinate_task_lifecycle", {})
    expected_archive_after = {
        "accepted_exact_candidate_receipt",
        "no_correction_pending",
        "commit_push_integration",
        "primary_branch_sync",
        "terminal_reconciliation",
        "worktree_cleanup",
    }
    expected_finalization = {
        "recorded_receipt_hashes",
        "subordinate_task_dispositions",
        "terminal_reconciliation",
        "primary_branch_sync",
        "worktree_removal",
        "archive_acknowledgment",
    }
    if (
        lifecycle.get("saved_project_required") is not True
        or lifecycle.get("reuse_runner_thread_per_cycle") is not True
        or lifecycle.get("archive_owner") != "owner_orchestrator"
        or set(lifecycle.get("archive_after", ())) != expected_archive_after
        or set(lifecycle.get("finalization_requires", ())) != expected_finalization
        or lifecycle.get("visible_nonterminal_statuses")
        != ["failed", "blocked", "user_input_needed"]
    ):
        raise OrchestrationError("registry subordinate-task lifecycle is incomplete")


def owner_config(owner: str, repo: str | Path | None = None, *, active: bool = False) -> dict[str, Any]:
    """Return one registered owner, optionally requiring active adoption."""

    registry = load_registry(repo)
    key = owner.strip().lower()
    key = registry.get("aliases", {}).get(key, key)
    value = registry["owners"].get(key)
    if not isinstance(value, dict):
        raise InactiveOwnerError(f"unresolved owner: {owner}")
    if active and value.get("status") != "active":
        raise InactiveOwnerError(f"owner adoption required: {key}")
    return {"name": key, **value}


class InactiveOwnerError(OrchestrationError):
    """Raised when a registered but inactive owner requests an active lane."""


def load_owner_profile(owner: str, repo: str | Path | None = None, *, require_active: bool = False) -> dict[str, Any]:
    """Validate a registered owner's profile without creating repository paths.

    Prospective owners may validate their profile before Core changes the owner
    status. Dispatch callers set ``require_active`` and therefore fail closed.
    """

    root = repository_root(repo)
    config = owner_config(owner, root, active=require_active)
    path = _repo_relative_path(root, config["profile_path"], "owner profile path")
    try:
        profile = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OrchestrationError(f"missing or invalid owner profile: {path}") from exc
    if profile.get("schema_version") != PROFILE_SCHEMA or profile.get("owner") != config["name"]:
        raise OrchestrationError("owner profile schema or owner does not match registry")
    for field in ("role_instruction_path", "bootstrap_prompt_path", "continuity_moc_path", "continuity_receipts_root", "branch_prefix", "verification_profiles"):
        if not profile.get(field):
            raise OrchestrationError(f"owner profile requires {field}")
    if profile["branch_prefix"] != config["branch_prefix"]:
        raise OrchestrationError("owner profile branch prefix does not match registry")
    for field in ("role_instruction_path", "bootstrap_prompt_path", "continuity_moc_path"):
        reference = _repo_relative_path(root, profile[field], field)
        if not reference.is_file():
            raise OrchestrationError(f"owner profile reference is missing: {field}")
    _repo_relative_path(root, profile["continuity_receipts_root"], "continuity_receipts_root")
    verification = profile["verification_profiles"]
    if not isinstance(verification, dict) or set(verification) != {"focused", "broad"}:
        raise OrchestrationError("owner profile verification_profiles must define focused and broad")
    for name, checks in verification.items():
        if not isinstance(checks, list) or not checks or any(not isinstance(item, str) or not item for item in checks):
            raise OrchestrationError(f"owner profile {name} verification checks are required")
    return profile


def load_active_owner_profile(owner: str, repo: str | Path | None = None) -> dict[str, Any]:
    """Load and validate the active owner's profile for dispatch operations."""

    return load_owner_profile(owner, repo, require_active=True)


def classify_task(description: str, paths: Iterable[str] = ()) -> dict[str, Any]:
    """Deterministically select the minimum permitted lane topology.

    The static classifier is deliberately monotonic: callers may escalate its
    tier but no caller may downgrade a triggered full-team condition.
    """

    normalized_paths = _safe_paths(list(paths), "classification path")
    text = " ".join((description, *normalized_paths)).lower()
    triggers = [name for name, terms in RISK_TRIGGERS.items() if any(_contains_term(text, term) for term in terms)]
    triggers.extend(_path_risk_triggers(normalized_paths))
    triggers = list(dict.fromkeys(triggers))
    if triggers:
        tier = "full_team"
    elif not normalized_paths or _all_a2a_or_continuity_markdown(normalized_paths):
        tier = "orchestrator_only"
    elif _is_explicit_low_risk_documentation(description) and _all_safe_noncanonical_markdown(normalized_paths):
        tier = "orchestrator_only"
    else:
        tier = "orchestrator_plus_implementer"
    return {"schema_version": "owner_scoped_risk_classification_v1", "tier": tier, "triggers": tuple(triggers)}


def compose_prompt(owner: str, task_packet: Mapping[str, Any], repo: str | Path | None = None) -> dict[str, Any]:
    """Return explicit shared-base/profile/packet prompt composition metadata."""

    root = repository_root(repo)
    profile = load_active_owner_profile(owner, root)
    config = owner_config(owner, root, active=True)
    return {
        "schema_version": "owner_scoped_prompt_composition_v1",
        "shared_sol_base": "roles/shared/OWNER_ORCHESTRATOR_PROMPT.md",
        "owner": config["name"], "git_owner": config["git_owner"], "branch_prefix": config["branch_prefix"],
        "owner_profile": str(config["profile_path"]),
        "task_packet_hash": task_packet.get("canonical_hash", ""),
        "references": [profile["role_instruction_path"], profile["bootstrap_prompt_path"], profile["continuity_moc_path"]],
    }


def make_packet(*, owner: str, task_id: str, approval_ref: str, baseline: str, branch: str, worktree: str, allowed_paths: Iterable[str], prohibited_paths: Iterable[str], evidence_refs: Iterable[str], focused_checks: Iterable[str], broad_checks: Iterable[str], description: str, requested_tier: str | None = None, subordinate_task_ids: Mapping[str, str] | None = None, repo: str | Path | None = None) -> dict[str, Any]:
    """Build a self-hashing active-owner packet from explicit public inputs."""

    root = repository_root(repo)
    config = owner_config(owner, root, active=True)
    profile = load_active_owner_profile(owner, root)
    if not _is_safe_task_id(task_id) or not isinstance(approval_ref, str) or not isinstance(description, str) or not approval_ref.strip() or not description.strip() or not HEX40.fullmatch(baseline):
        raise OrchestrationError("task_id, approval_ref, and a 40-hex baseline are required")
    _require_safe_text(approval_ref, "packet user_approval_ref")
    _require_safe_text(description, "packet task_description")
    if not _is_safe_branch_for_prefix(branch, config["branch_prefix"]):
        raise OrchestrationError("branch does not use the owner profile prefix")
    allowed = _safe_paths(list(allowed_paths), "allowed path")
    prohibited = _safe_paths(list(prohibited_paths), "prohibited path")
    if _path_scopes_overlap(allowed, prohibited):
        raise OrchestrationError("allowed and prohibited paths overlap")
    worktree = _safe_worktree(worktree)
    evidence = list(evidence_refs)
    focused = list(focused_checks)
    broad = list(broad_checks)
    _require_safe_string_list(evidence, "packet evidence_refs")
    _require_safe_string_list(focused, "packet focused_checks")
    _require_safe_string_list(broad, "packet broad_checks")
    classification = classify_task(description, allowed)
    tiers = ("orchestrator_only", "orchestrator_plus_implementer", "full_team")
    if requested_tier and requested_tier not in tiers:
        raise OrchestrationError("unknown requested tier")
    effective = max((classification["tier"], requested_tier or classification["tier"]), key=tiers.index)
    subordinate_tasks = _validate_subordinate_task_ids(subordinate_task_ids, effective)
    payload = {
        "schema_version": PACKET_SCHEMA, "owner": config["name"], "task_id": task_id, "user_approval_ref": approval_ref, "task_description": description,
        "baseline": baseline, "branch": branch, "worktree": worktree, "allowed_paths": list(allowed), "prohibited_paths": list(prohibited),
        "lane_models": {lane: _lane_binding(load_registry(root), lane) for lane in ("owner_orchestrator", "implementer", "runner")},
        "owner_profile_ref": config["profile_path"], "owner_profile_hash": sha256_canonical(profile),
        "evidence_refs": evidence, "focused_checks": focused, "broad_checks": broad,
        "responsibilities": PACKET_RESPONSIBILITIES,
        "git_requirements": "Implementer may create a local candidate commit; Sol publishes and cleans owner worktrees; Core alone integrates master.",
        "continuity_requirements": "Owner orchestrator exports the full transcript; one packet-bound Terra/Luna host task is reused through every correction attempt and acknowledged before final closeout.",
        "classification": {**classification, "tier": effective},
        "subordinate_task_ids": subordinate_tasks,
    }
    return {**payload, "canonical_hash": sha256_canonical(payload)}


def validate_packet(packet: Mapping[str, Any], repo: str | Path | None = None) -> None:
    """Fail closed unless a packet is internally and registry-consistent."""

    if packet.get("schema_version") == LEGACY_PACKET_SCHEMA:
        raise OrchestrationError("legacy packet lacks required stable subordinate task IDs; issue a v2 packet")
    if set(packet) != PACKET_KEYS:
        raise OrchestrationError("packet has missing or forbidden fields")
    if packet.get("schema_version") != PACKET_SCHEMA:
        raise OrchestrationError("invalid packet schema")
    expected = {key: value for key, value in packet.items() if key != "canonical_hash"}
    if packet.get("canonical_hash") != sha256_canonical(expected):
        raise OrchestrationError("packet canonical hash mismatch")
    config = owner_config(str(packet.get("owner", "")), repo, active=True)
    if not _is_safe_task_id(packet.get("task_id")):
        raise OrchestrationError("packet task_id must be a conservative slug")
    _require_safe_text(packet.get("user_approval_ref"), "packet user_approval_ref")
    _require_safe_text(packet.get("task_description"), "packet task_description")
    if not HEX40.fullmatch(str(packet.get("baseline", ""))):
        raise OrchestrationError("packet baseline must be a 40-hex commit")
    if not _is_safe_branch_for_prefix(packet.get("branch"), config["branch_prefix"]):
        raise OrchestrationError("packet branch mismatch")
    registry = load_registry(repo)
    expected_models = {lane: _lane_binding(registry, lane) for lane in ("owner_orchestrator", "implementer", "runner")}
    if packet.get("lane_models") != expected_models:
        raise OrchestrationError("packet lane model bindings mismatch")
    profile = load_active_owner_profile(config["name"], repo)
    if packet.get("owner_profile_ref") != config["profile_path"] or packet.get("owner_profile_hash") != sha256_canonical(profile):
        raise OrchestrationError("packet owner profile identity mismatch")
    allowed = _safe_paths(packet.get("allowed_paths", ()), "allowed path")
    prohibited = _safe_paths(packet.get("prohibited_paths", ()), "prohibited path")
    if _path_scopes_overlap(allowed, prohibited):
        raise OrchestrationError("allowed and prohibited paths overlap")
    _safe_worktree(str(packet.get("worktree", "")))
    _require_safe_string_list(packet.get("evidence_refs"), "packet evidence_refs")
    _require_safe_string_list(packet.get("focused_checks"), "packet focused_checks")
    _require_safe_string_list(packet.get("broad_checks"), "packet broad_checks")
    if packet.get("responsibilities") != PACKET_RESPONSIBILITIES:
        raise OrchestrationError("packet responsibilities mismatch")
    _require_safe_text(packet.get("git_requirements"), "packet git_requirements")
    _require_safe_text(packet.get("continuity_requirements"), "packet continuity_requirements")
    classification = packet.get("classification")
    if not isinstance(classification, dict) or set(classification) != {"schema_version", "tier", "triggers"}:
        raise OrchestrationError("packet classification has missing or forbidden fields")
    static = classify_task(packet["task_description"], allowed)
    if classification.get("schema_version") != static["schema_version"] or tuple(classification.get("triggers", ())) != static["triggers"]:
        raise OrchestrationError("packet classification does not match static triggers")
    tiers = ("orchestrator_only", "orchestrator_plus_implementer", "full_team")
    if classification.get("tier") not in tiers or tiers.index(classification["tier"]) < tiers.index(static["tier"]):
        raise OrchestrationError("packet classification tier downgrades static risk")
    _validate_subordinate_task_ids(packet.get("subordinate_task_ids"), classification["tier"])


def bind_runner(packet: Mapping[str, Any], implementer_receipt: Mapping[str, Any], candidate_commit: str, repo: str | Path | None = None) -> dict[str, Any]:
    """Bind a runner to one validated receipt and exact candidate commit."""

    validate_packet(packet, repo)
    if packet.get("classification", {}).get("tier") != "full_team":
        raise OrchestrationError("runner binding is available only for full-team packets")
    _validate_implementer_receipt(implementer_receipt, packet, repo)
    if not HEX40.fullmatch(candidate_commit):
        raise OrchestrationError("candidate commit must be exact lowercase 40-hex")
    if implementer_receipt.get("candidate_commit") != candidate_commit:
        raise OrchestrationError("implementer receipt candidate mismatch")
    payload = {"schema_version": RUNNER_BINDING_SCHEMA, "owner": packet["owner"], "task_id": packet["task_id"], "packet_hash": packet["canonical_hash"], "implementer_receipt_hash": _payload_hash(implementer_receipt), "candidate_commit": candidate_commit, "runner_model": _lane_binding(load_registry(repo), "runner"), "runner_task_id": packet["subordinate_task_ids"]["runner"]}
    return {**payload, "canonical_hash": sha256_canonical(payload)}


def validate_receipts(packet: Mapping[str, Any], implementer_receipt: Mapping[str, Any] | None = None, runner_binding: Mapping[str, Any] | None = None, runner_receipt: Mapping[str, Any] | None = None, sol_disposition: Mapping[str, Any] | None = None, repo: str | Path | None = None) -> None:
    """Validate packet/receipt identity, lane models, and runner immutability."""

    validate_packet(packet, repo)
    tier = packet.get("classification", {}).get("tier")
    if tier not in {"orchestrator_only", "orchestrator_plus_implementer", "full_team"}:
        raise OrchestrationError("packet has an unknown risk tier")
    if tier == "orchestrator_only":
        if implementer_receipt is not None or runner_binding is not None or runner_receipt is not None:
            raise OrchestrationError("orchestrator-only packet cannot include execution lanes")
        if sol_disposition is not None:
            _validate_sol_disposition(sol_disposition, packet, repo)
        return
    if implementer_receipt is None:
        raise OrchestrationError("implementer receipt is required for this tier")
    _validate_implementer_receipt(implementer_receipt, packet, repo)
    if tier == "orchestrator_plus_implementer":
        if runner_binding is not None or runner_receipt is not None:
            raise OrchestrationError("orchestrator-plus-implementer packet cannot include runner artifacts")
        return
    if runner_binding is None or runner_receipt is None:
        raise OrchestrationError("full-team packet requires runner binding and receipt")
    if runner_binding is not None:
        binding_keys = {"schema_version", "owner", "task_id", "packet_hash", "implementer_receipt_hash", "candidate_commit", "runner_model", "runner_task_id", "canonical_hash"}
        if set(runner_binding) != binding_keys:
            raise OrchestrationError("runner binding has missing or forbidden fields")
        expected = {key: value for key, value in runner_binding.items() if key != "canonical_hash"}
        if runner_binding.get("schema_version") != RUNNER_BINDING_SCHEMA or runner_binding.get("canonical_hash") != sha256_canonical(expected):
            raise OrchestrationError("invalid runner binding")
        for field, value in (("owner", packet["owner"]), ("task_id", packet["task_id"]), ("packet_hash", packet["canonical_hash"])):
            if runner_binding.get(field) != value:
                raise OrchestrationError(f"runner binding {field} mismatch")
        if runner_binding.get("candidate_commit") != implementer_receipt.get("candidate_commit"):
            raise OrchestrationError("runner binding candidate mismatch")
        if runner_binding.get("implementer_receipt_hash") != _payload_hash(implementer_receipt):
            raise OrchestrationError("runner binding implementer receipt hash mismatch")
        if runner_binding.get("runner_model") != _lane_binding(load_registry(repo), "runner"):
            raise OrchestrationError("runner binding model mismatch")
        if runner_binding.get("runner_task_id") != packet["subordinate_task_ids"]["runner"]:
            raise OrchestrationError("runner binding task ID must match the packet-bound runner task")
    if runner_receipt is not None:
        if runner_binding is None:
            raise OrchestrationError("runner receipt requires runner binding")
        _validate_runner_receipt(runner_receipt, packet, runner_binding, repo)
        if runner_receipt.get("candidate_commit") != runner_binding.get("candidate_commit"):
            raise OrchestrationError("runner receipt candidate mismatch")
        actions = set(runner_receipt.get("actions", ()))
        if actions & RUNNER_WRITE_ACTIONS:
            raise OrchestrationError("runner receipt declares a forbidden write action")
        if runner_receipt.get("outcome") != "passed":
            raise InactiveOwnerError("runner lane outcome failed")


def build_subordinate_archive_manifest(
    packet: Mapping[str, Any],
    implementer_receipt: Mapping[str, Any] | None,
    runner_binding: Mapping[str, Any] | None,
    runner_receipt: Mapping[str, Any] | None,
    repo: str | Path | None = None,
) -> dict[str, Any] | None:
    """Build a transport-neutral request to archive completed lane tasks."""

    validate_receipts(packet, implementer_receipt, runner_binding, runner_receipt, repo=repo)
    tier = packet["classification"]["tier"]
    expected: dict[str, Mapping[str, Any]] = {}
    if tier in {"orchestrator_plus_implementer", "full_team"}:
        if implementer_receipt is None:
            raise OrchestrationError("successful implementer receipt is required for archival")
        expected["implementer"] = implementer_receipt
    if tier == "full_team":
        if runner_receipt is None:
            raise OrchestrationError("successful runner receipt is required for archival")
        expected["runner"] = runner_receipt
    if not expected:
        return None
    lanes = [
        {
            "lane": lane,
            "subordinate_task_id": packet["subordinate_task_ids"][lane],
            "receipt_hash": _payload_hash(expected[lane]),
            "action": "archive",
            "status": "ready_after_owner_receipt_capture",
        }
        for lane in ("implementer", "runner")
        if lane in expected
    ]
    payload = {
        "schema_version": ARCHIVE_MANIFEST_SCHEMA,
        "owner": packet["owner"],
        "task_id": packet["task_id"],
        "packet_hash": packet["canonical_hash"],
        "authority": "owner_orchestrator",
        "transport": "host_task_management_surface",
        "runner_binding_hash": runner_binding["canonical_hash"] if runner_binding else "",
        "lanes": lanes,
    }
    return {**payload, "canonical_hash": sha256_canonical(payload)}


def _build_orchestration_record(
    packet: Mapping[str, Any],
    implementer_receipt: Mapping[str, Any] | None,
    runner_binding: Mapping[str, Any] | None,
    runner_receipt: Mapping[str, Any] | None,
    sol_disposition: Mapping[str, Any] | None,
    archive_manifest: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Build the exact bounded record that anchors later closeout evidence."""

    payload = {
        "schema_version": RECORD_SCHEMA,
        "owner": packet["owner"],
        "task_id": packet["task_id"],
        "packet_hash": packet["canonical_hash"],
        "tier": packet["classification"]["tier"],
        "implementer_receipt_hash": _payload_hash(implementer_receipt) if implementer_receipt else "",
        "runner_binding_hash": runner_binding["canonical_hash"] if runner_binding else "",
        "runner_receipt_hash": _payload_hash(runner_receipt) if runner_receipt else "",
        "sol_disposition_hash": _payload_hash(sol_disposition) if sol_disposition else "",
        "archive_manifest_hash": archive_manifest["canonical_hash"] if archive_manifest else "",
    }
    return {**payload, "canonical_hash": sha256_canonical(payload)}


def record_bundle(packet: Mapping[str, Any], implementer_receipt: Mapping[str, Any] | None = None, runner_binding: Mapping[str, Any] | None = None, runner_receipt: Mapping[str, Any] | None = None, sol_disposition: Mapping[str, Any] | None = None, repo: str | Path | None = None) -> dict[str, Any]:
    """Write one content-addressed, no-overwrite owner receipt bundle."""

    root = repository_root(repo)
    validate_receipts(packet, implementer_receipt, runner_binding, runner_receipt, sol_disposition, root)
    if packet["classification"]["tier"] == "orchestrator_only" and sol_disposition is None:
        raise OrchestrationError("tier-one record requires an explicit Sol disposition")
    profile = load_active_owner_profile(packet["owner"], root)
    packet_hash = packet["canonical_hash"]
    directory = root / profile["continuity_receipts_root"] / packet["task_id"] / packet_hash
    task_root = directory.parent
    if task_root.exists() and (_path_exists(directory) or any(path.is_dir() and not path.name.startswith(".") for path in task_root.iterdir())):
        raise OrchestrationError(f"task receipt already exists and task IDs are unique: {packet['task_id']}")
    archive_manifest = build_subordinate_archive_manifest(packet, implementer_receipt, runner_binding, runner_receipt, root)
    record = _build_orchestration_record(packet, implementer_receipt, runner_binding, runner_receipt, sol_disposition, archive_manifest)
    temporary = root / "tmp" / "owner_scoped_orchestration_receipts" / f"{packet_hash}.tmp-{os.getpid()}"
    try:
        os.makedirs(_filesystem_path(task_root), exist_ok=True)
        os.makedirs(_filesystem_path(temporary), exist_ok=False)
        _exclusive_write(temporary / "packet.json", packet)
        if implementer_receipt:
            _exclusive_write(temporary / "implementer_receipt.json", implementer_receipt)
        if runner_binding:
            _exclusive_write(temporary / "runner_binding.json", runner_binding)
        if runner_receipt:
            _exclusive_write(temporary / "runner_receipt.json", runner_receipt)
        if sol_disposition:
            _exclusive_write(temporary / "sol_disposition.json", sol_disposition)
        if archive_manifest:
            _exclusive_write(temporary / "subordinate_archive_manifest.json", archive_manifest)
        _exclusive_write(temporary / "record.json", record)
        if _path_exists(directory):
            raise OrchestrationError("no-overwrite receipt already exists")
        os.replace(_filesystem_path(temporary), _filesystem_path(directory))
    except Exception:
        if _path_exists(temporary):
            shutil.rmtree(_filesystem_path(temporary))
        raise
    return record


def validate_archive_manifest(
    manifest: Mapping[str, Any],
    packet: Mapping[str, Any],
    implementer_receipt: Mapping[str, Any] | None,
    runner_binding: Mapping[str, Any] | None,
    runner_receipt: Mapping[str, Any] | None,
    repo: str | Path | None = None,
) -> None:
    """Require an archive manifest to exactly match the recorded lanes."""

    expected = build_subordinate_archive_manifest(packet, implementer_receipt, runner_binding, runner_receipt, repo)
    if expected is None:
        raise OrchestrationError("orchestrator-only packets have no subordinate archive manifest")
    if dict(manifest) != expected:
        raise OrchestrationError("archive manifest does not exactly match the validated recorded lanes")


def validate_archive_acknowledgment(
    acknowledgment: Mapping[str, Any],
    manifest: Mapping[str, Any],
) -> None:
    """Validate Sol's host-side archival acknowledgment."""

    required = {
        "schema_version", "owner", "task_id", "packet_hash",
        "archive_manifest_hash", "acknowledged_by", "correction_pending",
        "lane_dispositions", "canonical_hash",
    }
    if set(acknowledgment) != required:
        raise OrchestrationError("archive acknowledgment has missing or forbidden fields")
    unsigned = {key: value for key, value in acknowledgment.items() if key != "canonical_hash"}
    if acknowledgment.get("schema_version") != ARCHIVE_ACKNOWLEDGMENT_SCHEMA or acknowledgment.get("canonical_hash") != sha256_canonical(unsigned):
        raise OrchestrationError("archive acknowledgment hash or schema is invalid")
    for field in ("owner", "task_id", "packet_hash"):
        if acknowledgment.get(field) != manifest.get(field):
            raise OrchestrationError(f"archive acknowledgment {field} mismatch")
    if acknowledgment.get("archive_manifest_hash") != manifest.get("canonical_hash"):
        raise OrchestrationError("archive acknowledgment manifest hash mismatch")
    if acknowledgment.get("acknowledged_by") != "owner_orchestrator" or acknowledgment.get("correction_pending") is not False:
        raise OrchestrationError("archive acknowledgment must be Sol-owned and confirm no correction is pending")
    actual = acknowledgment.get("lane_dispositions")
    expected_lanes = manifest.get("lanes")
    if not isinstance(actual, list) or not isinstance(expected_lanes, list) or len(actual) != len(expected_lanes):
        raise OrchestrationError("archive acknowledgment must disposition every requested lane")
    for supplied, requested in zip(actual, expected_lanes, strict=True):
        if not isinstance(supplied, dict) or set(supplied) != {"lane", "subordinate_task_id", "disposition", "supersession_ref"}:
            raise OrchestrationError("archive acknowledgment lane disposition has an invalid shape")
        if supplied.get("lane") != requested.get("lane") or supplied.get("subordinate_task_id") != requested.get("subordinate_task_id"):
            raise OrchestrationError("archive acknowledgment lane task identity mismatch")
        disposition = supplied.get("disposition")
        supersession = supplied.get("supersession_ref")
        if disposition not in {"archived", "superseded"}:
            raise OrchestrationError("archive acknowledgment disposition must be archived or superseded")
        if disposition == "archived" and supersession != "":
            raise OrchestrationError("archived lane must not carry a supersession reference")
        if disposition == "superseded":
            _require_safe_text(supersession, "archive acknowledgment supersession_ref")


def validate_recorded_bundle(
    record: Mapping[str, Any],
    packet: Mapping[str, Any],
    implementer_receipt: Mapping[str, Any] | None,
    runner_binding: Mapping[str, Any] | None,
    runner_receipt: Mapping[str, Any] | None,
    archive_manifest: Mapping[str, Any],
) -> None:
    """Require the recorded bundle to match every finalized lane hash."""

    expected = _build_orchestration_record(packet, implementer_receipt, runner_binding, runner_receipt, None, archive_manifest)
    if dict(record) != expected:
        raise OrchestrationError("recorded receipt bundle does not match the finalized lanes")


def validate_closeout_delivery_evidence(
    evidence: Mapping[str, Any],
    packet: Mapping[str, Any],
    implementer_receipt: Mapping[str, Any] | None,
    runner_binding: Mapping[str, Any] | None,
    runner_receipt: Mapping[str, Any] | None,
    record: Mapping[str, Any],
    repo: str | Path | None = None,
) -> None:
    """Validate Sol's terminal Git, synchronization, and worktree evidence."""

    required = {
        "schema_version", "owner", "task_id", "packet_hash", "branch",
        "candidate_commit", "receipt_record_hash", "captured_receipt_hashes",
        "terminal_reconciliation", "primary_branch_sync", "worktree_removal",
        "acknowledged_by", "canonical_hash",
    }
    if set(evidence) != required:
        raise OrchestrationError("closeout delivery evidence has missing or forbidden fields")
    unsigned = {key: value for key, value in evidence.items() if key != "canonical_hash"}
    if evidence.get("schema_version") != CLOSEOUT_DELIVERY_EVIDENCE_SCHEMA or evidence.get("canonical_hash") != sha256_canonical(unsigned):
        raise OrchestrationError("closeout delivery evidence hash or schema is invalid")
    for field in ("owner", "task_id", "packet_hash", "branch"):
        expected = packet["canonical_hash"] if field == "packet_hash" else packet[field]
        if evidence.get(field) != expected:
            raise OrchestrationError(f"closeout delivery evidence {field} mismatch")
    candidate = implementer_receipt.get("candidate_commit") if implementer_receipt else ""
    if evidence.get("candidate_commit") != candidate:
        raise OrchestrationError("closeout delivery evidence candidate mismatch")
    if evidence.get("receipt_record_hash") != record.get("canonical_hash"):
        raise OrchestrationError("closeout delivery evidence record hash mismatch")
    expected_receipts = {
        "implementer": _payload_hash(implementer_receipt) if implementer_receipt else "",
        "runner_binding": runner_binding.get("canonical_hash", "") if runner_binding else "",
        "runner": _payload_hash(runner_receipt) if runner_receipt else "",
    }
    if evidence.get("captured_receipt_hashes") != expected_receipts:
        raise OrchestrationError("closeout delivery evidence receipt hashes mismatch")
    if evidence.get("acknowledged_by") != "owner_orchestrator":
        raise OrchestrationError("closeout delivery evidence must be Sol-owned")
    registry = load_registry(repo)
    canonical_target = f"{registry['git']['canonical_remote']}/{registry['git']['canonical_branch']}"
    reconciliation = evidence.get("terminal_reconciliation")
    if not isinstance(reconciliation, dict) or set(reconciliation) != {"target", "disposition", "evidence_ref"} or reconciliation.get("target") != canonical_target or reconciliation.get("disposition") not in {"landed", "superseded"}:
        raise OrchestrationError("closeout requires terminal branch reconciliation")
    _require_safe_text(reconciliation.get("evidence_ref"), "terminal reconciliation evidence_ref")
    primary_sync = evidence.get("primary_branch_sync")
    if not isinstance(primary_sync, dict) or set(primary_sync) != {"verified", "evidence_ref"} or primary_sync.get("verified") is not True:
        raise OrchestrationError("closeout requires verified primary-branch synchronization")
    _require_safe_text(primary_sync.get("evidence_ref"), "primary branch sync evidence_ref")
    worktree = evidence.get("worktree_removal")
    if not isinstance(worktree, dict) or set(worktree) != {"worktree", "removed", "evidence_ref"} or worktree.get("worktree") != packet["worktree"] or worktree.get("removed") is not True:
        raise OrchestrationError("closeout requires verified packet worktree removal")
    _require_safe_text(worktree.get("evidence_ref"), "worktree removal evidence_ref")


def finalize_closeout(
    packet: Mapping[str, Any],
    implementer_receipt: Mapping[str, Any] | None,
    runner_binding: Mapping[str, Any] | None,
    runner_receipt: Mapping[str, Any] | None,
    archive_manifest: Mapping[str, Any],
    archive_acknowledgment: Mapping[str, Any],
    record: Mapping[str, Any],
    delivery_evidence: Mapping[str, Any],
    repo: str | Path | None = None,
) -> dict[str, Any]:
    """Publish immutable finalization after archival and delivery closeout."""

    root = repository_root(repo)
    validate_archive_manifest(archive_manifest, packet, implementer_receipt, runner_binding, runner_receipt, root)
    validate_archive_acknowledgment(archive_acknowledgment, archive_manifest)
    validate_recorded_bundle(record, packet, implementer_receipt, runner_binding, runner_receipt, archive_manifest)
    validate_closeout_delivery_evidence(delivery_evidence, packet, implementer_receipt, runner_binding, runner_receipt, record, root)
    profile = load_active_owner_profile(packet["owner"], root)
    lane_dispositions = [
        {"lane": item["lane"], "subordinate_task_id": item["subordinate_task_id"], "disposition": item["disposition"]}
        for item in archive_acknowledgment["lane_dispositions"]
    ]
    payload = {
        "schema_version": CLOSEOUT_FINALIZATION_SCHEMA,
        "owner": packet["owner"],
        "task_id": packet["task_id"],
        "packet_hash": packet["canonical_hash"],
        "receipt_record_hash": record["canonical_hash"],
        "captured_receipt_hashes": delivery_evidence["captured_receipt_hashes"],
        "archive_manifest_hash": archive_manifest["canonical_hash"],
        "archive_acknowledgment_hash": _payload_hash(archive_acknowledgment),
        "subordinate_task_dispositions": lane_dispositions,
        "terminal_reconciliation": delivery_evidence["terminal_reconciliation"],
        "primary_branch_sync": delivery_evidence["primary_branch_sync"],
        "worktree_removal": delivery_evidence["worktree_removal"],
        "delivery_evidence_hash": delivery_evidence["canonical_hash"],
        "outcome": "closed",
    }
    finalization = {**payload, "canonical_hash": sha256_canonical(payload)}
    directory = root / profile["continuity_receipts_root"] / packet["task_id"] / "finalizations" / finalization["canonical_hash"]
    temporary = root / "tmp" / "owner_scoped_orchestration_finalizations" / f"{finalization['canonical_hash']}.tmp-{os.getpid()}"
    try:
        os.makedirs(_filesystem_path(temporary), exist_ok=False)
        _exclusive_write(temporary / "archive_acknowledgment.json", archive_acknowledgment)
        _exclusive_write(temporary / "closeout_delivery_evidence.json", delivery_evidence)
        _exclusive_write(temporary / "closeout_finalization.json", finalization)
        if _path_exists(directory):
            raise OrchestrationError("no-overwrite closeout finalization already exists")
        os.makedirs(_filesystem_path(directory.parent), exist_ok=True)
        os.replace(_filesystem_path(temporary), _filesystem_path(directory))
    except Exception:
        if _path_exists(temporary):
            shutil.rmtree(_filesystem_path(temporary))
        raise
    return finalization


def _lane_binding(registry: Mapping[str, Any], lane: str) -> dict[str, str]:
    binding = registry["model_binding"][lane]
    return {"model": binding["model"], "reasoning_effort": binding["reasoning_effort"]}


def _validate_lane_identity(receipt: Mapping[str, Any], schema: str, lane: str, packet: Mapping[str, Any], repo: str | Path | None) -> None:
    if receipt.get("schema_version") != schema:
        raise OrchestrationError(f"invalid {lane} receipt schema")
    for field, value in (("owner", packet["owner"]), ("task_id", packet["task_id"]), ("packet_hash", packet["canonical_hash"])):
        if receipt.get(field) != value:
            raise OrchestrationError(f"{lane} receipt {field} mismatch")
    if receipt.get("model") != _lane_binding(load_registry(repo), lane):
        raise OrchestrationError(f"{lane} receipt model binding mismatch")
    if receipt.get("outcome") != "passed":
        raise InactiveOwnerError(f"{lane} lane outcome failed")


def _validate_implementer_receipt(receipt: Mapping[str, Any], packet: Mapping[str, Any], repo: str | Path | None) -> None:
    """Validate the exact Terra receipt shape and bounded candidate evidence."""

    _require_exact_keys(receipt, IMPLEMENTER_KEYS, "implementer receipt")
    _validate_lane_identity(receipt, IMPLEMENTER_RECEIPT_SCHEMA, "implementer", packet, repo)
    if not HEX40.fullmatch(str(receipt.get("candidate_commit", ""))):
        raise OrchestrationError("implementer candidate commit must be exact lowercase 40-hex")
    changed = _safe_paths(receipt.get("changed_paths", ()), "changed path")
    if not changed or any(not _path_is_within(path, packet["allowed_paths"]) for path in changed):
        raise OrchestrationError("implementer changed path is outside packet allowed scope")
    if any(_path_is_within(path, packet["prohibited_paths"]) for path in changed):
        raise OrchestrationError("implementer changed path is prohibited")
    actions = _string_list(receipt.get("actions"), "implementer actions")
    if set(actions) & IMPLEMENTER_FORBIDDEN_ACTIONS:
        raise OrchestrationError("implementer receipt declares a forbidden Git action")
    _validate_checks(receipt.get("checks"), packet["focused_checks"], "implementer")
    _validate_safe_diagnostics(receipt.get("residual_issues"), "implementer residual_issues")


def _validate_runner_receipt(receipt: Mapping[str, Any], packet: Mapping[str, Any], binding: Mapping[str, Any], repo: str | Path | None) -> None:
    """Validate the exact Luna receipt shape and independently pinned binding."""

    _require_exact_keys(receipt, RUNNER_KEYS, "runner receipt")
    _validate_lane_identity(receipt, RUNNER_RECEIPT_SCHEMA, "runner", packet, repo)
    if receipt.get("runner_binding_hash") != binding.get("canonical_hash"):
        raise OrchestrationError("runner receipt binding hash mismatch")
    if receipt.get("candidate_commit") != binding.get("candidate_commit"):
        raise OrchestrationError("runner receipt candidate mismatch")
    actions = _string_list(receipt.get("actions"), "runner actions")
    if set(actions) & RUNNER_WRITE_ACTIONS:
        raise OrchestrationError("runner receipt declares a forbidden write action")
    _validate_checks(receipt.get("checks"), packet["broad_checks"], "runner")
    _validate_runner_environment(receipt.get("environment_preflight"))
    _validate_runner_git_status(receipt.get("git_status"))
    _validate_reconciler_evidence(receipt.get("reconciler_evidence"), binding["candidate_commit"])
    _validate_safe_diagnostics(receipt.get("diagnostics"), "runner diagnostics")
    _validate_safe_diagnostics(receipt.get("residual_issues"), "runner residual_issues")


def _validate_sol_disposition(receipt: Mapping[str, Any], packet: Mapping[str, Any], repo: str | Path | None) -> None:
    """Validate the explicit Sol-only disposition optionally recorded for tier one."""

    _require_exact_keys(receipt, SOL_KEYS, "Sol disposition")
    _validate_lane_identity(receipt, SOL_DISPOSITION_SCHEMA, "owner_orchestrator", packet, repo)
    if not isinstance(receipt.get("disposition"), str) or not receipt["disposition"]:
        raise OrchestrationError("Sol disposition is required")
    _string_list(receipt.get("residual_issues"), "Sol residual_issues")


def _validate_runner_environment(value: Any) -> None:
    """Require bounded runner preflight evidence for the pinned candidate."""

    expected = {"candidate_commit_verified", "model_binding_verified", "initial_worktree_clean"}
    if not isinstance(value, dict) or set(value) != expected or any(item is not True for item in value.values()):
        raise OrchestrationError("runner environment_preflight must prove candidate, model, and initial cleanliness")


def _validate_runner_git_status(value: Any) -> None:
    """Require the runner to preserve a clean initial and final worktree."""

    if not isinstance(value, dict) or value != {"initial": "clean", "final": "clean"}:
        raise OrchestrationError("runner git_status must record clean initial and final states")


def _validate_reconciler_evidence(value: Any, candidate_commit: str) -> None:
    """Require bounded pre-publication reconciler evidence for the candidate."""

    expected = {"target": "origin/master", "candidate_commit": candidate_commit, "state": "pre_publication_unlanded"}
    if not isinstance(value, dict) or value != expected:
        raise OrchestrationError("runner reconciler_evidence does not match the pinned candidate")


def _require_exact_keys(value: Mapping[str, Any], expected: frozenset[str], label: str) -> None:
    """Reject missing and extraneous receipt fields, including unsafe payloads."""

    actual = frozenset(value)
    if actual != expected:
        raise OrchestrationError(f"{label} has missing or forbidden fields")


def _validate_checks(value: Any, expected_commands: Iterable[str], lane: str) -> None:
    """Require each packet check once and only once with a passed outcome."""

    if not isinstance(value, list):
        raise OrchestrationError(f"{lane} checks must be a list")
    commands: list[str] = []
    for item in value:
        if not isinstance(item, dict) or set(item) != {"command", "outcome"} or not isinstance(item["command"], str):
            raise OrchestrationError(f"{lane} check has an invalid shape")
        if item["outcome"] != "passed":
            raise InactiveOwnerError(f"{lane} check failed")
        commands.append(item["command"])
    expected = list(expected_commands)
    if len(commands) != len(set(commands)) or sorted(commands) != sorted(expected):
        raise OrchestrationError(f"{lane} checks must contain each packet check exactly once")


def _string_list(value: Any, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise OrchestrationError(f"{label} must be a string list")
    return tuple(value)


def _is_safe_task_id(value: Any) -> bool:
    """Return whether a task identifier is one conservative path component."""

    return (
        isinstance(value, str)
        and len(value) <= MAX_TASK_ID_LENGTH
        and bool(TASK_ID_PATTERN.fullmatch(value))
    )


def _is_opaque_task_id(value: Any) -> bool:
    """Return whether a host task ID is bounded and safe to persist."""

    return (
        isinstance(value, str)
        and len(value) <= MAX_SUBORDINATE_TASK_ID_LENGTH
        and bool(OPAQUE_TASK_ID_PATTERN.fullmatch(value))
    )


def _validate_subordinate_task_ids(
    value: Mapping[str, str] | None,
    tier: str,
) -> dict[str, str]:
    """Require exactly the packet-bound subordinate tasks needed by the tier."""

    expected = {
        "orchestrator_only": set(),
        "orchestrator_plus_implementer": {"implementer"},
        "full_team": {"implementer", "runner"},
    }.get(tier)
    if expected is None:
        raise OrchestrationError("unknown risk tier for subordinate task binding")
    supplied = dict(value or {})
    if set(supplied) != expected:
        raise OrchestrationError("packet subordinate task IDs do not match the selected tier")
    if any(not _is_opaque_task_id(task_id) for task_id in supplied.values()):
        raise OrchestrationError("subordinate task ID must be an opaque safe identifier")
    if len(set(supplied.values())) != len(supplied):
        raise OrchestrationError("subordinate task IDs must be unique across lanes")
    return supplied


def _is_safe_branch_prefix(value: Any) -> bool:
    """Return whether a registry branch prefix is slash-terminated safe segments."""

    if not isinstance(value, str) or not value.endswith("/") or value.startswith("/"):
        return False
    segments = value[:-1].split("/")
    return bool(segments) and all(BRANCH_SEGMENT_PATTERN.fullmatch(segment) for segment in segments)


def _is_safe_branch_for_prefix(branch: Any, prefix: str) -> bool:
    """Return whether a branch is one safe nonempty suffix below its owner prefix."""

    if not isinstance(branch, str) or not _is_safe_branch_prefix(prefix) or not branch.startswith(prefix):
        return False
    suffix = branch[len(prefix):]
    if not suffix or suffix.startswith("/") or suffix.endswith("/") or ".." in suffix or "\\" in suffix:
        return False
    return all(BRANCH_SEGMENT_PATTERN.fullmatch(segment) for segment in suffix.split("/"))


def _require_safe_text(value: Any, label: str) -> str:
    """Return a nonempty safe diagnostic-compatible public text field."""

    if not isinstance(value, str) or not value.strip():
        raise OrchestrationError(f"{label} is required")
    try:
        validate_safe_diagnostic(label, value)
    except ValueError as exc:
        raise OrchestrationError(str(exc)) from exc
    return value


def _require_safe_string_list(value: Any, label: str) -> tuple[str, ...]:
    """Return a nonempty list whose public strings pass safety validation."""

    values = _string_list(value, label)
    if not values or any(not item.strip() for item in values):
        raise OrchestrationError(f"{label} must be a non-empty string list")
    for item in values:
        _require_safe_text(item, label)
    return values


def _validate_safe_diagnostics(value: Any, label: str) -> tuple[str, ...]:
    """Validate nonempty receipt diagnostics through the shared safety port."""

    diagnostics = _string_list(value, label)
    for item in diagnostics:
        if item:
            try:
                validate_safe_diagnostic(label, item)
            except ValueError as exc:
                raise OrchestrationError(str(exc)) from exc
    return diagnostics


def _payload_hash(value: Mapping[str, Any]) -> str:
    return sha256_canonical({key: item for key, item in value.items() if key != "canonical_hash"})


def _safe_paths(values: Iterable[Any], label: str) -> tuple[str, ...]:
    if not isinstance(values, list):
        raise OrchestrationError(f"{label}s must be a list")
    normalized: list[str] = []
    for value in values:
        normalized_value = value.replace("\\", "/") if isinstance(value, str) else value
        parts = Path(normalized_value).parts if isinstance(normalized_value, str) else ()
        if not isinstance(value, str) or not value or Path(normalized_value).is_absolute() or ".." in parts or ".git" in parts:
            raise OrchestrationError(f"unsafe {label}: {value!r}")
        normalized.append(normalized_value)
    return tuple(normalized)


def _safe_worktree(value: str) -> str:
    """Return a normalized worktree path constrained to `.worktrees/<name>`."""

    if not isinstance(value, str) or not value:
        raise OrchestrationError("worktree is required")
    normalized = value.replace("\\", "/")
    parts = Path(normalized).parts
    if Path(normalized).is_absolute() or ".." in parts or ".git" in parts or len(parts) < 2 or parts[0] != ".worktrees":
        raise OrchestrationError("worktree must be a relative path under .worktrees/")
    return normalized


def _repo_relative_path(root: Path, value: Any, label: str) -> Path:
    """Resolve one safe repository-relative profile reference without writing."""

    if not isinstance(value, str) or not value:
        raise OrchestrationError(f"{label} must be a non-empty relative path")
    normalized = value.replace("\\", "/")
    candidate = Path(normalized)
    if candidate.is_absolute() or ".." in candidate.parts or ".git" in candidate.parts:
        raise OrchestrationError(f"unsafe {label}")
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise OrchestrationError(f"unsafe {label}") from exc
    return resolved


def _path_scopes_overlap(left: Iterable[str], right: Iterable[str]) -> bool:
    """Return whether any two declared path scopes contain one another."""

    return any(_path_prefix(a, b) or _path_prefix(b, a) for a in left for b in right)


def _path_is_within(path: str, scopes: Iterable[str]) -> bool:
    """Return whether a normalized path is equal to or below one packet scope."""

    return any(_path_prefix(path, scope) for scope in scopes)


def _path_prefix(path: str, scope: str) -> bool:
    return path == scope or path.startswith(scope.rstrip("/") + "/")


def _path_exists(path: Path) -> bool:
    """Return whether a path exists through the shared platform boundary."""

    return os.path.exists(_filesystem_path(path))


def _filesystem_path(path: Path) -> str:
    """Return an absolute path with extended Windows-path support."""

    resolved = str(path.resolve())
    if os.name != "nt" or resolved.startswith("\\\\?\\"):
        return resolved
    if resolved.startswith("\\\\"):
        return f"\\\\?\\UNC\\{resolved[2:]}"
    return f"\\\\?\\{resolved}"


def _branch_prefixes_overlap(left: str, right: str) -> bool:
    """Return whether two branch-prefix namespaces are nested or identical."""

    return left == right or left.startswith(right) or right.startswith(left)


def _path_risk_triggers(paths: Iterable[str]) -> list[str]:
    """Return conservative full-team triggers derived from declared paths."""

    triggers: list[str] = []
    canonical_names = {
        "core thesis.md",
        "architecture.md",
        "spec.md",
        "implementation roadmap.md",
    }
    for path in paths:
        lower = path.lower()
        name = Path(path).name.lower()
        if lower == "agents.md":
            triggers.append("canonical_doctrine")
        if lower.startswith("src/"):
            triggers.append("runtime")
        if lower.startswith("project_obsidian_vault/00_canonical/") or name in canonical_names:
            triggers.append("canonical_doctrine")
        if any(token in lower for token in ("security", "privacy")):
            triggers.append("security_privacy")
        if any(token in lower for token in ("kernel", "rkhs", "spectral", "/math/")):
            triggers.append("math")
        if any(token in lower for token in ("adapter", "mcp", "migration")):
            triggers.append("external_adapter" if "adapter" in lower or "mcp" in lower else "migration")
        if any(token in lower for token in ("legal-release", "legal_release")):
            triggers.append("legal_release")
        if any(token in lower for token in ("/ui/", "frontend", "user-facing")):
            triggers.append("user_facing")
    return triggers


def _all_a2a_or_continuity_markdown(paths: Iterable[str]) -> bool:
    """Return whether every path is an A2A record or owner-continuity note."""

    prefix = "project_obsidian_vault/"
    return all(
        path.lower().endswith(".md")
        and (
            path.lower().startswith(prefix + "40_coordination/")
            or "/continuity/" in path.lower()
        )
        for path in paths
    )


def _is_explicit_low_risk_documentation(description: str) -> bool:
    """Return whether the orchestrator explicitly labelled docs as low risk."""

    text = description.lower()
    return any(phrase in text for phrase in ("low-risk documentation", "low risk documentation", "low-risk docs", "low risk docs"))


def _all_safe_noncanonical_markdown(paths: Iterable[str]) -> bool:
    """Return whether all paths are Markdown outside canonical Core doctrine."""

    canonical_prefix = "project_obsidian_vault/00_canonical/"
    return all(path.lower().endswith(".md") and not path.lower().startswith(canonical_prefix) and path.lower() != "agents.md" for path in paths)


def _contains_term(text: str, term: str) -> bool:
    """Match a configured risk term on word boundaries, not as a substring."""

    return re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", text) is not None


def _exclusive_write(path: Path, payload: Mapping[str, Any]) -> None:
    os.makedirs(_filesystem_path(path.parent), exist_ok=True)
    try:
        with open(_filesystem_path(path), "x", encoding="utf-8", newline="\n") as handle:
            handle.write(canonical_json(payload) + "\n")
    except FileExistsError as exc:
        raise OrchestrationError(f"no-overwrite receipt already exists: {path}") from exc


def _load_json(path: str | Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OrchestrationError(f"cannot load JSON: {path}") from exc
    if not isinstance(value, dict):
        raise OrchestrationError(f"JSON object required: {path}")
    return value


def _tmp_output(root: Path, output: str | Path) -> Path:
    path = Path(output)
    resolved = (root / path).resolve() if not path.is_absolute() else path.resolve()
    try:
        resolved.relative_to((root / "tmp").resolve())
    except ValueError as exc:
        raise OrchestrationError("write output must remain under repository tmp") from exc
    return resolved


def _write_tmp(root: Path, output: str | Path, payload: Mapping[str, Any]) -> Path:
    path = _tmp_output(root, output)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(canonical_json(payload) + "\n")
    except FileExistsError as exc:
        raise OrchestrationError(f"no-overwrite tmp output already exists: {path}") from exc
    return path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=str(REPOSITORY_ROOT))
    commands = parser.add_subparsers(dest="command", required=True)
    owner = commands.add_parser("check-owner"); owner.add_argument("--owner", required=True); owner.add_argument("--active", action="store_true")
    classify = commands.add_parser("classify"); classify.add_argument("--owner", required=True); classify.add_argument("--description", required=True); classify.add_argument("--path", action="append", default=[]); classify.add_argument("--requested-tier")
    prepare = commands.add_parser("prepare")
    for argument in ("owner", "task-id", "approval-ref", "baseline", "branch", "worktree", "description", "output"):
        prepare.add_argument(f"--{argument}", required=True)
    for argument in ("allowed-path", "prohibited-path", "evidence-ref", "focused-check", "broad-check"):
        prepare.add_argument(f"--{argument}", action="append", default=[])
    prepare.add_argument("--requested-tier")
    prepare.add_argument("--implementer-task-id")
    prepare.add_argument("--runner-task-id")
    bind = commands.add_parser("bind-runner"); bind.add_argument("--packet", required=True); bind.add_argument("--implementer-receipt", required=True); bind.add_argument("--candidate-commit", required=True); bind.add_argument("--output", required=True)
    validate = commands.add_parser("validate"); validate.add_argument("--packet", required=True); validate.add_argument("--implementer-receipt"); validate.add_argument("--runner-binding"); validate.add_argument("--runner-receipt"); validate.add_argument("--sol-disposition")
    record = commands.add_parser("record"); record.add_argument("--packet", required=True); record.add_argument("--implementer-receipt"); record.add_argument("--runner-binding"); record.add_argument("--runner-receipt"); record.add_argument("--sol-disposition")
    finalize = commands.add_parser("finalize-closeout"); finalize.add_argument("--packet", required=True); finalize.add_argument("--implementer-receipt"); finalize.add_argument("--runner-binding"); finalize.add_argument("--runner-receipt"); finalize.add_argument("--archive-manifest", required=True); finalize.add_argument("--archive-acknowledgment", required=True); finalize.add_argument("--record", required=True); finalize.add_argument("--delivery-evidence", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the command-line interface with 0/2/3 exit semantics."""

    args = _parser().parse_args(argv)
    root = repository_root(args.repo)
    try:
        if args.command == "check-owner":
            config = owner_config(args.owner, root, active=args.active)
            profile = load_owner_profile(args.owner, root, require_active=args.active)
            result = {**config, "profile_schema_version": profile["schema_version"]}
        elif args.command == "classify":
            owner_config(args.owner, root, active=True); result = classify_task(args.description, args.path)
            if args.requested_tier:
                tiers = ("orchestrator_only", "orchestrator_plus_implementer", "full_team")
                if args.requested_tier not in tiers: raise OrchestrationError("unknown requested tier")
                result["tier"] = max((result["tier"], args.requested_tier), key=tiers.index)
        elif args.command == "prepare":
            subordinate_task_ids = {lane: value for lane, value in (("implementer", args.implementer_task_id), ("runner", args.runner_task_id)) if value}
            result = make_packet(owner=args.owner, task_id=args.task_id, approval_ref=args.approval_ref, baseline=args.baseline, branch=args.branch, worktree=args.worktree, allowed_paths=args.allowed_path, prohibited_paths=args.prohibited_path, evidence_refs=args.evidence_ref, focused_checks=args.focused_check, broad_checks=args.broad_check, description=args.description, requested_tier=args.requested_tier, subordinate_task_ids=subordinate_task_ids, repo=root); _write_tmp(root, args.output, result)
        elif args.command == "bind-runner":
            result = bind_runner(_load_json(args.packet), _load_json(args.implementer_receipt), args.candidate_commit, root); _write_tmp(root, args.output, result)
        elif args.command == "validate":
            validate_receipts(_load_json(args.packet), _load_json(args.implementer_receipt) if args.implementer_receipt else None, _load_json(args.runner_binding) if args.runner_binding else None, _load_json(args.runner_receipt) if args.runner_receipt else None, _load_json(args.sol_disposition) if args.sol_disposition else None, root); result = {"outcome": "passed"}
        elif args.command == "record":
            result = record_bundle(_load_json(args.packet), _load_json(args.implementer_receipt) if args.implementer_receipt else None, _load_json(args.runner_binding) if args.runner_binding else None, _load_json(args.runner_receipt) if args.runner_receipt else None, _load_json(args.sol_disposition) if args.sol_disposition else None, root)
        else:
            result = finalize_closeout(_load_json(args.packet), _load_json(args.implementer_receipt) if args.implementer_receipt else None, _load_json(args.runner_binding) if args.runner_binding else None, _load_json(args.runner_receipt) if args.runner_receipt else None, _load_json(args.archive_manifest), _load_json(args.archive_acknowledgment), _load_json(args.record), _load_json(args.delivery_evidence), root)
        print(canonical_json(result)); return 0
    except InactiveOwnerError as exc:
        print(str(exc), file=sys.stderr); return 2
    except OrchestrationError as exc:
        print(str(exc), file=sys.stderr); return 3


if __name__ == "__main__":
    raise SystemExit(main())
