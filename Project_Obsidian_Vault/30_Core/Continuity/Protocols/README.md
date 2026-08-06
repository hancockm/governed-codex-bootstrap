# Core Continuity Protocols

<!-- generated:breadcrumbs:start -->
<< Previous: [[30_Core/Continuity/README]] | Up: [[30_Core/Continuity/Core Continuity MOC]] | Next: [[30_Core/Continuity/Protocols/Reorientation And Next-Step Discovery]] >>
<!-- generated:breadcrumbs:end -->

## Purpose

This directory contains reusable Core rehydration and closeout procedures.
They guide evidence review but do not override current canonical or runtime
facts.

## Contents

- `Reorientation And Next-Step Discovery.md` governs cold-start evidence and
  bounded next-step selection.
- `Assumption Audit.md` classifies verified, invalidated, unverified, and
  owner-dependent assumptions.
- `Canonical-To-Runtime Reconciliation.md` compares doctrine with source,
  tests, configuration, Git, and receipts.
- `Continuity Maintenance Protocol.md` governs transcript export, navigation,
  manifest refresh, and closeout.

## Change Discipline

Each protocol has one parent in the Core Continuity MOC. Preserve its scope,
update affected navigation through the maintainer, and never treat historical
continuity as stronger than current evidence.
