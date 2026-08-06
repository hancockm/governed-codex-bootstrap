# Core Vault Maintenance Protocol

<!-- generated:breadcrumbs:start -->
<< Previous: [[30_Core/Core Protocols]] | Up: [[30_Core/Core MOC]] | Next: [[30_Core/Role Bootstrap and Activation]] >>
<!-- generated:breadcrumbs:end -->

Core performs cleanup only after report and check. The complete procedure lives
in `docs/CORE_VAULT_MAINTENANCE_PROTOCOL.md`.

Classify every finding as retained, reparented, archived, generated refresh,
owner handoff, or blocker. Never infer another owner's narrative, delete solely
for tidiness, or split headings destructively. Preserve source and history,
archive with provenance, and update MOC parentage atomically.

Run breadcrumb dry-run, apply, and a second idempotent dry-run. Validate every
enforced scope, inspect Git diff and status, stage only Core-owned vault
changes, and complete continuity closeout. Generated breadcrumb and transcript
content is tool-owned and must not be hand-edited.
