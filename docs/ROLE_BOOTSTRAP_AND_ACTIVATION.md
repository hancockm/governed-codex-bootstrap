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
3. continuity MOC, protocols, transcript root, and receipt root;
4. owner dependency profile;
5. strict Git branch/worktree namespace;
6. owner-scoped orchestration profile and verification commands;
7. vault scope and narrative parentage;
8. feature/package README and source-documentation entry points;
9. focused and conformance tests;
10. activation and retirement evidence fields.

Assets reference shared instructions rather than copying mutable repository-
wide policy into each role.

## Dependency Architecture

The owner profile records:

```text
owner identity
├── Git identity and namespaces
├── authority and prohibited boundaries
├── owned/consumed capabilities
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
dependency assumptions, and publishes an adoption record. Adoption confirms
the owner accepts its authority, non-ownership, public dependencies,
continuity responsibilities, tests, and Git rules. It does not activate the
profile by itself.

## Core Activation

Core verifies:

- boundary and user/Core recognition evidence;
- complete adopted profile;
- registered continuity/vault assets;
- no private cross-owner dependency;
- exact orchestration bindings and checks;
- conformance tests;
- branch integration and terminal reconciliation.

Core then changes the registry state to `active`, records the activation
commit, and assigns the first bounded task. Until that commit is canonical,
dispatch remains forbidden.

## Retirement

Retirement marks the owner `superseded`, removes dispatch authority, and
preserves canonical history, continuity, A2A records, capability ownership
transfers, and branch evidence. Do not delete an owner pack merely because the
role is inactive.

## Future-Owner Template

`future_owners/owner-template/` demonstrates required shape only. Copying it
does not grant authority. Every filled template must pass the same recognition,
adoption, integration, and activation sequence.
