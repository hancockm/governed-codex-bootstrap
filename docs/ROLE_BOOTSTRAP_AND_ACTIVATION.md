# Role Bootstrap And Activation

Core alone recognizes and activates a separate owner. Role creation is an
authority-bearing dependency decision, not safe boilerplate generation.

## Lifecycle States

- `proposed`: a possible boundary with no authority;
- `recognized_inactive`: Core accepts the boundary shape;
- `owner_adoption_required`: assets exist and await owner acceptance;
- `active`: registry prerequisites and integration evidence permit dispatch;
- `superseded`: authority is retired while provenance remains.

Only `active` is dispatch-authorized. A complete-looking scaffold remains
inactive until explicit adoption and Core activation.

## Boundary Recognition

Start from a demonstrated need that cannot be cleanly owned by an existing
role. Record:

- the user/Core recognition decision;
- stable owner ID and separate Git owner identity;
- branch namespace and repository-local worktree prefix;
- owned files, decisions, capabilities, and maturity claims;
- explicit non-ownership;
- public upstream contracts and owners;
- downstream consumers;
- cross-owner requests and escalation path.

An owner consumes public contracts. It must not depend on another owner's
private implementation.

## Required Assets

Core supplies an inactive, connected set:

1. role instruction document;
2. bootstrap prompt with exact startup order;
3. owner Core Thesis, Architecture, Spec, and Implementation Roadmap;
4. continuity MOC, protocols, transcript root, and receipt root;
5. owner dependency profile with exact canonical-document paths;
6. strict Git branch/worktree namespace;
7. owner-scoped orchestration profile and verification commands;
8. concrete proposed path rules in the owner profile;
8. vault scope and narrative parentage;
9. feature/package README and source-documentation entry points;
10. focused and conformance tests;
11. activation and retirement evidence fields.

Assets reference shared instructions rather than copying mutable repository-
wide policy into each role.

## Core Scaffold And User Handoff

After the user approves the owner-boundary plan, Core creates the complete
inactive scaffold. Core registers the proposed identity and namespaces,
connects the role and bootstrap, creates the four owner canonical documents,
maps their exact paths in the dependency profile, establishes exactly one
continuity pack, binds the shared orchestration prompts, records public
dependencies and non-ownership, adds focused/conformance tests, and publishes
an adoption A2A.

The owner's **Core Thesis** states why that owner exists and its governing
claims; it does not grant project-wide Core authority. **Architecture** fixes
the owner's components, dependency direction, and boundaries. **Spec** defines
observable contracts and invariants. **Implementation Roadmap** sequences
authorized capability gates and acceptance evidence. Before activation these
documents are candidate, non-authorizing doctrine. After activation the owner
maintains their meaning within its scope, while project-wide conflicts return
to Core for disposition.

Core then returns the scaffold paths, validation and Git evidence, unresolved
questions, and a complete fresh-task prompt. The prompt identifies the role as
proposed and inactive, supplies the exact reading order, requires an authority
and dependency audit as the first response, and prohibits feature
implementation before activation.

The user starts a separate Codex task with that prompt. Core must not operate
the new role inside the Core task, and the new task must not infer active
authority from the scaffold's completeness.

## Dependency Architecture

The owner profile records:

```text
owner identity
├── Git identity and namespaces
├── authority and prohibited boundaries
├── owned/consumed capabilities
├── owner canonical quartet and exact paths
├── public upstream contracts
├── downstream consumers
├── continuity ownership
├── orchestration lanes and checks
└── activation/retirement evidence
```

Core validates uniqueness of owner IDs, Git owners, branch prefixes, and
worktree prefixes. Nested or overlapping namespaces require an explicit,
validated parent/child design; accidental overlap fails closed.

## Owner Adoption

The proposed owner reads the role/bootstrap/profile, challenges ownership and
dependency assumptions, reconciles all four owner canonical documents, and
publishes an adoption record. Adoption confirms the owner accepts its thesis,
architecture, spec, implementation sequence, authority, non-ownership, public
dependencies, continuity responsibilities, tests, and Git rules. It does not
activate the profile by itself.

## First Owner Task

The first task is adoption-only. The proposed owner verifies current canonical
and runtime evidence, challenges the four owner documents, overlaps, and
private dependencies, confirms Git and continuity uniqueness, and reports
whether it accepts the boundary.
After user approval, it publishes only adoption records and authorized
corrections on its registered adoption branch. It remains inactive while Core
integrates and validates that branch.

## Core Activation

Core verifies:

- boundary and user/Core recognition evidence;
- complete adopted profile;
- all four mapped owner canonical documents exist and were adopted;
- registered continuity/vault assets;
- no private cross-owner dependency;
- exact orchestration bindings and checks;
- conformance tests;
- branch integration and terminal reconciliation.

Core then adds the owner to the active path-ownership registry, changes the registry state to `active`, records the activation
commit, and assigns the first bounded task. Until that commit is canonical,
dispatch remains forbidden.

## Retirement

Retirement marks the owner `superseded`, removes dispatch authority, and
preserves canonical history, continuity, A2A records, capability ownership
transfers, and branch evidence. Do not delete an owner pack merely because the
role is inactive.

## Future-Owner Template

[future_owners/owner-template/](../future_owners/owner-template) demonstrates required shape only. Copying it
does not grant authority. Every filled template must pass the same recognition,
adoption, integration, and activation sequence.

The complete operator walkthrough and reusable first-task prompt are in
[docs/SYSTEM_USER_GUIDE.md](SYSTEM_USER_GUIDE.md) under "Create And Activate A New Owner."
