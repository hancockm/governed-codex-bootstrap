"""Repository architecture conformance checks."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any

from .source_docs import audit_package
from .vault import check as check_vault


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


def check_repository(root: Path) -> list[str]:
    """Return deterministic violations of the bootstrap architecture."""
    config = _load(root, "configs/conformance_v1.json")
    failures: list[str] = []
    for plane, paths in config["required_planes"].items():
        for item in paths:
            if not (root / item).is_file():
                failures.append(f"{plane}: missing {item}")
    old_canonical = root / "canonical"
    if old_canonical.exists() and any(old_canonical.rglob("*")):
        failures.append("canonical: narrative canonical files must exist only in the vault")
    registry = _load(root, "configs/vault_maintenance_registry_v1.json")
    vault_root = root / registry["vault_root"]
    if not vault_root.is_dir() or any(not (vault_root / path).is_file() for path in registry["canonical_paths"]):
        failures.append("canonical: vault canonical single source is incomplete")
    vault_errors = check_vault(root)
    if vault_errors:
        failures.extend(f"vault: {error}" for error in vault_errors)
    source_findings = audit_package(root / "governance_bootstrap")
    if source_findings:
        failures.extend(f"source-doc: {finding}" for finding in source_findings)
    capability = _load(root, "configs/capability_registry_v1.json")
    allowed_states = {"proposed", "active", "verified", "deferred", "superseded", "retired"}
    if any(item.get("state") not in allowed_states or not item.get("evidence") or not item.get("verification") for item in capability.get("capabilities", [])):
        failures.append("capability: maturity evidence is incomplete")
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
    template = owners.get("future-owner-template", {})
    if template.get("active") or any(not (root / template.get(key, "")).exists() for key in ("role", "bootstrap", "continuity", "profile")):
        failures.append("future-owner: inactive template prerequisites are incomplete")
    orchestration = _load(root, "configs/owner_scoped_orchestration_v1.json")
    expected_bindings = {"sol": ("gpt-5.6-sol", "xhigh"), "terra": ("gpt-5.6-terra", "high"), "luna": ("gpt-5.6-luna", "max")}
    for lane, (model, reasoning) in expected_bindings.items():
        binding = orchestration.get("lanes", {}).get(lane, {})
        if binding.get("model") != model or binding.get("reasoning_effort") != reasoning:
            failures.append(f"orchestration: exact {lane} model binding is missing")
    luna = orchestration.get("lanes", {}).get("luna", {})
    if not luna.get("must_run_in_saved_project") or not luna.get("must_reuse_project_bound_thread") or not orchestration.get("saved_project_id") or not orchestration.get("project_bound_luna_thread"):
        failures.append("orchestration: saved-project Luna reuse is incomplete")
    finalization = orchestration.get("sol_finalization", {})
    required_finalization = {"accepted_exact_candidate_receipt", "no_correction_pending", "commit_push_integration", "primary_branch_sync", "terminal_reconciliation", "worktree_cleanup"}
    if finalization.get("owner") != "sol" or finalization.get("acknowledgment") != "subordinate_archive" or set(finalization.get("requires", [])) != required_finalization:
        failures.append("orchestration: separate Sol finalization is incomplete")
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
            if path.is_file() and path.relative_to(root).as_posix() != "configs/conformance_v1.json" and ".git" not in path.parts and path.suffix in {".md", ".json", ".py", ".toml"}:
                if marker in path.read_text(encoding="utf-8", errors="ignore"):
                    failures.append(f"neutrality: forbidden marker {marker!r} in {path.relative_to(root)}")
    return failures
