# Universal Work Selection Audit

<!-- generated:breadcrumbs:start -->
<< Previous: [[40_Coordination/Instructions/All Owners User Collaboration And Decision Semantics]] | Up: [[40_Coordination/Instructions/README]] | Next: [[40_Coordination/Instructions/Repository-Local Worktree Standard]] >>
<!-- generated:breadcrumbs:end -->

## Purpose

Every substantial next-step selection leaves one source-only audit of the
evidence used to select one candidate. The audit validates declared evidence;
it does not discover work, establish truth, grant ownership, or authorize
implementation.

## Evidence Boundary

Pin the Git commit used for decision evidence. Declare repository-relative
Markdown paths, exact ATX heading lines, section hashes, stable atom IDs, and
exact excerpts. Each excerpt must be unique in its normalized section.

Separate the candidate result from unrelated repository conditions.
Candidate-specific unresolved prerequisites may produce `not_selectable`,
`owner_disposition_required`, or `user_approval_required`. A structurally valid
adverse audit remains useful evidence.

## Procedure

1. Pin the baseline commit.
2. Select one candidate with stable ID, owner, and summary.
3. Hash each exact evidence section.
4. Declare stable atoms and unique excerpts.
5. Record relation, resolution, authority, owner, candidate effect, and any
   disposition for every atom.
6. Declare candidate-specific prerequisites and supporting atoms.
7. Derive the candidate status.
8. Write exactly one validated audit payload in its Markdown record.
9. Name the immutable record with its content-hash prefix.
10. Run validation before relying on it.

## Commands

```text
python tools/agent_work_selection_audit.py section-hash --path <path> --heading-line <heading> --commit <commit>
python tools/agent_work_selection_audit.py check --audit <record>
python tools/agent_work_selection_audit.py pilot-check --manifest configs/work_selection_audit_v1.json
```

Corrections create new records that supersede prior payloads. Do not edit an
existing content-addressed audit in place.

## Boundaries

The capability registry remains the machine-readable maturity ledger.
Canonical roadmaps, owner status documents, user approval, and ownership rules
remain independently binding. Audit completeness covers the declared evidence
universe, not every potentially relevant fact.

## Decision Status

Active non-blocking source-evidence protocol. Permanent gating would require a
separate accepted decision and conformance change.
