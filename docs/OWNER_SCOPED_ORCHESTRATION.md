# Owner-Scoped Development Orchestration

Owner-scoped orchestration is the governed development workflow for every
active owner. It is distinct from any runtime application orchestrator.

## Operating Shape

| Lane | Binding | Responsibility | Repository writes |
| --- | --- | --- | --- |
| Owner Orchestrator | Sol / `xhigh` | Authority, scope, review, publication, continuity | Owner publication and closeout |
| Implementer | Terra / `high` | Packet-bounded implementation and focused checks | Candidate worktree and local commit |
| Verification Runner | Luna / `max` | Independent exact-candidate verification | None |

Bindings are exact and fail-closed. No lane silently substitutes a different
model or reasoning tier. Sol remains user-facing and owns the transcript.
Terra and Luna return bounded receipts without private reasoning or secrets.

## Risk Tiers

The registry deterministically selects:

- `orchestrator_only`: analysis, planning, A2A, continuity, and explicitly
  low-risk noncanonical documentation;
- `orchestrator_plus_implementer`: bounded owner-scoped changes without a
  high-risk trigger;
- `full_team`: runtime behavior, public contracts, canonical doctrine,
  persistence, security/privacy, mathematics, external adapters, migrations,
  user-facing workflows, legal/release work, cross-owner integration, or any
  change requiring the full suite.

Sol may escalate but may not downgrade a triggered tier.

## Work Packet Contract

Each immutable packet binds:

- owner and lane identities;
- task and implementation-cycle IDs;
- user approval reference;
- frozen baseline commit;
- branch and repository-local worktrees;
- authorized and prohibited paths;
- evidence and public dependencies;
- material assumptions and unresolved owner boundaries;
- focused, affected, broad, and final checks;
- Git, continuity, and archival requirements;
- canonical packet hash.

A packet does not expand file ownership. A mismatched packet hash, owner,
task, candidate commit, worktree, or model binding fails closed.

## Packet And Receipt Flow

```text
Sol selects and plans
→ user approval
→ Sol classifies and prepares packet
→ Terra implements and commits locally
→ Sol reviews candidate and receipt
→ Sol binds saved-project Luna task to exact candidate
→ Luna verifies exact candidate
→ Terra corrects failures
→ same Luna task verifies replacement candidate
→ Sol publishes owner branch
→ Core integrates primary branch
→ terminal reconciliation and worktree cleanup
→ Sol records finalization and archives subordinate tasks
→ owner continuity closeout
```

Terra's receipt includes packet hash, candidate commit, changed paths, checks,
and residual issues. Luna's receipt additionally includes runner binding,
environment preflight, exact commands/results, initial/final Git status,
reconciliation evidence, project/task identity, and outcome. A receipt cannot
authorize itself.

## Command Guide

Validate an owner:

```text
python tools/owner_scoped_orchestration.py check-owner --owner <owner> --active
```

Classify and prepare:

```text
python tools/owner_scoped_orchestration.py classify --owner <owner> --description "..." --path <path>
python tools/owner_scoped_orchestration.py prepare --owner <owner> --task-id <id> ...
```

Bind, validate, and record:

```text
python tools/owner_scoped_orchestration.py bind-runner ...
python tools/owner_scoped_orchestration.py validate ...
python tools/owner_scoped_orchestration.py record ...
```

The tool does not invoke models, infer ownership, push branches, integrate the
primary branch, or archive Codex tasks. It validates and records the contract
used by those actions.

## Saved-Project Runner Rule

Luna must operate inside the same saved project so it sees the same repository
and worktree. One runner task ID is reused for all corrections in a cycle.
Creating a new runner task for each retry fragments evidence and leaves stale
active tasks. A projectless task is invalid even when it can read a copied
checkout.

Luna is read-only: it may inspect source/diffs/Git state, run tests, and run
read-only reconciliation checks. It may not edit, stage, commit, push, merge,
rebase, reset, delete, alter the primary branch, or archive itself.

## Correction And Verification

Terra uses focused, cached-failed, affected, and broad profiles. Luna runs the
authoritative full profile once for the final candidate. If full verification
fails, return to serial failed triage, correct the candidate, and reuse Luna.
Do not launch repeated full parallel runs while debugging.

Every replacement candidate receives a new binding and receipt. The previous
receipt remains immutable and is marked superseded through the final bundle.

## Git And Publication

Terra creates a local candidate commit but does not push or integrate. Sol
reviews and publishes the owner branch after accepted verification. Non-Core
owners route `awaiting_named_integrator` to Core. Core alone integrates and
synchronizes the primary branch. Reconciliation remains separate from branch
or worktree deletion.

## Subordinate Task Archival

An accepted Luna receipt is verification evidence, not archival authority.
Sol archives a completed or superseded Terra/Luna task only after all of these
are recorded:

- accepted exact-candidate receipt;
- no correction pending;
- commit, push, and authorized integration;
- primary-branch synchronization;
- terminal branch reconciliation;
- verified worktree cleanup;
- receipt bundle captured in the owner's continuity pack.

Failed, blocked, and user-input-needed tasks remain visible. Keep only the
owner-facing Sol task active after successful closeout.

## Continuity

One continuity pack exists per owner, not per lane. Sol receives the full
thread transcript. Terra/Luna task IDs and compact receipts appear under an
`Orchestration Receipts` section. Do not duplicate full subordinate
transcripts into new continuity ownership.

## Future-Owner Adoption

Before a new owner may use this workflow, Core must:

1. recognize a demonstrated boundary;
2. assign stable owner and Git identities;
3. define branch/worktree namespaces and ownership/non-ownership;
4. create role instructions and bootstrap prompt;
5. initialize continuity, vault scope, tests, and public dependencies;
6. create an inactive owner profile referencing those assets;
7. obtain owner adoption evidence;
8. integrate and activate the registry entry.

A generated template or complete-looking profile is non-authorizing until the
entry is active.
