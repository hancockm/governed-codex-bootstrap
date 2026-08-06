# Vault Information Architecture Standard

The Obsidian vault is the project's maintained narrative reading surface. It
separates canonical decisions, source research, owner continuity, feature
documentation, coordination records, and archives while preserving links and
provenance.

## Narrative Maps Of Content

Every managed area begins at a narrative Map of Content (MOC). A MOC explains
why its children belong together and what order to read them in. It is not a
raw filename listing.

Managed children use one generated block:

```markdown
<!-- managed:moc-children:start -->
- [[path/to/child]] — Narrative description.
<!-- managed:moc-children:end -->
```

Rules:

- canonical prose has one authoritative location;
- every managed child has exactly one managed parent;
- links are vault-relative and path-qualified;
- MOCs do not use transclusion embeds;
- frontmatter, when present, begins at byte zero;
- filenames alone never imply narrative parentage or ownership.

## Breadcrumb Trail

`tools/vault_maintainer.py sync-navigation --apply` owns generated breadcrumb
blocks:

```markdown
<!-- generated:breadcrumbs:start -->
<< Previous: [[...]] | Up: [[...]] | Next: [[...]] >>
<!-- generated:breadcrumbs:end -->
```

The block appears below H1 in managed children. Large files repeat the block
at the footer when required by configuration. Agents may edit MOC order and
descriptions but must not hand-edit generated breadcrumbs.

## Ownership And Rollout

`configs/vault_maintenance_registry_v1.json` declares the vault root, scopes,
owners, rollout state, size budgets, and exceptions.

- `enforced`: structural/navigation errors fail checks;
- `pending_owner_migration`: diagnostics remain visible while the owner
  supplies narrative and accepts parentage;
- `validation_only`: historical material is inspected without semantic
  modernization.

Core owns the registry, standard, and maintainer. Each active owner owns its
narrative, descriptions, and child order. Core does not infer another owner's
meaning during cleanup.

## Canonical And Evidence Areas

- `00_Canonical/`: accepted Thesis, Architecture, Spec, Roadmap, Current State,
  and registry explanation;
- `10_Research/`: immutable source maps and provenance;
- `20_Features/`: owner-specific feature entry points;
- `30_Core/`: Core protocols, bootstrap, and continuity;
- `40_Coordination/`: A2A critique, requests, selection audits, and updates;
- `90_Archive/`: superseded material with provenance.

Research and continuity remain source context. Their presence in the vault
does not grant canonical status.

## Size Budgets

Size diagnostics identify candidates for nested MOCs. They do not authorize an
automatic split. Exceptions require a named owner and rationale and suppress
only size diagnostics—not parent, link, breadcrumb, or transclusion rules.

## Lossless Migration

Destructive heading-based splitting is prohibited. A migration must:

1. identify the exact source blob and SHA-256;
2. validate every source range;
3. write a versioned manifest and destination hashes;
4. reconstruct the original bytes from archived slices;
5. abort without partial replacement on mismatch;
6. provide manifest-based restoration;
7. remain byte-idempotent after navigation synchronization.

Archive slices are rollback material, not current doctrine.

## Agent Continuity Packs

A continuity pack is noncanonical source context for rehydrating an owner.
It records baseline commits and requires live freshness checks against
canonical docs, source, tests, configuration, A2A, and Git history.

Transcript exports preserve exact safe user-visible user/assistant records,
display projections, source-prefix identity, selected-record identity,
redaction counts, and output hashes. They exclude hidden instructions,
reasoning, tool activity, runtime state, and encrypted content. One thread ID
belongs to one owner pack.

## Agent-To-Agent Records

Plan critiques and boundary requests are atomic, schema-versioned records.
Content-addressed names prevent accidental overwrites. Monthly or topic MOCs
index them chronologically while active indexes remain compact. Review agents
edit only assigned records; the owning role maintains indexes and final
dispositions.

## Core Cleanup Protocol

Cross-owner cleanup starts with report/check and classifies each finding as:

- retained;
- reparented;
- archived;
- generated refresh;
- owner handoff;
- blocker.

Never delete solely for cleanliness, infer another owner's narrative, or
rewrite historical meaning. Archive with provenance and update parentage and
navigation atomically.

## Maintainer Commands

```text
python tools/vault_maintainer.py report --scope <scope>
python tools/vault_maintainer.py check --scope <scope>
python tools/vault_maintainer.py sync-navigation --scope <scope>
python tools/vault_maintainer.py sync-navigation --scope <scope> --apply
```

Report, check, and dry sync are read-only. Apply may change only generated
blocks and must validate the complete transaction before replacement.

## Acceptance

A scope is enforceable when:

- every note is reachable from a declared root MOC;
- every managed child has one parent;
- all managed links resolve and are path-qualified;
- narrative order is owner-approved;
- breadcrumbs synchronize and the second dry run is byte-identical;
- MOCs contain no transclusions;
- exceptions are registered with rationale;
- scope check reports zero errors.
