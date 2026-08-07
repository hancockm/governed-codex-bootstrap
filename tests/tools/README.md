# Tool Tests

## Purpose

This directory contains focused behavioral tests for repository governance
commands. Test fixtures use temporary repositories and must not mutate the
developer's primary checkout.

## Contents

| File | Significance |
| --- | --- |
| [test_agent_work_selection_audit.py](test_agent_work_selection_audit.py) | Audit identity, evidence cutoff, validation, and advisory posture. |
| [test_capability_status.py](test_capability_status.py) | Capability maturity schema and evidence validation. |
| [test_export_agent_thread_continuity.py](test_export_agent_thread_continuity.py) | Exact-prefix selection, redaction, rendering, uniqueness, transactions, and recovery. |
| [test_origin_reconciler.py](test_origin_reconciler.py) | Branch, worktree, remote, patch-equivalence, inbox, disposition, and primary-sync safety. |
| [test_owner_scoped_orchestration.py](test_owner_scoped_orchestration.py) | Risk tiers, packet/receipt hashes, lane restrictions, runner binding, and immutable publication. |
| [test_tool_parity.py](test_tool_parity.py) | Reference-tool inventory and generic-disposition completeness. |
| [test_vault_maintainer.py](test_vault_maintainer.py) | Vault ownership, navigation, migration, restoration, and diagnostics. |

## Change Discipline

Use repository-local pytest temporary bases, assert failed inspections as
failures rather than clean state, and remove any intentionally locked or
permission-restricted fixture artifacts.
