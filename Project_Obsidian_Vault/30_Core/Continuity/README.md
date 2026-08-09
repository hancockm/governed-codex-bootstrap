# Core Continuity Guide

<!-- generated:breadcrumbs:start -->
<< Previous: none | Up: [[30_Core/Continuity/Core Continuity MOC]] | Next: [[30_Core/Continuity/Protocols/README]] >>
<!-- generated:breadcrumbs:end -->

Core continuity preserves the bounded evidence needed to resume work. It does
not become a second canonical architecture.

Because the pack is versioned with the repository, an authorized user can
rehydrate Core on another device or in a fresh Codex task. The organization can
also transfer human responsibility for Core while preserving the logical
owner, attributable transcript history, accepted decisions, and unresolved
obligations. The new custodian uses a new task and thread ID in the same Core
pack; a personnel change does not create a second owner archive.

## Components

- the complete Core bootstrap prompt;
- the Core continuity MOC;
- reorientation and next-step discovery;
- assumption audit;
- canonical-to-runtime reconciliation;
- continuity maintenance;
- generated transcript roots and compact orchestration receipts when present.

## Ownership

One task thread belongs to one owner pack. A new owner or role transition uses
a new thread ID. Cross-owner context travels through A2A records and links to
the owning archive, never duplicate exports.

## Export

Use [tools/export_agent_thread_continuity.py](../../../tools/export_agent_thread_continuity.py) with the exact session source,
registered schemas, label, thread ID, output directory, and vault target. Dry-
run, inspect, apply, synchronize navigation, refresh post-navigation hashes,
and require an idempotent dry refresh.

If the exact source is unavailable, record an incomplete closeout. Do not
reconstruct it from memory, summaries, or partial notes.

## Subordinate Receipts

Implementer and verification tasks produce compact packet-bound receipts in
the owning pack. They do not create duplicate continuity owners. Completed or
superseded subordinate tasks are archived only after durable receipt capture,
delivery, terminal reconciliation, and worktree cleanup.

Closeout records both packet-bound Implementer task dispositions. It records
an accepted cumulative Bounded Correction Low receipt when that work occurred.
Otherwise it records the Bounded Correction Low task as unused or Primary-
superseded. The Primary receipt starts from the packet baseline, and an
accepted Bounded Correction Low receipt starts from the accepted Primary
candidate.

Start at [[30_Core/Continuity/Core Continuity MOC]] and open only the
protocol relevant to the present task.
