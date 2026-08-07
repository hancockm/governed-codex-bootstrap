# Source Documentation Style

Project-owned source uses native type annotations plus Google-style
docstrings. Types carry formal shape; docstrings explain intent, behavior,
boundaries, failure modes, and non-obvious edge cases.

## Core Rule

When behavior is important enough to explain in a plan, review, README, or
user-facing response, the public source boundary should carry the essential
explanation. Markdown orients readers; source-adjacent docstrings remain the
first operational contract.

Run:

```text
python tools/source_doc_audit.py
```

The default audit covers project source and reusable tools. Public modules,
classes, functions, dataclasses, protocols, command entry points, and methods
require docstrings. Private helpers may omit them when names and local context
are sufficient.

## Python Docstrings

Use Google-style sections when useful:

- `Args:` for public functions, adapters, commands, and multi-parameter APIs;
- `Returns:` when the result is not obvious;
- `Raises:` for expected caller-visible errors;
- `Attributes:` for public record fields;
- `Examples:` for reusable operator flows.

Do not duplicate type names already present in signatures.

```python
def resolve_record(record_id: str, version: str | None = None) -> Record:
    """Resolve one immutable record from configured storage.

    Args:
        record_id: Stable public record identity.
        version: Optional exact version override.

    Returns:
        The verified record selected by the request.

    Raises:
        RecordError: If the record is absent or fails integrity checks.
    """
```

## Module Docstrings

Every non-test Python module begins with a short purpose docstring. CLI modules
also state whether they read or write repository state, use network services,
and how secrets are loaded/redacted.

## Dataclasses And Protocols

Document what the record or port represents, not merely its field types. Use
`Attributes:` when fields carry public semantics, authority, redaction, or
lineage. Protocol docstrings state the business operation and atomicity
requirements rather than exposing adapter internals.

## CLI Programs

CLI documentation states:

- what is inspected or changed;
- common commands;
- exit-code meanings;
- network/external-service posture;
- secret and payload handling;
- dry-run versus apply behavior;
- recovery expectations after failure.

Use argparse help plus a sibling Markdown guide for repeated operator flows.

## JavaScript Or TypeScript

Use TypeScript signatures for shape and JSDoc/TSDoc for purpose and behavior.
Document exported components, hooks, utilities, state transitions, and errors.
Do not repeat obvious primitive types in prose.

## Markdown Docs

Markdown requires a clear H1, purpose, concrete commands/configuration for
operator procedures, nearby source links when useful, and no real secrets.
Operational documents must include failure and recovery behavior rather than
only a happy-path summary.

Feature READMEs additionally follow
[docs/FEATURE_AGENT_DOCUMENTATION_STANDARD.md](FEATURE_AGENT_DOCUMENTATION_STANDARD.md).

## Boundaries

- Do not rewrite vendored or generated code solely for style.
- Never document or commit real credentials.
- Prefer docstrings over comments for public contracts.
- Use comments sparingly for local implementation constraints.
- Keep examples project-neutral unless the owning feature deliberately
  supplies domain fixtures.
