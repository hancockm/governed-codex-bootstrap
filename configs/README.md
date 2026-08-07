# Configuration Registry

## Purpose

This directory holds versioned, machine-readable governance policy. Markdown
explains the rules; these files provide the identities and constraints that
tools validate.

## Contents

| File or directory | Significance |
| --- | --- |
| [capability_registry_v1.json](capability_registry_v1.json) | Declares capability maturity and its evidence. |
| [codex_bootstrap_v1.json](codex_bootstrap_v1.json) | Separates required native Codex capabilities from optional plugins, exact optional research parsers, and explicitly authorized bounded source adapters during cold start. |
| [conformance_v1.json](conformance_v1.json) | Defines the six required governance planes and research-first cold start. |
| [core_moc_v1.json](core_moc_v1.json) | Registers Core vault hierarchy and maintained navigation. |
| [documentation_system_v1.json](documentation_system_v1.json) | Registers required operational documents, folder READMEs, and adaptation dispositions. |
| [git_reconciliation_v1.json](git_reconciliation_v1.json) | Defines the primary branch, remote, owners, namespaces, and worktree root. |
| [owner_scoped_orchestration_v1.json](owner_scoped_orchestration_v1.json) | Defines lane models, owner profiles, Git authority, and subordinate-task lifecycle. |
| [owners_v1.json](owners_v1.json) | Registers active and inactive owners and their dependency profiles. |
| [risk_classification_v1.json](risk_classification_v1.json) | Maps change triggers to required orchestration tiers. |
| [tool_parity_v1.json](tool_parity_v1.json) | Records the disposition of each reference and bootstrap tool. |
| [vault_maintenance_registry_v1.json](vault_maintenance_registry_v1.json) | Registers maintained vault scopes, owners, schemas, and generated navigation. |
| [work_selection_audit_v1.json](work_selection_audit_v1.json) | Defines the advisory work-selection audit schema and fixtures. |
| [testing/](testing) | Contains test execution and source-to-test impact policy. |

## Change Discipline

Configuration changes require matching tests and documentation. Never edit a
versioned policy merely to make a failing check pass; reconcile the intended
contract first, then change the policy and its consumers together.
