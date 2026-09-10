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
- [RESEARCH_CRITIC_PROMPT.md](RESEARCH_CRITIC_PROMPT.md) defines Astra's optional, Sol-invoked, read-only
  advisory review rules.

## Change Discipline

Shared prompts cannot grant owner-specific authority. Keep them aligned with
the orchestration registry and root policy, and validate every active owner
after a shared prompt changes.

Sol sends the Implementation Context Brief through the existing dispatch
message. Terra uses the Implementer prompt to reorient to the repository and
each target document before narrative edits. The brief does not change packet
or receipt schemas.

The Implementer prompt defines Primary Medium work and Bounded Correction
Light work with backend `low`. The registry still has exactly three lane keys: Owner Orchestrator,
Implementer, and Verification Runner.

The optional Research Critic is a support role. It is not a packet lane. Sol
alone may invoke it with host-recorded role and model evidence for one bounded
evidence gap or contradiction. All subordinate prompts require parent
notifications and end idle turns after dispatch or return.
