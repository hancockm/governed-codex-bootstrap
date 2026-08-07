# Owner-Scoped Development Lanes

<!-- generated:breadcrumbs:start -->
<< Previous: [[40_Coordination/Instructions/Review And Critique Agent]] | Up: [[40_Coordination/Instructions/README]] | Next: [[40_Coordination/Instructions/External Critique Handoff]] >>
<!-- generated:breadcrumbs:end -->

## Team

- Owner Orchestrator: authority, scope, review, publication, continuity;
- Implementer: packet-bounded candidate and focused verification;
- Verification Runner: independent read-only verification of the exact
  candidate commit.

All lanes inherit the active owner's authority. No subordinate lane can widen
paths, decisions, or cross-owner scope.

## Packet And Receipts

The immutable packet binds owner, task, approval, baseline, worktree, allowed
and prohibited paths, evidence, acceptance, checks, Git, and continuity. The
implementation receipt binds the packet and candidate. The verification
receipt binds the exact candidate and environment.

## Correction Cycle

Use one saved-project verification task throughout a cycle. Failed verification
returns to the implementer; reverification uses the same task and a new exact
candidate. Do not create accumulating runner tasks for each correction.

## Publication And Archive

Only the Owner Orchestrator publishes. Core alone integrates primary. Archive
accepted or superseded subordinate tasks only after receipt capture, no pending
correction, delivery, primary synchronization, terminal reconciliation, and
worktree cleanup. Keep blocked or user-input-needed tasks visible.

The binding procedure is [docs/OWNER_SCOPED_ORCHESTRATION.md](../../../docs/OWNER_SCOPED_ORCHESTRATION.md) and the machine
contract is [configs/owner_scoped_orchestration_v1.json](../../../configs/owner_scoped_orchestration_v1.json).
