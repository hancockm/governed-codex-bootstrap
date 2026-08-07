# Core Agent Workflow

This is the single-owner workflow for the project's initial Core owner. Core
owns canonical promotion, shared governance substrate, future-owner
activation, primary-branch integration, and its continuity pack. Product and
domain authority must be derived from this project's evidence.

## Required Starting Points

Before planning or implementation, read in this order:

1. root [AGENTS.md](../AGENTS.md);
2. [roles/core/ROLE.md](../roles/core/ROLE.md) and [roles/core/BOOTSTRAP.md](../roles/core/BOOTSTRAP.md);
3. [Project_Obsidian_Vault/30_Core/Core Bootstrap.md](../Project_Obsidian_Vault/30_Core/Core%20Bootstrap.md);
4. [Project_Obsidian_Vault/30_Core/Continuity/Core Continuity MOC.md](../Project_Obsidian_Vault/30_Core/Continuity/Core%20Continuity%20MOC.md) and its
   relevant protocols;
5. [Project_Obsidian_Vault/00_Home/Project MOC.md](../Project_Obsidian_Vault/00_Home/Project%20MOC.md);
6. [Project_Obsidian_Vault/10_Research/Research Sources MOC.md](../Project_Obsidian_Vault/10_Research/Research%20Sources%20MOC.md);
7. the current canonical Thesis, Architecture, Spec, Roadmap, Current State,
   and capability registry;
8. the coordination MOC, update log, and only relevant open records;
9. current source, tests, configuration, receipts, Git status, recent commits,
   and changes since relevant continuity baselines.

Continuity baselines are freshness markers, not authority. Reclassify current
maturity from the live repository.

## Outstanding Issue Triage

Do not treat the roadmap or latest coordination entry as a complete queue.
For every relevant open request, record one disposition:

- `owned by Core`;
- `owned by another owner`;
- `already satisfied`;
- `deferred`;
- `blocked`;
- `requires user approval`.

Run the Core integration inbox before selecting a new gate. A published branch
is not an accepted request merely because it exists. Read its owner-authored
disposition and inspect exact commits.

## Research-First Canonicalization

Core starts without inferred domain doctrine. Preserve original research in
the source lane, organize it without promotion, compare agreement and
conflict, and write only explicitly supported decisions into the canonical
vault. For each promotion, retain:

- exact research/provenance references;
- unresolved uncertainty and counterevidence;
- user/Core disposition;
- canonical wording;
- verification witness and capability state.

Research records, organizer candidates, A2A critiques, and transcripts remain
evidence. They never become canonical by location or repetition.

For a public Git research source, require a credential-free HTTPS URL,
explicit branch or tag ref, full expected commit, and user-authorized network
acquisition. Use the bounded adapter rather than a working-tree clone. Preserve
commit, tree, blob, file-hash, path, selection-limit, and omission evidence;
never execute repository code or infer that capture grants reuse rights.

## Reorientation And Next-Step Discovery

For a next-step request:

1. freeze the first inspected baseline;
2. inspect relevant continuity and canonical maps;
3. reconcile canonical statements with source/tests/configuration;
4. classify capabilities as proposed, partial, implemented, verified,
   deferred, superseded, or owner-dependent;
5. build an assumption ledger: verified, invalidated, unverified, and
   owner-disposition-required;
6. test whether prerequisites are already satisfied or reordered;
7. identify the smallest unblocked Core-owned gate;
8. distinguish a planning prerequisite from the implementation target;
9. create the work-selection audit and relevant critique handoff;
10. present an approval-ready plan without implementing it.

Do not repeatedly rescan unrelated repository churn after the conclusion is
stable. Reopen only for a material change.

## Canonical Doc Sync

Every substantial Core plan records whether accepted convergence changes:

- Thesis: project purpose or governing claims;
- Architecture: components, ownership, or dependency direction;
- Spec: observable contracts and invariants;
- Roadmap: sequencing and acceptance gates;
- Current State/capability registry: implemented maturity and evidence;
- none, with a reason.

External critique never promotes itself. Documentation must describe actual
behavior and must not claim maturity that tests or source do not establish.

## Boundary Filter Before Action

Before editing, answer:

- Is this change within Core's registered paths and decisions?
- Does it alter another owner's semantics, UI, source selection, legal
  position, audit conclusion, governance decision, or narrative?
- Can the need be met through an existing public contract?
- Does a missing cross-owner boundary require A2A first?
- Would the proposed change create a second schema, ledger, parser, store, or
  authority for an existing concept?

Core may publish neutral contracts and boundary stubs. It must not implement a
future owner's private semantics merely to unblock the project.

## Implementation Routine

After explicit approval:

1. synchronize a clean primary checkout and verify the Core inbox;
2. create a repository-local Core worktree from current remote primary;
3. classify risk and create the immutable Sol packet;
4. have Terra implement only the allowed paths and focused checks;
5. review the candidate diff and receipt;
6. bind Luna to the exact candidate in the saved project;
7. run full verification once when required;
8. return failures to Terra and reuse the same Luna task;
9. update source docs, canonical docs, registry, A2A records, and navigation in
   the same cycle;
10. integrate through Core, prove terminal reconciliation, synchronize the
    primary checkout, and clear the inbox;
11. export continuity, validate it, and archive accepted/superseded
    subordinate tasks after cleanup.

Use focused, failed, affected, and broad testing during iteration. Do not use
repeated full-suite runs as a debugger.

## Primary Master Synchronization

At Core startup and closeout:

```text
python tools/origin_reconciler.py inspect --agent core
python tools/origin_reconciler.py inbox --agent core
```

When safe:

```text
python tools/origin_reconciler.py sync-main --agent core
```

Never force synchronization through dirty, divergent, detached, local-only,
or active-operation state. After every Core integration push, the cycle is
incomplete until local primary equals remote primary and the inbox is clear.

## Vault Maintenance Boundary

Core maintains vault structure, registry, and generated navigation. Other
owners maintain their meaning and narrative order. Cross-owner cleanup begins
with report/check and routes owner semantics rather than guessing them. Follow
[docs/CORE_VAULT_MAINTENANCE_PROTOCOL.md](CORE_VAULT_MAINTENANCE_PROTOCOL.md).

## Average-user UX Gate

For user-facing changes, record the primary user outcome and shortest safe
path. Verify plain-language labels, input preservation, actionable errors,
keyboard/focus behavior, responsive rendering, zoom, reduced motion, and
explicit empty/unavailable/denied/degraded states. Expert controls must remain
secondary.

## Continuity Closeout

Follow [docs/AGENT_CONTINUITY_EXPORT.md](AGENT_CONTINUITY_EXPORT.md) and the continuity maintenance
protocol. Export the exact current session source, synchronize navigation,
refresh the post-navigation manifest, require idempotence, validate the scope,
stage only Core-owned archive files, and push the closeout. Do not reconstruct
missing history or duplicate another owner's thread.

## Definition Of Complete

Core work is complete only when:

- accepted scope and acceptance conditions are satisfied;
- focused and risk-proportionate broad checks pass;
- source/canonical/registry evidence is synchronized;
- owner handoffs are durable and visible;
- intended commits are integrated or explicitly superseded;
- primary checkout equals remote primary;
- Core inbox is clear or parallel work is explicitly authorized;
- temporary worktrees are removed safely;
- continuity export and manifest validation are complete.

Reporting a blocker does not convert an incomplete closeout into completion.
