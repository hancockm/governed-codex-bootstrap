# Source Documentation Style

Use native Python type annotations and concise Google-style docstrings for public modules, APIs, classes, dataclasses, and CLI entry points. Document arguments, returns, raises, state invariants, persistence boundaries, and ownership consequences that are not evident from types. Dataclasses explain semantic fields rather than restating annotations. Public CLIs describe safe defaults, writes, and exit behavior.

For TypeScript, document exported contracts and runtime validation boundaries; for Markdown, document ownership, authority, source status, and links instead of duplicating machine registries. Keep generated, vendored, and private implementation details out of the public audit scope. Run `python tools/source_doc_audit.py`, focused tests, and the vault check before completing source/documentation changes.
