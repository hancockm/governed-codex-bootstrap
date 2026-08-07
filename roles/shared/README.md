# Shared Role Prompts

## Purpose

This directory holds project-neutral prompt material that owner profiles may
reference without copying into each role.

## Contents

- [OWNER_ORCHESTRATOR_PROMPT.md](OWNER_ORCHESTRATOR_PROMPT.md) defines the common Sol authority, packet,
  review, publication, and closeout posture.
- [IMPLEMENTER_PROMPT.md](IMPLEMENTER_PROMPT.md) defines Terra's packet-bounded implementation,
  local-candidate, receipt, and non-publication rules.
- [VERIFICATION_RUNNER_PROMPT.md](VERIFICATION_RUNNER_PROMPT.md) defines Luna's saved-project, exact-candidate,
  read-only verification and receipt rules.

## Change Discipline

Shared prompts cannot grant owner-specific authority. Keep them aligned with
the orchestration registry and root policy, and validate every active owner
after a shared prompt changes.
