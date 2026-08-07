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


def test_first_bootstrap_requires_native_capabilities_and_no_plugins() -> None:
    bootstrap = json.loads((ROOT / "configs/codex_bootstrap_v1.json").read_text(encoding="utf-8"))
    assert bootstrap["plugin_policy"] == {
        "required_plugins": [],
        "automatic_installation": False,
        "external_orchestration_plugin_required": False,
        "posture": "native_capabilities_first",
    }
    assert {item["id"] for item in bootstrap["required_native_capabilities"]} == {
        "saved_local_project_primary_folder",
        "repository_agents_guidance",
        "git_and_repository_local_worktrees",
        "owner_orchestrator_model_binding",
        "implementer_model_binding",
        "verification_runner_model_binding",
        "subordinate_task_coordination",
        "subordinate_task_archival",
    }
    assert all(item["default_state"] == "not_required" for item in bootstrap["optional_plugins"])
    assert bootstrap["preflight"]["installation_requires_user_approval"] is True
    pdf = bootstrap["optional_research_dependencies"][0]
    assert pdf["id"] == "native_text_pdf_extraction"
    assert pdf["package"] == "pypdf"
    assert pdf["version"] == "6.14.2"
    assert pdf["automatic_download_or_install"] is False
    assert pdf["user_approval_required"] is True


def test_external_a2a_configuration_is_nonsecret_and_opt_in() -> None:
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "/.env" in ignored
    assert "!/.env.example" in ignored
    for provider in ("CLAUDE", "GEMINI", "MMX", "AGY", "CODEX"):
        assert f"PROJECT_{provider}_COMMAND=" in example
        assert f"PROJECT_{provider}_INPUT_MODE=" in example
        assert f"PROJECT_{provider}_MODEL_ID=" in example
    assert "Do not put API keys" in example
    assert "PROJECT_CLAUDE_API_KEY" not in example


def test_orchestration_has_exact_model_bindings_and_separate_sol_finalization() -> None:
    orchestration = json.loads((ROOT / "configs/owner_scoped_orchestration_v1.json").read_text(encoding="utf-8"))
    bindings = orchestration["model_binding"]
    assert bindings["owner_orchestrator"] == {"model": "gpt-5.6-sol", "reasoning_effort": "xhigh"}
    assert bindings["implementer"] == {"model": "gpt-5.6-terra", "reasoning_effort": "high"}
    assert bindings["runner"] == {"model": "gpt-5.6-luna", "reasoning_effort": "max"}
    assert orchestration["prompt_templates"] == {
        "owner_orchestrator": "roles/shared/OWNER_ORCHESTRATOR_PROMPT.md",
        "implementer": "roles/shared/IMPLEMENTER_PROMPT.md",
        "runner": "roles/shared/VERIFICATION_RUNNER_PROMPT.md",
    }
    assert all((ROOT / path).is_file() for path in orchestration["prompt_templates"].values())
    assert orchestration["subordinate_task_lifecycle"]["archive_owner"] == "owner_orchestrator"
    assert orchestration["subordinate_task_lifecycle"]["reuse_runner_thread_per_cycle"] is True
    assert set(orchestration["subordinate_task_lifecycle"]["finalization_requires"]) == {
        "recorded_receipt_hashes",
        "subordinate_task_dispositions",
        "terminal_reconciliation",
        "primary_branch_sync",
        "worktree_removal",
        "archive_acknowledgment",
    }
    assert "/.worktrees/" in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()


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


def test_system_user_guide_explains_operation_instead_of_only_listing_assets() -> None:
    guide = (ROOT / "docs/SYSTEM_USER_GUIDE.md").read_text(encoding="utf-8")
    for phrase in (
        "## Start In The Codex Desktop App",
        "### Guide map",
        "## The Vault And The LLM Wiki Pattern",
        "## Owner-Scoped Orchestration",
        "## Agent-To-Agent Discussions And Owner Direction",
        "### Set Up A2A Coordination From The Bootstrap",
        "### Optional External-Model Critique",
        "## Close A Task Promptly And Rehydrate Correctly",
        "### Why continuity is stored in Git",
        "### Rehydrate in a fresh task or on another device",
        "## What Is Unique Here",
        "## How The Architecture Is Opinionated",
        "## Daily Operator Checklist",
        "convention-driven and batteries-included",
        "Routine mechanics follow established conventions",
        "Authority explicit",
        "Once active,",
        "every owner—including non-Core owners—uses the complete Sol/Terra/Luna",
        "Core alone integrates the",
        "but it does not implement another owner's product work",
        "Project_Obsidian_Vault/30_Core/Core Bootstrap.md",
        "roles/shared/",
        "archive the completed owner task",
        "Use SymPy for exact symbolic constants",
        "Use NumPy for the finite floating-point behavior",
        "### Codex capability and plugin preflight",
        "No Codex plugin is required for the initial bootstrap",
        "Sol Advisor is not required or installed",
        "Responsibility transferred to another employee",
        "The owner is therefore a durable project role",
        "Git supplies portability, provenance, integrity history, and distribution",
        "Different model families",
        "Copy-Item .env.example .env",
        "External invocation is data egress",
        "Put `.md`, `.txt`, and `.pdf` source material",
        "PDF research requires optional pypdf 6.14.2",
        "python -m pip install -e \".[pdf]\"",
        "does not perform OCR",
        "public GitHub repository—or another public HTTPS Git repository—enters",
        "Research can begin from four source types",
        "Public GitHub repository",
        "python tools/research_git_adapter.py",
        "does not check out or execute code",
        "Every repository has its own license and reuse posture",
    ):
        assert phrase in guide
    assert guide.count("```mermaid") >= 7


def test_system_user_guide_has_a_clean_ordered_narrative_map() -> None:
    guide = (ROOT / "docs/SYSTEM_USER_GUIDE.md").read_text(encoding="utf-8")
    sections = (
        "The System In One View",
        "Start In The Codex Desktop App",
        "The Vault And The LLM Wiki Pattern",
        "Owner-Scoped Orchestration",
        "Create And Activate A New Owner",
        "Agent-To-Agent Discussions And Owner Direction",
        "One Complete Work Cycle",
        "Close A Task Promptly And Rehydrate Correctly",
        "What Is Unique Here",
        "How The Architecture Is Opinionated",
        "When To Simplify",
        "Daily Operator Checklist",
    )
    positions = [guide.index(f"## {section}") for section in sections]
    assert positions == sorted(positions)
    for section in sections:
        assert f"| [{section}](#" in guide
    assert guide.index("### Who decides the direction") < guide.index(
        "### Set Up A2A Coordination From The Bootstrap"
    )
    assert "This section shows their\nnormal operating sequence" in guide


def test_system_user_guide_explains_new_owner_scaffold_and_prompt_handoff() -> None:
    guide = (ROOT / "docs/SYSTEM_USER_GUIDE.md").read_text(encoding="utf-8")
    for phrase in (
        "## Create And Activate A New Owner",
        "### What Core builds",
        "### What Core returns to the user",
        "This is an adoption task",
        "The user should paste that prompt into a **new task",
        "### Adoption and activation sequence",
        "### Worked example: Database Layer Owner",
        "Business repository ports and atomic domain operations",
        "does not activate a database owner in this bootstrap",
    ):
        assert phrase in guide
    assert guide.index("## Owner-Scoped Orchestration") < guide.index(
        "## Create And Activate A New Owner"
    ) < guide.index("## Agent-To-Agent Discussions And Owner Direction")
    assert "no_ownership_grant: true" in guide


def test_system_user_guide_defines_a2a_authority_and_owner_direction() -> None:
    guide = (ROOT / "docs/SYSTEM_USER_GUIDE.md").read_text(encoding="utf-8")
    for phrase in (
        "The requesting owner should say **what public outcome it needs and why**",
        "receiving owner decides **whether and how",
        "Strong words",
        "do not make a point binding",
        "Accepted` means the owner accepts the direction; it does not claim the code",
        "awaiting_named_integrator",
        "Common Agreement",
        "All Remaining Disagreements",
        "Core needs a third-party licensing disposition",
        "The owner agent operates this",
        "The user does not need to run the handoff commands",
        "What the user does",
        "What the owner agent does",
        "40_Coordination/Generated/Active Records.md",
        "The owner publishes a separate",
        "generated files are never",
        "PROJECT_<PROVIDER>_COMMAND",
        "--invoke claude",
    ):
        assert phrase in guide


def test_root_policy_requires_executable_mathematical_evidence() -> None:
    policy = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for phrase in (
        "Do not supply numerical or algebraic claims from memory or mental",
        "Use SymPy for exact symbolic constants, identities, rational",
        "use NumPy for the finite floating-point behavior",
        "Cite the executable witness, repository constant, or",
    ):
        assert phrase in policy


def test_continuity_documentation_supports_device_and_custodian_portability() -> None:
    guide = (ROOT / "docs/AGENT_CONTINUITY_EXPORT.md").read_text(encoding="utf-8")
    core = (
        ROOT / "Project_Obsidian_Vault/30_Core/Continuity/README.md"
    ).read_text(encoding="utf-8")
    for phrase in (
        "An owner is a durable project role",
        "another device",
        "transfer responsibility to another employee",
        "Git provides portable and",
        "versioned evidence",
    ):
        assert phrase in guide
    assert "new task and thread ID" in core
    assert "same Core" in core


def test_folder_readmes_explain_every_registered_maintained_directory() -> None:
    manifest = json.loads(
        (ROOT / "configs/documentation_system_v1.json").read_text(encoding="utf-8")
    )
    folders = {item["directory"]: item for item in manifest["folder_readmes"]}
    assert {
        "configs",
        "docs",
        "governance_bootstrap",
        "roles/core",
        "tests",
        "tests/tools",
        "tools",
    } <= folders.keys()
    assert validate_documentation_system(ROOT) == []


def test_tools_readme_describes_each_operator_tool() -> None:
    readme = (ROOT / "tools/README.md").read_text(encoding="utf-8")
    maintained_tools = {
        path.name
        for path in (ROOT / "tools").glob("*.py")
        if path.name != "__init__.py"
    }
    assert maintained_tools
    assert all(f"`{name}`" in readme for name in maintained_tools)


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
        "PDF research requires optional pypdf 6.14.2",
        "Never download or install a PDF",
        "public Git repository is proposed as research",
        "full expected commit",
        "no checkout, hooks, code execution",
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


def test_vault_readmes_and_instruction_hub_are_complete() -> None:
    manifest = json.loads(
        (ROOT / "configs/documentation_system_v1.json").read_text(encoding="utf-8")
    )
    surfaces = {item["path"] for item in manifest["surfaces"]}
    assert {
        "Project_Obsidian_Vault/README.md",
        "Project_Obsidian_Vault/10_Research/README.md",
        "Project_Obsidian_Vault/30_Core/Continuity/README.md",
        "Project_Obsidian_Vault/40_Coordination/README.md",
        "Project_Obsidian_Vault/40_Coordination/Instructions/README.md",
        "Project_Obsidian_Vault/90_Archive/README.md",
    } <= surfaces
    hub = (
        ROOT / "Project_Obsidian_Vault/40_Coordination/Instructions/README.md"
    ).read_text(encoding="utf-8")
    for phrase in (
        "## Required Starting Order",
        "## Critique Preamble And Shape",
        "## Planning Routine",
        "## Implementation And Publication",
        "## Instruction Map",
    ):
        assert phrase in hub
    assert len(manifest["vault_reference_dispositions"]) == 10
