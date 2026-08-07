# Documentation System Parity

This bootstrap preserves the operational behavior of a mature governed
development environment without copying its product doctrine, owner history,
or domain-specific instructions. Equivalence means that a new project can
perform the same authority, planning, implementation, delivery, continuity,
and recovery operations. It does not mean that files must share wording or
line counts with a reference project.

## Parity Classes

- `operational_equivalent`: the same reusable workflow and failure boundaries;
- `generic_adaptation`: the same function with product and owner semantics
  derived later from this project's research and activation records;
- `excluded`: material that would incorrectly import runtime or domain doctrine;
- `future_owner_material`: generated only after Core recognizes and activates
  a separate owner.

[configs/documentation_system_v1.json](../configs/documentation_system_v1.json) makes the first two classes executable
by requiring paths, minimum substantive size, and essential headings.

## Shared Operational Surfaces

| Surface | Required behavior |
| --- | --- |
| Root policy | Decision semantics, planning cutoff, integrated cycles, evidence, testing, orchestration, Git, continuity, UX, and vault rules |
| Git reconciliation | Evidence-only inspection, durable dispositions, Core inbox, safe primary synchronization, worktree cleanup, and recovery |
| Core workflow | Research-first startup, reorientation, canonical promotion, owner boundaries, implementation, delivery, and continuity |
| Owner orchestration | Risk tiers, immutable packets/receipts, one saved-project runner task, correction cycles, publication, and archival |
| Vault standard | Single narrative source, one parent per child, owner-authored MOCs, generated breadcrumbs, validation, and lossless recovery |
| Continuity export | Exact source-prefix selection, redaction, transactional output, ownership, navigation, manifest idempotence, and failure posture |
| Source and feature documentation | Public-contract documentation, package maps, ownership boundaries, cross-owner requests, and executable audit |
| Folder documentation | A local README for every maintained directory, with artifact significance, generated-content posture, and change discipline |
| PowerShell guidance | Safe control-flow pipelines, explicit upstream syntax, literal paths, separate mutations, and exit-code checks |

## Core Continuity Equivalence

The Core continuity system is intentionally more than a transcript directory.
It contains:

1. a complete rehydration prompt with authority order and first-response shape;
2. a Core continuity MOC with one managed parent for each protocol;
3. reorientation and next-step discovery;
4. an assumption audit;
5. canonical-to-runtime reconciliation;
6. continuity maintenance and bounded transcript export;
7. compact subordinate receipts linked without duplicate transcript ownership.

The bootstrap begins with empty domain doctrine. Its Core prompt therefore
routes through research records before canonical documents. This is the
essential adaptation: governance behavior is retained while product truth is
not imported.

## Future Owner Equivalence

A mature repository may contain many owner-specific instruction manuals,
workflows, and continuity packs. Creating those in a generic bootstrap would
grant fictional authority. Instead, [docs/ROLE_BOOTSTRAP_AND_ACTIVATION.md](ROLE_BOOTSTRAP_AND_ACTIVATION.md)
defines the complete dependency architecture for creating them:

```text
recognized boundary
→ inactive owner Core Thesis, Architecture, Spec, and Implementation Roadmap
→ inactive role, bootstrap, profile, continuity, vault, and test assets
→ owner adoption
→ Core integration and activation
→ active owner-specific workflow
```

The inactive template proves the structure without preselecting domains. Its
four owner documents are placeholder-only and non-authorizing until a
recognized owner derives content from project evidence and adopts it.

## Vault README And Instruction Equivalence

The vault provides practical READMEs for its root, canonical, research,
features, Core, Core continuity, coordination, and archive areas. These notes
explain reading order, authority, ownership, maintenance, and recovery while
the MOCs remain the navigable hierarchy.

The vault instruction hub retains reusable behavior for:

- user collaboration and decision semantics;
- frozen-baseline work-selection audits;
- repository-local worktree navigation to the binding root policy;
- Core startup, promotion, integration, and continuity;
- future-owner recognition, adoption, activation, and retirement;
- advisory review and critique;
- owner-scoped development lanes;
- optional external critique handoffs.

Owner-specific manuals and continuity packs are not copied into a clean
bootstrap. They are generated only after activation. Transcript-root and
monthly READMEs are exporter output and therefore appear only after a real
thread is archived. Publication or summary guides remain deferred until their
owners and capabilities exist.

## Deliberate Exclusions

Do not import:

- product package architecture or runtime lifecycle manuals;
- domain-specific parameter, mathematics, provider, or maintenance manuals;
- feature-owner instructions before that owner exists;
- historical continuity transcripts or A2A conclusions;
- paths, branch names, organization names, or artifacts from a reference repo.

Those items must be derived from local research, user approval, and accepted
canonical contracts. Reusable tools are classified independently by
[configs/tool_parity_v1.json](../configs/tool_parity_v1.json).

## Conformance

Run:

```text
python tools/architecture_conformance.py
python -m pytest -q tests/test_conformance.py
```

Conformance fails when a required operational document disappears, collapses
below its substantive floor, loses an essential heading, omits a Core
continuity protocol, loses a required vault README/instruction disposition,
leaves a registered maintained directory undocumented, fails to describe a
registered artifact, or introduces a forbidden project-specific marker.
