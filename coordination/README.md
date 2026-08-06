# Agent-to-Agent Coordination

This folder contains source-only cross-owner requests, critiques, work-
selection audits, update records, and dispositions. It is convergence history,
not canonical project doctrine.

## Reading Order

1. Open the vault coordination MOC.
2. Read the compact active/update index.
3. Open only records relevant to the current boundary.
4. Verify repository claims against current source, tests, configuration,
   canonical documents, and Git state.

Do not load every archive by default.

## Critique Structure

Every substantive critique records:

1. Common Agreement
2. All Remaining Disagreements
3. Critical Weak Points
4. Convergence Move
5. Decision Status

The owning agent assigns each point one disposition: Accepted, Partially
accepted, Rejected, Deferred, or Requires user approval. Strong critique
language is not implementation authority.

## Atomic Records

Use `tools/agent_to_agent_plan_handoff.py` to create one content-addressed
record per plan. The compatibility alias is
`tools/agent_to_agent_handoff.py`. Record the frozen baseline, source plan,
critique, owner disposition, and relevant hashes together. Managed indexes and
update records remain compact.

## Cross-Owner Publication

A request is delivered only when its record is committed and reachable from
the recipient's shared canonical Git history. A record left solely in an
unlanded worktree cannot establish an external blocker. Responses and
dispositions follow the same publication rule.

## Boundaries

- A2A records do not grant file ownership.
- Review agents edit only assigned atomic records.
- Core owns shared indexes and canonical promotion.
- Feature owners own the meaning and final disposition of their boundary.
- Cross-owner transcript duplication is prohibited; link to the owning
  continuity archive instead.
