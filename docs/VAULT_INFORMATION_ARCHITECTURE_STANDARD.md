# Vault Information Architecture Standard

The maintained vault is a narrative navigation surface. Canonical narrative documents live only under `Project_Obsidian_Vault/00_Canonical/`; machine registries live in `configs/` and are linked by reference rather than copied into prose. Every managed note has exactly one registered parent except the root MOC. Links are path-qualified, transclusions are prohibited, generated breadcrumbs are owned only by the maintainer, and oversized notes are diagnostics rather than automatic split targets.

Managed breadcrumb grammar is `<!-- generated:breadcrumbs:start -->`, one path-qualified parent link, then `<!-- generated:breadcrumbs:end -->`. The bootstrap currently generates an up/parent breadcrumb; previous/next sequencing and large-scale migrations are deferred recovery extensions, not silently simulated behavior. Dynamic A2A records live only in the registered generated coordination scope. Continuity packs, A2A records, and archives preserve provenance. Migrations are lossless: never delete merely for cleanup or split headings destructively; archive with provenance and update parentage/MOCs atomically.

Run `vault_maintainer.py report`, `check`, then `sync-navigation` dry-run before `sync-navigation --apply`. The tool fails closed when registry, parentage, links, or non-generated content are unsafe.

Acceptance is report/check clean, dry-run reviewed, apply limited to generated blocks, second dry-run idempotent, source-doc audit/conformance passing, and a scoped Git diff. See the Core vault maintenance protocol for cleanup dispositions.
