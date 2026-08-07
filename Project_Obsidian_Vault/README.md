```
# Governed Project Vault Guide
```

This Obsidian vault is the maintained narrative reading surface for the
project. It connects research evidence, current canonical decisions, feature
boundaries, Core protocols, cross-owner coordination, continuity, and
historical archives without collapsing them into one authority level.

## Start Here

New operators should first read the repository-level
[System User Guide](../docs/SYSTEM_USER_GUIDE.md) for Codex project setup,
task closeout, continuity rehydration, and the architectural rationale.

1. Open [[00_Home/Project MOC]].
2. Read [[10_Research/Research Sources MOC]] before accepting derived
   canonical claims.
3. Read [[00_Canonical/Canonical MOC]] for current accepted doctrine.
4. Use [[30_Core/Core MOC]] for Core authority and operating protocols.
5. Use [[40_Coordination/Agent-to-Agent Discussions MOC]] for active
   requests, critiques, and dispositions.
6. Open feature or continuity areas only when the task requires them.

Do not traverse every transcript or archive by default. Read MOCs first, then
only the linked source needed for the current decision.

## Authority Layers

| Area | Meaning |
| --- | --- |
| Research | Preserved source material and review evidence; never self-promoting |
| Canonical | Current accepted Thesis, Architecture, Spec, Roadmap, and capability state |
| Features | Owner-scoped product or domain material after recognition and activation |
| Core | Shared authority, activation, delivery, maintenance, and continuity protocols |
| Coordination | Advisory requests, critique, audit, handoff, and disposition records |
| Continuity | Bounded owner-attributed transcript and receipt history |
| Archive | Superseded or closed material retained with provenance |

The latest explicit user instruction controls intent and authorization.
Canonical documents control accepted doctrine. Source, tests, configuration,
receipts, and Git history establish implemented behavior. Coordination and
continuity explain history but do not become canonical merely by existing.

## Maintained And Generated Content

Owners write narrative MOCs, summaries, decisions, and descriptions.
[tools/vault_maintainer.py](../tools/vault_maintainer.py) owns breadcrumb blocks. Transcript exporters and
coordination tools own their generated records and indexes. Never hand-edit a
generated transcript, receipt bundle, breadcrumb, or output inventory.

Every managed child has one parent. A concept has one canonical prose
location. Links are path-qualified when names could collide. Archives remain
discoverable from current narrative rather than becoming an unindexed dump.

## Owner Instructions

Shared owner instructions live at
[[40_Coordination/Instructions/README]]. Root [AGENTS.md](../AGENTS.md) remains the sole
repository-wide operational authority. Owner instructions narrow scope and
startup order but cannot weaken shared Git, continuity, safety, evidence, or
verification rules.

Only Core is active in a new bootstrap. Future owner material remains a
non-authorizing template until recognition, adoption, integration, and a Core
activation commit are complete.

## Maintenance

Use:

```text
python tools/vault_maintainer.py report --scope project
python tools/vault_maintainer.py check --scope project
python tools/vault_maintainer.py sync-navigation --scope project
python tools/vault_maintainer.py sync-navigation --scope project --apply
```

Always dry-run navigation before apply, run a second idempotent dry-run, then
validate the scope. Cleanup follows [docs/CORE_VAULT_MAINTENANCE_PROTOCOL.md](../docs/CORE_VAULT_MAINTENANCE_PROTOCOL.md).

## Recovery

Do not repair missing history from memory. Preserve the exact source, use the
registered restoration or exporter tool, validate hashes and parentage, and
record any unresolved source gap. A cleaner-looking vault is not worth losing
provenance or inventing continuity.
