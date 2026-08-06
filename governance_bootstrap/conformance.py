"""Repository architecture conformance checks."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any

from tools.capability_status import CapabilityStatusError, validate_registry
from tools.source_doc_audit import find_missing_docstrings
from tools.tool_parity import validate_manifest
from tools.vault_maintainer import collect_diagnostics, load_registry


def _load(root: Path, relative: str) -> Any:
    return json.loads((root / relative).read_text(encoding="utf-8"))


def _require_artifact(failures: list[str], root: Path, name: str, version: str) -> None:
    path = root / "third_party" / f"{name}-{version}.json"
    if not path.is_file():
        failures.append(f"third-party: missing exact artifact record {path.name}")
        return
    record = json.loads(path.read_text(encoding="utf-8"))
    required = {"package", "version", "artifact", "sha256", "provenance", "license", "posture"}
    if required - record.keys() or record.get("package") != name or record.get("version") != version:
        failures.append(f"third-party: incomplete exact artifact record {path.name}")
    if len(record.get("sha256", "")) != 64 or not record.get("provenance", "").startswith("https://"):
        failures.append(f"third-party: invalid hash or provenance in {path.name}")


def validate_documentation_system(root: Path) -> list[str]:
    """Return violations of the governed instruction and Markdown contract."""
    manifest = _load(root, "configs/documentation_system_v1.json")
    failures: list[str] = []
    if manifest.get("schema_version") != "governed_documentation_system_v1":
        failures.append("invalid documentation-system schema")
        return failures
    allowed_classes = {"operational_equivalent", "generic_adaptation"}
    seen: set[str] = set()
    for surface in manifest.get("surfaces", []):
        relative = surface.get("path", "")
        if not relative or relative in seen:
            failures.append(f"invalid or duplicate documentation surface {relative!r}")
            continue
        seen.add(relative)
        if surface.get("classification") not in allowed_classes:
            failures.append(f"invalid documentation classification for {relative}")
        path = root / relative
        if not path.is_file():
            failures.append(f"missing documentation surface {relative}")
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        minimum = surface.get("minimum_lines")
        if not isinstance(minimum, int) or minimum < 1 or len(lines) < minimum:
            failures.append(
                f"documentation surface {relative} has {len(lines)} lines; "
                f"requires at least {minimum}"
            )
        headings = {line.strip() for line in lines if line.lstrip().startswith("#")}
        for heading in surface.get("required_headings", []):
            if heading not in headings:
                failures.append(f"documentation surface {relative} is missing heading {heading!r}")
    for relative in manifest.get("required_core_continuity_protocols", []):
        if not (root / relative).is_file():
            failures.append(f"missing Core continuity protocol {relative}")
    required_dispositions = {
        "shared_repository_governance",
        "core_owner_workflow",
        "owner_specific_instruction_sets",
        "owner_specific_continuity_packs",
        "product_runtime_architecture",
        "domain_parameter_manuals",
        "product_specific_tooling",
    }
    if set(manifest.get("adaptation_dispositions", {})) != required_dispositions:
        failures.append("documentation adaptation dispositions are incomplete")
    return failures


def check_repository(root: Path) -> list[str]:
    """Return deterministic violations of the bootstrap architecture."""
    config = _load(root, "configs/conformance_v1.json")
    failures: list[str] = []
    for plane, paths in config["required_planes"].items():
        for item in paths:
            if not (root / item).is_file():
                failures.append(f"{plane}: missing {item}")
    failures.extend(
        f"documentation: {item}" for item in validate_documentation_system(root)
    )
    old_canonical = root / "canonical"
    if old_canonical.exists() and any(old_canonical.rglob("*")):
        failures.append("canonical: narrative canonical files must exist only in the vault")
    registry = load_registry(root / "configs/vault_maintenance_registry_v1.json")
    vault_root = registry.vault_root
    canonical_paths = ("00_Canonical/Core Thesis.md", "00_Canonical/ARCHITECTURE.md", "00_Canonical/SPEC.md", "00_Canonical/ROADMAP.md")
    if not vault_root.is_dir() or any(not (vault_root / path).is_file() for path in canonical_paths):
        failures.append("canonical: vault canonical single source is incomplete")
    vault_diagnostics = collect_diagnostics(registry, registry.scopes, require_navigation=True)
    failures.extend(
        f"vault: {item.code}: {item.path}: {item.message}"
        for item in vault_diagnostics
        if item.severity == "error"
    )
    source_findings = find_missing_docstrings((root / "governance_bootstrap", root / "tools"))
    if source_findings:
        failures.extend(f"source-doc: {finding.format()}" for finding in source_findings)
    capability = _load(root, "configs/capability_registry_v1.json")
    try:
        validate_registry(capability, root=root)
    except CapabilityStatusError as error:
        failures.append(f"capability: {error}")
    research_policy = config["research_first"]
    research = root / research_policy["research_dir"]
    records = research / "records"
    if not research.is_dir() or not records.is_dir() or not list(records.glob("*.md")):
        failures.append("research-first: immutable source material is missing")
    if research_policy.get("cold_start_sequence") != ["research_intake", "research_organization", "core_canonicalization", "core_delivery", "future_owner_activation"]:
        failures.append("research-first: cold-start sequence is not canonical")
    owners = _load(root, "configs/owners_v1.json")["owners"]
    active = sorted(name for name, value in owners.items() if value.get("active"))
    if active != research_policy["initial_active_owners"]:
        failures.append("research-first: initial bootstrap may activate only Core")
    owner_ids: set[str] = set()
    git_owners: set[str] = set()
    branch_prefixes: set[str] = set()
    worktree_prefixes: set[str] = set()
    for name, owner in owners.items():
        profile_path = root / owner.get("profile", "")
        if not profile_path.is_file():
            failures.append(f"owner: missing dependency profile for {name}")
            continue
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        required_profile = {"owner_id", "git_owner", "branch_prefix", "worktree_prefix", "lifecycle_state", "owned_paths", "prohibited_paths", "owns_capabilities", "consumes_capabilities", "public_contracts", "upstream_owners", "downstream_consumers", "continuity", "verification_profiles", "orchestration", "activation_evidence", "no_ownership_grant"}
        if required_profile - profile.keys():
            failures.append(f"owner: incomplete dependency map for {name}")
            continue
        for field, seen in (("owner_id", owner_ids), ("git_owner", git_owners), ("branch_prefix", branch_prefixes), ("worktree_prefix", worktree_prefixes)):
            value = profile[field]
            if value in seen:
                failures.append(f"owner: duplicate {field} {value}")
            seen.add(value)
        private_dependencies = profile.get("private_implementation_dependencies", []) or [value for value in [*profile["consumes_capabilities"], *profile["public_contracts"]] if "private" in value.lower()]
        if private_dependencies:
            failures.append(f"owner: private cross-owner dependency for {name}")
        continuity = profile["continuity"]
        if not continuity.get("moc") or not (root / continuity["moc"]).exists():
            failures.append(f"owner: missing continuity MOC for {name}")
        if owner.get("active"):
            if profile["lifecycle_state"] != "active" or profile["no_ownership_grant"] or not profile["activation_evidence"] or not profile["verification_profiles"] or not profile["orchestration"].get("lanes"):
                failures.append(f"owner: active prerequisites are incomplete for {name}")
        elif profile["lifecycle_state"] == "active" or not profile["no_ownership_grant"]:
            failures.append(f"owner: inactive scaffold grants authority for {name}")
    template = owners.get("future-owner-template", {})
    if template.get("active") or any(not (root / template.get(key, "")).exists() for key in ("role", "bootstrap", "continuity", "profile")):
        failures.append("future-owner: inactive template prerequisites are incomplete")
    orchestration = _load(root, "configs/owner_scoped_orchestration_v1.json")
    expected_bindings = {"owner_orchestrator": ("gpt-5.6-sol", "xhigh"), "implementer": ("gpt-5.6-terra", "high"), "runner": ("gpt-5.6-luna", "max")}
    for lane, (model, reasoning) in expected_bindings.items():
        binding = orchestration.get("model_binding", {}).get(lane, {})
        if binding.get("model") != model or binding.get("reasoning_effort") != reasoning:
            failures.append(f"orchestration: exact {lane} model binding is missing")
    subordinate = orchestration.get("subordinate_task_lifecycle", {})
    if not subordinate.get("saved_project_required") or not subordinate.get("reuse_runner_thread_per_cycle"):
        failures.append("orchestration: saved-project Luna reuse is incomplete")
    required_finalization = {"accepted_exact_candidate_receipt", "no_correction_pending", "commit_push_integration", "primary_branch_sync", "terminal_reconciliation", "worktree_cleanup"}
    if subordinate.get("archive_owner") != "owner_orchestrator" or set(subordinate.get("archive_after", [])) != required_finalization:
        failures.append("orchestration: separate Sol finalization is incomplete")
    parity = validate_manifest(_load(root, "configs/tool_parity_v1.json"), root=root)
    failures.extend(f"tool-parity: {item}" for item in parity["errors"])
    testing = _load(root, "configs/testing/execution_v1.json")
    if testing.get("full", {}).get("workers") != 4 or set(testing.get("parallel_safe", [])) & set(testing.get("serial", [])):
        failures.append("testing: xdist cap or serial isolation is invalid")
    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    pytest_options = pyproject.get("tool", {}).get("pytest", {}).get("ini_options", {})
    if pytest_options.get("cache_dir") != "tmp/pytest-cache" or pytest_options.get("testpaths") != ["tests"]:
        failures.append("testing: pytest cache or testpaths are invalid")
    forbidden_global = ("-n", "--tb", "--maxfail", "--lf")
    if any(flag in pytest_options.get("addopts", "") for flag in forbidden_global):
        failures.append("testing: lifecycle flags must not be global addopts")
    _require_artifact(failures, root, "pytest-xdist", "3.8.0")
    _require_artifact(failures, root, "execnet", "2.1.2")
    for marker in config["forbidden_project_markers"]:
        for path in root.rglob("*"):
            relative = path.relative_to(root).as_posix() if path.is_file() else ""
            allowed = {"configs/conformance_v1.json", *config.get("reference_marker_allowlist", [])}
            if path.is_file() and relative not in allowed and ".git" not in path.parts and path.suffix in {".md", ".json", ".py", ".toml"}:
                if marker in path.read_text(encoding="utf-8", errors="ignore"):
                    failures.append(f"neutrality: forbidden marker {marker!r} in {path.relative_to(root)}")
    return failures
