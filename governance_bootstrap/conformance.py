"""Repository architecture conformance checks."""

from __future__ import annotations

import hashlib
import json
import tomllib
from pathlib import Path
from typing import Any

from tools.capability_status import CapabilityStatusError, validate_registry
from tools.source_doc_audit import find_missing_docstrings
from tools.tool_parity import validate_manifest
from tools.vault_maintainer import collect_diagnostics, load_registry


APACHE_2_0_SPDX_ID = "Apache-2.0"
APACHE_2_0_LICENSE_SHA256 = (
    "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30"
)
PROJECT_NOTICE = (
    "Governed Codex Bootstrap\n"
    "Copyright 2026 Michael E. Hancock\n\n"
    "This product is licensed under the Apache License, Version 2.0.\n"
)


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


def validate_project_license(root: Path) -> list[str]:
    """Return violations of the root Apache-2.0 licensing contract."""
    failures: list[str] = []
    license_path = root / "LICENSE"
    notice_path = root / "NOTICE"
    readme_path = root / "README.md"
    pyproject_path = root / "pyproject.toml"

    if not license_path.is_file():
        failures.append("missing root LICENSE")
    else:
        normalized = (
            license_path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        )
        if hashlib.sha256(normalized).hexdigest() != APACHE_2_0_LICENSE_SHA256:
            failures.append("root LICENSE is not the unmodified official Apache 2.0 text")

    if not notice_path.is_file():
        failures.append("missing root NOTICE")
    elif notice_path.read_text(encoding="utf-8").replace("\r\n", "\n") != PROJECT_NOTICE:
        failures.append("root NOTICE does not identify the project and copyright holder")

    if not pyproject_path.is_file():
        failures.append("missing pyproject.toml licensing metadata")
    else:
        project = tomllib.loads(pyproject_path.read_text(encoding="utf-8")).get("project", {})
        if project.get("license") != APACHE_2_0_SPDX_ID:
            failures.append("pyproject.toml project license must be Apache-2.0")

    if not readme_path.is_file():
        failures.append("missing README.md licensing declaration")
    else:
        readme = readme_path.read_text(encoding="utf-8")
        required_readme_text = (
            "## License",
            "[Apache License 2.0](LICENSE)",
            "`Apache-2.0`",
            "[NOTICE](NOTICE)",
        )
        if any(item not in readme for item in required_readme_text):
            failures.append("README.md license section is incomplete")
    return failures


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
    documented_directories: set[str] = set()
    for folder in manifest.get("folder_readmes", []):
        directory = folder.get("directory", "")
        readme = folder.get("readme", "")
        if not directory or directory in documented_directories:
            failures.append(f"invalid or duplicate folder documentation {directory!r}")
            continue
        documented_directories.add(directory)
        directory_path = root / directory
        readme_path = root / readme
        if not directory_path.is_dir():
            failures.append(f"missing documented directory {directory}")
            continue
        if readme_path.parent != directory_path or not readme_path.is_file():
            failures.append(f"missing folder README {readme or directory + '/README.md'}")
            continue
        text = readme_path.read_text(encoding="utf-8")
        for entry in folder.get("required_entries", []):
            if entry not in text:
                failures.append(f"folder README {readme} does not describe {entry}")
        for heading in folder.get("required_headings", []):
            if heading not in text:
                failures.append(f"folder README {readme} is missing heading {heading!r}")
    if not documented_directories:
        failures.append("folder documentation inventory is empty")
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
    required_vault_dispositions = {
        "plane_readmes",
        "shared_instruction_hub",
        "core_owner_instructions",
        "future_owner_instructions",
        "owner_continuity_packs",
        "transcript_and_month_readmes",
        "feature_readmes",
        "publication_and_summary_readmes",
        "product_and_domain_manuals",
        "historical_rollout_records",
    }
    if set(manifest.get("vault_reference_dispositions", {})) != required_vault_dispositions:
        failures.append("vault README and instruction dispositions are incomplete")
    return failures


def validate_owner_profiles(root: Path, owners: dict[str, Any]) -> list[str]:
    """Return owner-profile and future-owner-template violations."""
    failures: list[str] = []
    owner_ids: set[str] = set()
    git_owners: set[str] = set()
    branch_prefixes: set[str] = set()
    worktree_prefixes: set[str] = set()
    required_profile = {
        "owner_id",
        "git_owner",
        "branch_prefix",
        "worktree_prefix",
        "lifecycle_state",
        "owned_paths",
        "prohibited_paths",
        "owns_capabilities",
        "consumes_capabilities",
        "public_contracts",
        "upstream_owners",
        "downstream_consumers",
        "canonical_documents",
        "canonical_document_adoption_evidence",
        "continuity",
        "verification_profiles",
        "orchestration",
        "activation_evidence",
        "no_ownership_grant",
    }
    required_canonical_documents = {
        "core_thesis",
        "architecture",
        "spec",
        "implementation_roadmap",
    }

    for name, owner in owners.items():
        profile_path = root / owner.get("profile", "")
        if not profile_path.is_file():
            failures.append(f"owner: missing dependency profile for {name}")
            continue
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        if required_profile - profile.keys():
            failures.append(f"owner: incomplete dependency map for {name}")
            continue
        canonical_documents = profile["canonical_documents"]
        canonical_document_set = (
            set(canonical_documents) if isinstance(canonical_documents, dict) else set()
        )
        if canonical_document_set != required_canonical_documents:
            failures.append(f"owner: canonical document set is incomplete for {name}")
        else:
            for document_name, document_path in canonical_documents.items():
                if (
                    not isinstance(document_path, str)
                    or not document_path
                    or not (root / document_path).is_file()
                ):
                    failures.append(
                        f"owner: missing {document_name} canonical document for {name}"
                    )
        for field, seen in (
            ("owner_id", owner_ids),
            ("git_owner", git_owners),
            ("branch_prefix", branch_prefixes),
            ("worktree_prefix", worktree_prefixes),
        ):
            value = profile[field]
            if value in seen:
                failures.append(f"owner: duplicate {field} {value}")
            seen.add(value)
        private_dependencies = profile.get("private_implementation_dependencies", []) or [
            value
            for value in [
                *profile["consumes_capabilities"],
                *profile["public_contracts"],
            ]
            if "private" in value.lower()
        ]
        if private_dependencies:
            failures.append(f"owner: private cross-owner dependency for {name}")
        continuity = profile["continuity"]
        if not continuity.get("moc") or not (root / continuity["moc"]).exists():
            failures.append(f"owner: missing continuity MOC for {name}")
        if owner.get("active"):
            owned_paths = [
                path.rstrip("/")
                for path in profile["owned_paths"]
                if isinstance(path, str) and path
            ]
            canonical_documents_owned = (
                all(
                    isinstance(document_path, str)
                    and any(
                        document_path == owned_path
                        or document_path.startswith(f"{owned_path}/")
                        for owned_path in owned_paths
                    )
                    for document_path in canonical_documents.values()
                )
                if isinstance(canonical_documents, dict)
                else False
            )
            active_prerequisites_incomplete = (
                profile["lifecycle_state"] != "active"
                or profile["no_ownership_grant"]
                or not profile["activation_evidence"]
                or not profile["canonical_document_adoption_evidence"]
                or not profile["verification_profiles"]
                or not profile["orchestration"].get("lanes")
                or canonical_document_set != required_canonical_documents
                or not canonical_documents_owned
            )
            if active_prerequisites_incomplete:
                failures.append(f"owner: active prerequisites are incomplete for {name}")
        elif profile["lifecycle_state"] == "active" or not profile["no_ownership_grant"]:
            failures.append(f"owner: inactive scaffold grants authority for {name}")

    template = owners.get("future-owner-template", {})
    template_paths = ("role", "bootstrap", "continuity", "profile")
    if template.get("active") or any(
        not (root / template.get(key, "")).exists() for key in template_paths
    ):
        failures.append("future-owner: inactive template prerequisites are incomplete")
    return failures


def check_repository(root: Path) -> list[str]:
    """Return deterministic violations of the bootstrap architecture."""
    config = _load(root, "configs/conformance_v1.json")
    failures: list[str] = []
    failures.extend(f"license: {item}" for item in validate_project_license(root))
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
    codex_bootstrap = _load(root, "configs/codex_bootstrap_v1.json")
    plugin_policy = codex_bootstrap.get("plugin_policy", {})
    if (
        codex_bootstrap.get("schema_version") != "codex_bootstrap_v1"
        or plugin_policy.get("required_plugins") != []
        or plugin_policy.get("automatic_installation") is not False
        or plugin_policy.get("external_orchestration_plugin_required") is not False
    ):
        failures.append("codex-bootstrap: cold start must require no plugins or automatic installation")
    expected_native = {
        "saved_local_project_primary_folder",
        "repository_agents_guidance",
        "git_and_repository_local_worktrees",
        "owner_orchestrator_model_binding",
        "implementer_model_binding",
        "verification_runner_model_binding",
        "subordinate_task_coordination",
        "subordinate_task_archival",
    }
    native = codex_bootstrap.get("required_native_capabilities", [])
    if {item.get("id") for item in native if isinstance(item, dict)} != expected_native:
        failures.append("codex-bootstrap: required native capability preflight is incomplete")
    if any(
        not item.get("required_for") or not item.get("failure_posture") or not item.get("purpose")
        for item in native
        if isinstance(item, dict)
    ):
        failures.append("codex-bootstrap: native capability dispositions are incomplete")
    optional_plugins = codex_bootstrap.get("optional_plugins", [])
    if not optional_plugins or any(
        item.get("default_state") != "not_required" or not item.get("use_only_when")
        for item in optional_plugins
        if isinstance(item, dict)
    ):
        failures.append("codex-bootstrap: optional plugin boundaries are incomplete")
    preflight = codex_bootstrap.get("preflight", {})
    if (
        preflight.get("inspect_installed_plugins") is not True
        or preflight.get("installation_requires_user_approval") is not True
        or preflight.get("connector_authorization_is_separate") is not True
    ):
        failures.append("codex-bootstrap: plugin preflight and authorization are incomplete")
    research_dependencies = codex_bootstrap.get("optional_research_dependencies", [])
    pdf_dependencies = [
        item for item in research_dependencies if item.get("id") == "native_text_pdf_extraction"
    ]
    if len(pdf_dependencies) != 1:
        failures.append("codex-bootstrap: native-text PDF dependency declaration is missing")
    else:
        pdf_dependency = pdf_dependencies[0]
        if (
            pdf_dependency.get("package") != "pypdf"
            or pdf_dependency.get("version") != "6.14.2"
            or pdf_dependency.get("python_extra") != "pdf"
            or pdf_dependency.get("automatic_download_or_install") is not False
            or pdf_dependency.get("user_approval_required") is not True
            or pdf_dependency.get("extensions") != [".pdf"]
        ):
            failures.append("codex-bootstrap: native-text PDF dependency consent is incomplete")
    research_adapters = codex_bootstrap.get("research_source_adapters", [])
    git_adapters = [
        item
        for item in research_adapters
        if item.get("id") == "public_https_git_snapshot"
    ]
    if len(git_adapters) != 1:
        failures.append("codex-bootstrap: public Git research adapter is missing")
    else:
        git_adapter = git_adapters[0]
        if (
            git_adapter.get("command") != "python tools/research_git_adapter.py"
            or git_adapter.get("dependency") != "installed Git executable"
            or git_adapter.get("automatic_download_or_install") is not False
            or git_adapter.get("network_authorization_required") is not True
            or git_adapter.get("selected_formats") != [".md", ".txt", ".pdf"]
            or len(git_adapter.get("identity_requirements", [])) != 4
            or len(git_adapter.get("limitations", [])) != 4
        ):
            failures.append("codex-bootstrap: public Git research boundary is incomplete")
    failures.extend(validate_owner_profiles(root, owners))
    orchestration = _load(root, "configs/owner_scoped_orchestration_v1.json")
    expected_bindings = {"owner_orchestrator": ("gpt-5.6-sol", "xhigh"), "implementer": ("gpt-5.6-terra", "high"), "runner": ("gpt-5.6-luna", "xhigh")}
    for lane, (model, reasoning) in expected_bindings.items():
        binding = orchestration.get("model_binding", {}).get(lane, {})
        if binding.get("model") != model or binding.get("reasoning_effort") != reasoning:
            failures.append(f"orchestration: exact {lane} model binding is missing")
    expected_prompts = {
        "owner_orchestrator": "roles/shared/OWNER_ORCHESTRATOR_PROMPT.md",
        "implementer": "roles/shared/IMPLEMENTER_PROMPT.md",
        "runner": "roles/shared/VERIFICATION_RUNNER_PROMPT.md",
    }
    if orchestration.get("prompt_templates") != expected_prompts:
        failures.append("orchestration: shared lane prompt template registry is incomplete")
    for lane, prompt_path in expected_prompts.items():
        if not (root / prompt_path).is_file():
            failures.append(f"orchestration: shared prompt template is missing for {lane}")
    subordinate = orchestration.get("subordinate_task_lifecycle", {})
    if not subordinate.get("saved_project_required") or not subordinate.get("reuse_runner_thread_per_cycle"):
        failures.append("orchestration: saved-project Luna reuse is incomplete")
    required_finalization = {"accepted_exact_candidate_receipt", "no_correction_pending", "commit_push_integration", "primary_branch_sync", "terminal_reconciliation", "worktree_cleanup"}
    if subordinate.get("archive_owner") != "owner_orchestrator" or set(subordinate.get("archive_after", [])) != required_finalization:
        failures.append("orchestration: separate Sol finalization is incomplete")
    required_finalization_evidence = {"recorded_receipt_hashes", "subordinate_task_dispositions", "terminal_reconciliation", "primary_branch_sync", "worktree_removal", "archive_acknowledgment"}
    if set(subordinate.get("finalization_requires", [])) != required_finalization_evidence:
        failures.append("orchestration: enforceable closeout evidence is incomplete")
    gitignore_lines = {
        line.strip()
        for line in (root / ".gitignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    if "/.worktrees/" not in gitignore_lines:
        failures.append("git: repository-local worktree root is not ignored")
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
    pdf_extra = pyproject.get("project", {}).get("optional-dependencies", {}).get("pdf", [])
    if pdf_extra != ["pypdf==6.14.2"]:
        failures.append("research: exact optional PDF dependency is not pinned")
    _require_artifact(failures, root, "pypdf", "6.14.2")
    for marker in config["forbidden_project_markers"]:
        for path in root.rglob("*"):
            relative = path.relative_to(root).as_posix() if path.is_file() else ""
            allowed = {"configs/conformance_v1.json", *config.get("reference_marker_allowlist", [])}
            if path.is_file() and relative not in allowed and ".git" not in path.parts and path.suffix in {".md", ".json", ".py", ".toml"}:
                if marker in path.read_text(encoding="utf-8", errors="ignore"):
                    failures.append(f"neutrality: forbidden marker {marker!r} in {path.relative_to(root)}")
    return failures
