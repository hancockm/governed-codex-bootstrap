# Governance tool parity

This bootstrap does not equate a short script with a mature governance tool.
Every Python tool in the reference repository receives one explicit
disposition in [configs/tool_parity_v1.json](../configs/tool_parity_v1.json):

- `full_generic_equivalent` preserves the reusable behavior and callable
  surface while changing only project names, paths, and owner registries.
- `generic_adaptation` preserves the governance purpose but replaces
  product-bound providers or vocabularies with a documented generic contract.
- `project_specific_excluded` identifies product runtime or domain utilities
  that would contaminate a new project bootstrap.
- `bootstrap_native` identifies cold-start and conformance tools that do not
  exist in the mature reference repository.

Run `python tools/tool_parity.py` after adding, removing, or materially changing
a tool. The check fails when any bootstrap tool is unclassified, a declared
counterpart is missing, or any snapshotted top-level function or class
disappears. Full generic equivalents carry the complete reference symbol
inventory, including private transaction, redaction, rendering, and recovery
helpers—not merely their CLI entry point. The manifest is a structural guard,
not proof of semantic equivalence; focused behavior tests remain mandatory for
every full counterpart and adaptation.
