# Repository Tools

## Purpose

This directory contains the command-line programs that enforce the governed
development workflow. Tools report evidence or perform narrowly declared
repository maintenance; they do not create product authority.

## Contents

| File | Significance |
| --- | --- |
| [__init__.py](__init__.py) | Makes the directory importable so tests and other tools can reuse public helpers without shelling out. |
| [agent_to_agent_handoff.py](agent_to_agent_handoff.py) | Compatibility entry point for the canonical plan-handoff command. It preserves older operator commands without maintaining a second workflow. |
| [agent_to_agent_plan_handoff.py](agent_to_agent_plan_handoff.py) | Creates immutable, content-addressed plan-critique requests and optionally invokes an allowlisted Claude, Gemini, MiniMax, Antigravity, or Codex CLI configured through the ignored `.env`; it validates critique shape and records only a command hash and safe invocation posture. |
| [agent_work_selection_audit.py](agent_work_selection_audit.py) | Records the frozen evidence, ownership, prerequisites, and disposition behind a substantial next-step selection. |
| [architecture_conformance.py](architecture_conformance.py) | Runs the repository-wide six-plane and documentation conformance check. This is the principal bootstrap acceptance command. |
| [capability_status.py](capability_status.py) | Validates and reports machine-readable capability maturity without inferring implementation from prose. |
| [check_agent_discussion_updates.py](check_agent_discussion_updates.py) | Detects coordination records that changed and need owner review or publication handling. |
| [export_agent_thread_continuity.py](export_agent_thread_continuity.py) | Exports one exact bounded user-visible task transcript transactionally, with redaction, ownership, navigation, and manifest evidence. |
| [origin_reconciler.py](origin_reconciler.py) | Inspects branches, remotes, worktrees, reachability, patch equivalence, owner integration inboxes, and Core-only primary synchronization. |
| [owner_scoped_orchestration.py](owner_scoped_orchestration.py) | Validates risk classifications, immutable work packets, lane receipts, runner bindings, archive acknowledgments, terminal reconciliation/synchronization/worktree evidence, and immutable closeout finalization. It records but does not perform host task archival, invoke models, or mutate Git. |
| [research_git_adapter.py](research_git_adapter.py) | Captures a credential-free public HTTPS Git branch or tag at a caller-supplied full expected commit. It uses a temporary bare repository, never checks out or executes source code, records commit/tree/blob lineage, and publishes only bounded `.md`, `.txt`, and `.pdf` blobs after explicit network authorization. |
| [research_intake.py](research_intake.py) | Imports one `.md`, `.txt`, or `.pdf` research artifact into immutable, content-addressed source records with provenance; intake never installs parsers. |
| [research_organizer.py](research_organizer.py) | Scans, compares, reviews, and maps research records without promoting them into canonical doctrine. PDF page extraction is native-text-only, exact-version-bound, and explicitly unavailable until the user-approved optional dependency exists. |
| [source_doc_audit.py](source_doc_audit.py) | Checks project-owned Python public surfaces for the required module and API documentation. |
| [test_runner.py](test_runner.py) | Provides focused, cached-failure, affected, broad, and isolated full-suite test profiles. |
| [tool_parity.py](tool_parity.py) | Validates the explicit disposition of reusable reference tools, generic adaptations, bootstrap-native tools, and deliberate exclusions. |
| [vault_maintainer.py](vault_maintainer.py) | Validates vault ownership and navigation, synchronizes generated breadcrumbs, and performs bounded migration or restoration operations. |

The corresponding tests are described in [`tests/tools/README.md`](../tests/tools/README.md).
Operational procedures live in [`docs/README.md`](../docs/README.md).

## Change Discipline

- Keep each tool project-neutral and deterministic where its contract requires it.
- State read/write, network, secret, and recovery behavior in the module and CLI documentation.
- Add or update the matching test and impact-map entry when behavior changes.
- Do not duplicate an existing tool under a new name; compatibility entry points
  must delegate to one canonical implementation.
- Write temporary output only under the configured ignored `tmp/` tree.
