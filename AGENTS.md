# Repository governance

This bootstrap begins with one active owner: Core. Research is source evidence, not authority. Canonical documents are current truth only after Core has recorded the supporting research record identifiers and accepted the decision.

Do not activate, assign files to, or export continuity for a future owner until `configs/owners_v1.json` marks it active and its role assets exist. Keep implementation scope inside a validated work packet. Terra may make a candidate; Luna only verifies the SHA-pinned candidate and returns one reusable project-bound receipt; Core alone integrates.

Before a commit, inspect `git status --short`, stage only current-task files, inspect the staged name-status, and run the applicable runner profile. Use `python tools/origin_reconciler.py inspect` before integration and `sync-main` only on a clean primary checkout. Do not use merge, rebase, reset, or deletion as a recovery shortcut.

Temporary output belongs in `tmp/`. The continuity exporter accepts only bounded user/assistant response records and removes credential-shaped fields. Keep runtime dependencies in the standard library; development test dependencies are pinned in `pyproject.toml` and recorded under `third_party/`.
