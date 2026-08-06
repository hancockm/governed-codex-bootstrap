# Source Documentation Style

Use native Python type annotations and concise Google-style docstrings for public functions, classes, and modules when they clarify contracts. Document arguments, returns, raises, and invariants that are not evident from types. Keep generated, vendored, and private implementation details out of the public audit scope. Run `python tools/source_doc_audit.py` before completing source changes.
