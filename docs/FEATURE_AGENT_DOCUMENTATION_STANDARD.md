# Feature Agent Documentation Standard

Every active feature package must match Core's operational documentation
quality. Independent ownership does not permit undocumented imports,
boundaries, maturity, or verification.

## Required Pre-Work

Before planning or implementation, inspect:

- root `AGENTS.md`;
- the comparable Core/package README pattern;
- `docs/SOURCE_DOCUMENTATION_STYLE.md`;
- `docs/VAULT_INFORMATION_ARCHITECTURE_STANDARD.md`;
- the feature README and vault MOC;
- the active owner's role, bootstrap, continuity MOC, and profile;
- public upstream contracts and relevant A2A requests.

If the feature README lacks the required shape, repair it before adding more
feature source.

## README Shape

An active feature README includes:

- H1 feature/package name;
- lifecycle and implementation status;
- purpose and ordinary-user outcome;
- owner and decision authority;
- explicit non-ownership;
- folder/module map;
- canonical public imports or API entry points;
- consumed Core/public contracts;
- persistence/external-service boundaries;
- focused and broader test commands;
- links to feature vault, role, bootstrap, and A2A material.

Future stubs may be shorter but must remain explicitly inactive and
non-authorizing.

## Source Docstrings

Feature source follows the same public-docstring requirements as Core. Types
carry shape; docstrings explain behavior, ownership, redaction, failure, and
edge cases. Run `python tools/source_doc_audit.py` and add focused tests for new
public boundaries.

## Boundary Discipline

Feature owners consume public contracts. They do not import another owner's
private implementation or reimplement shared routing, persistence semantics,
authority, audit, or canonical schemas. A missing field, receipt, view, or port
becomes an A2A boundary request.

Documentation must state what the feature consumes, owns, and explicitly does
not own. It must distinguish implemented behavior from proposed or deferred
work.

## Feature Vault Maps

Each feature owner writes its narrative MOC, child descriptions, and order in
its registered scope. Use the managed child-block and breadcrumb grammar from
the vault standard. Do not infer narrative from filenames. Historical scopes
remain validation-only unless the owner authorizes migration.

A feature scope becomes enforced only after unique parentage, path-qualified
links, synchronized navigation, owner-approved narrative, and a clean scope
check.

## Activation And Retirement

A feature scaffold does not activate an owner. Core must integrate adopted
role/profile/continuity evidence and mark the owner active. Retirement marks
the owner or feature superseded while preserving canonical history,
continuity, A2A dispositions, and branch evidence.
