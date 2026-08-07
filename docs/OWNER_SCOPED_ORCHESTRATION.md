# Owner-Scoped Development Orchestration

Owner-scoped orchestration is the governed development workflow for every
active owner. It is distinct from any runtime application orchestrator.

## Operating Shape

| Lane | Binding | Responsibility | Repository writes |
| --- | --- | --- | --- |
| Owner Orchestrator | Sol / `xhigh` | Authority, scope, review, publication, continuity | Owner publication and closeout |
| Implementer | Terra / `high` | Packet-bounded implementation and focused checks | Candidate worktree and local commit |
| Verification Runner | Luna / `xhigh` | Independent exact-candidate verification | None |

Bindings are exact and fail-closed. No lane silently substitutes a different
model or reasoning tier. Sol remains user-facing and owns the transcript.
Terra and Luna return bounded receipts without private reasoning or secrets.

The registry binds one reusable owner-neutral prompt artifact to each lane:

- [roles/shared/OWNER_ORCHESTRATOR_PROMPT.md](../roles/shared/OWNER_ORCHESTRATOR_PROMPT.md) for Sol;
- [roles/shared/IMPLEMENTER_PROMPT.md](../roles/shared/IMPLEMENTER_PROMPT.md) for Terra;
- [roles/shared/VERIFICATION_RUNNER_PROMPT.md](../roles/shared/VERIFICATION_RUNNER_PROMPT.md) for Luna.

Each artifact is composed with the exact owner profile and task packet. It
cannot grant owner-specific authority or weaken repository policy. Missing or
unregistered templates make owner orchestration invalid.

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

A packet does not expand file ownership. Its allowed paths and Terra's actual
changed paths must resolve through [path_ownership_v1.json](../configs/path_ownership_v1.json)
to the active packet owner; unknown, shared/routed, and other-owner paths fail
closed. A branch prefix or owner profile is identity evidence only. A mismatched
packet hash, owner, task, candidate commit, worktree, or model binding fails closed.

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
python tools/owner_scoped_orchestration.py ownership --path <path> [--owner <owner>]
python tools/owner_scoped_orchestration.py prepare --owner <owner> --task-id <id> ...
```

Bind, validate, and record:

```text
python tools/owner_scoped_orchestration.py bind-runner ...
python tools/owner_scoped_orchestration.py validate ...
python tools/owner_scoped_orchestration.py record ...
python tools/owner_scoped_orchestration.py finalize-closeout --packet <packet>.json --implementer-receipt <terra-receipt>.json --runner-binding <binding>.json --runner-receipt <luna-receipt>.json --archive-manifest <recorded-manifest>.json --archive-acknowledgment <sol-acknowledgment>.json --record <recorded-bundle>.json --delivery-evidence <sol-delivery-evidence>.json
```

The tool does not invoke models, infer ownership, push branches, integrate the
primary branch, or archive Codex tasks. It validates and records the contract
used by those actions.

## Saved-Project Runner Rule

Luna must operate in one saved-project reusable chat so it sees the same
repository and worktree. One runner task ID is reused for all corrections in a
cycle, and every continuation explicitly repeats the configured model and
reasoning effort. Creating a projectless task, fork, or replacement runner for
each retry fragments evidence and leaves stale active tasks. A channel or task
identity mismatch is `route_integrity_failed`, not a successful verification.

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

The immutable delivery evidence must bind the exact recorded-bundle hash,
captured lane-receipt hashes, terminal `landed` or authorized `superseded`
reconciliation, verified primary-branch synchronization, and removal of the
packet worktree. The archive acknowledgment binds each packet-assigned
subordinate task ID to `archived` or explicitly `superseded`. Only
`finalize-closeout` can combine those records into the terminal `closed` state.
A recorded receipt, an archive manifest, or an acknowledgment by itself is not
closeout.

Failed, blocked, and user-input-needed tasks remain visible. Keep only the
owner-facing Sol task active after successful closeout.

## Change Notes

The temporary runner-channel rule is recorded in
[runner_channel_workaround_v1.json](../configs/runner_channel_workaround_v1.json).
Its issue watch records [Codex issue 36965](https://github.com/openai/codex/issues/36965)
as `closed_duplicate`, redirecting to [issue 36673](https://github.com/openai/codex/issues/36673)
(`open`, cross-platform advertised-thread handler loss) and
[issue 28080](https://github.com/openai/codex/issues/28080) (`open`, Windows
handler loss). All states were observed on 2026-08-07. Upstream state is not
local resolution: `locally_verified_resolved` remains false because the local
cross-route handler failure is reproducible. Recheck all three upstream issues
and local cross-route handler/model behavior before removing the explicit
model/effort and saved-project-chat workaround.

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
5. create the owner Core Thesis, Architecture, Spec, and Implementation Roadmap;
6. map their exact paths in the owner profile;
7. initialize continuity, vault scope, tests, and public dependencies;
8. create an inactive owner profile with concrete proposed path rules;
9. obtain adoption evidence covering the four documents and owner boundary;
10. add the owner's active path-ownership rules, integrate, and activate the registry entry.

A generated template or complete-looking profile is non-authorizing until the
entry is active.
