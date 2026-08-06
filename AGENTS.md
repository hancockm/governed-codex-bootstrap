# Repository governance

## Authority, evidence, and ownership

The user authorizes goals and material scope changes. Core is the sole active initial owner: it controls canonicalization, future-owner activation, primary-branch integration, and the owning continuity pack. Research records are immutable source evidence, never canonical truth. Core promotes a reviewed claim only by recording its evidence, decision, canonical wording, and verification witness.

An owner may change only its active, registered scope. Exploration, a critique, an attached transcript, or a proposed architecture does not grant implementation authority. Resolve ownership conflicts through a coordination record; do not create a parallel contract, parser, ledger, or store to bypass an existing boundary.

## Planning and coordination

For substantial planning, freeze selection evidence at the first inspected repository state. Separate selection evidence (canonical contracts, owner scope, prerequisites, tests) from later delivery conditions (unrelated worktree changes or generated output). Record material assumptions and reopen a decision only when the selected work or a material prerequisite changes.

Publish A2A work in `coordination/` as a bounded convergence record: common agreement, all remaining disagreements, critical weak points, convergence move, and decision status. Each substantive point receives an explicit disposition. Core alone promotes accepted conclusions to canonical documents.

## Integrated delivery lanes

Sol classifies risk and publishes a packet. Terra performs only the packet's bounded work, runs the required test profiles, and may create a candidate commit. Luna validates the exact candidate and never commits, pushes, integrates, resets, rebases, or deletes. A Luna task must be created in the saved project, one task identifier is reused for every correction/reverification in the implementation cycle, and a projectless task is invalid.

Luna's accepted receipt is not archival acknowledgment. Sol alone creates the separate subordinate archive/finalization record after the accepted exact-candidate receipt, no correction remains, delivery and integration are complete, primary synchronization and terminal reconciliation pass, and worktree cleanup is confirmed. Failed, blocked, and user-input-needed tasks remain visible.

## Testing and temporary artifacts

Use `tools/test_runner.py focused <targets>` for one surface; `failed` for cached failures only; `affected --base <ref>` for fail-closed impact selection; `broad` for the mapped regression boundary; and `full` once for final parallel-safe then serial execution. Keep lifecycle options out of global pytest options. Parallel-safe tests run with at most four workers; shared repositories, services, fixed ports, mutable process environment, and shared storage are serial.

All scratch data, pytest cache, and temporary test output belong under `tmp/`. Remove task-specific temporary output before closeout, or identify the exact retained path and recovery action.

## Git, worktrees, and reconciliation

Inspect `git status --short` before staging. Stage only current-task files, inspect staged name-status, and do not absorb concurrent or unowned changes. Core alone may run `python tools/origin_reconciler.py sync-main --agent core`; it requires a clean primary checkout, no active Git operation, no local-only commits, a resolvable remote primary branch, and uses only `fetch` plus `merge --ff-only`. It never switches branches, resets, rebases, discards, or deletes.

Before a remote exists, affected comparison and primary synchronization fail closed. A branch is complete only when it is terminally landed or explicitly superseded by an authorized owner; a named integrator request is visible, not terminal.

## Continuity

One source thread belongs to one continuity owner. Export only a stable full-line source prefix containing user/assistant response records; exclude private records, tools, and credential-shaped content. Store source-prefix and selected-record hashes, make exports idempotent, and never reconstruct unavailable source history from summaries. Terra and Luna provide receipts in Core's pack and do not become separate continuity owners.
