# Canonical-To-Runtime Reconciliation

<!-- generated:breadcrumbs:start -->
<< Previous: [[30_Core/Continuity/Protocols/Assumption Audit]] | Up: [[30_Core/Continuity/Core Continuity MOC]] | Next: [[30_Core/Continuity/Protocols/Continuity Maintenance Protocol]] >>
<!-- generated:breadcrumbs:end -->

Use this protocol whenever canonical documentation, capability status, source,
tests, configuration, receipts, or Git history appear inconsistent.

## Evidence Order

1. Latest explicit user instruction establishes intent and authorization.
2. Current canonical documents establish accepted doctrine and sequence.
3. Capability records establish declared maturity and required evidence.
4. Source and configuration establish implemented behavior.
5. Tests and receipts establish bounded observed evidence.
6. A2A and continuity explain history but remain non-canonical.

## Reconciliation

Describe each mismatch rather than silently selecting a preferred plane.
Determine whether the smallest correction belongs to runtime, tests,
configuration, canonical documents, capability evidence, or an owner handoff.
Preserve immutable historical decisions and receipts. A documentation update
must not claim runtime behavior that has not been implemented and verified.

If the mismatch affects the selected gate, reopen its plan from a new explicit
baseline. If it is unrelated, record it as a delivery condition or future
owner request without expanding scope.
