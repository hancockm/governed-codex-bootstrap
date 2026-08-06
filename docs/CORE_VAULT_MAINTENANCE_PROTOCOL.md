# Core Vault Maintenance Protocol

Only Core performs cross-owner vault cleanup. Begin with `vault_maintainer.py report` and `check`; classify each item as orphaned, unregistered, stale, generated, oversized, or broken-link. Use one disposition: `retained`, `reparented`, `archived`, `generated_refresh`, `owner_handoff`, or `blocker`. Never infer another owner's narrative, delete solely for cleanliness, split headings destructively, or lose source/history. Archive with provenance.

For an accepted Core cleanup, update MOC links, registry parentage, and archive provenance atomically. Run breadcrumb sync dry-run, apply only generated blocks, then a second dry-run that must be idempotent. Validate all enforced scopes, inspect Git diff/status, stage only Core-owned vault files, and complete continuity closeout. Unsupported recovery extensions remain explicit blockers or owner handoffs.
