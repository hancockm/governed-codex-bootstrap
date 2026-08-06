# Assumption Audit

<!-- generated:breadcrumbs:start -->
<< Previous: [[30_Core/Continuity/Protocols/Reorientation And Next-Step Discovery]] | Up: [[30_Core/Continuity/Core Continuity MOC]] | Next: [[30_Core/Continuity/Protocols/Canonical-To-Runtime Reconciliation]] >>
<!-- generated:breadcrumbs:end -->

Before sequencing substantial work, classify every material assumption.

## Classes

- `verified`: current repository evidence directly supports it;
- `invalidated`: current evidence contradicts it;
- `unverified`: plausible but not established;
- `owner_disposition_required`: another owner or the user must decide it;
- `deferred`: explicitly outside the selected gate.

## Required Questions

- Has a recent implementation already satisfied or reordered this work?
- Is the presumed dependency a public contract or a private implementation?
- Does canonical maturity match source and test evidence?
- Does a diagnostic or passive receipt get mistaken for execution authority?
- Would the plan silently change ownership, security, licensing, data egress,
  irreversible state, or user-visible behavior?
- Is a future profile, threshold, schema, or provider being treated as active?
- Is an unrelated dirty worktree being mistaken for planning evidence?

Record evidence references and the consequence of each answer. Do not fill an
unverified material assumption with confidence. Route owner-dependent items
through A2A and stop only when the unresolved choice changes the authorized
result.
