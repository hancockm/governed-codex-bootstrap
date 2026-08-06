# Core Vault Maintenance Protocol

<!-- generated:breadcrumbs:start -->
<< Previous: [[30_Core/Core Protocols]] | Up: [[30_Core/Core MOC]] | Next: [[30_Core/Role Bootstrap and Activation]] >>
<!-- generated:breadcrumbs:end -->

Core performs cleanup only after report and check. It classifies findings as retained, reparented, archived, generated refresh, owner handoff, or blocker; it never infers another owner's narrative, deletes solely for tidiness, or splits headings destructively. Preserve source/history, archive with provenance, update MOC registry and parentage atomically, run breadcrumb dry-run then apply then a second idempotent dry-run, validate every enforced scope, inspect Git diff/status, stage only owned vault changes, and complete continuity closeout.
