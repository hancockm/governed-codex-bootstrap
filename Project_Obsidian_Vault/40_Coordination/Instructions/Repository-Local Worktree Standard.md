# Repository-Local Worktree Standard

<!-- generated:breadcrumbs:start -->
<< Previous: [[40_Coordination/Instructions/Universal Work Selection Audit]] | Up: [[40_Coordination/Instructions/README]] | Next: [[40_Coordination/Instructions/Core Owner]] >>
<!-- generated:breadcrumbs:end -->

## Binding Authority

Root `AGENTS.md` is the sole operational authority for branch creation,
staging, commits, publication, reconciliation, worktree closeout, and primary-
branch synchronization. `docs/GIT_RECONCILIATION.md` is the practical guide.
This vault note is a navigation pointer, not a second policy copy.

## Shared Convention

Normal owner work uses the configured repository-local root:

```text
.worktrees/<owner>-<slice>
```

The primary checkout is reserved for clean Core integration. Temporary tests
and caches use `tmp/`, not worktree names or root-level scratch directories.

## Closeout Principle

A clean and pushed branch is not necessarily landed. Record `landed`,
`superseded`, or `awaiting_named_integrator`; only the first two are terminal.
Worktree deletion requires clean status, no active Git operation, terminal
disposition, verified remote evidence, and exact path containment.

## Safety Boundary

Never remove a worktree to erase uncertain ownership, inspection failure,
unpublished commits, or untracked content. Route other-owner material and
preserve exact evidence until disposition.

## Decision Status

Current navigation summary. Amend binding mechanics only in root `AGENTS.md`.
