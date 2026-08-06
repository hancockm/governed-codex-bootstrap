# Core Vault Maintenance Protocol

Core alone performs cross-owner vault cleanup. Structural authority does not
grant authority over another owner's meaning.

## Preflight

1. inspect repository and worktree status;
2. run `vault_maintainer.py report` for the affected scopes;
3. run `vault_maintainer.py check` without mutation;
4. identify each finding's owner and rollout state;
5. freeze the source paths and hashes for any migration.

Treat a failed check command as inspection failure, not evidence that a scope
is clean.

## Finding Classification

Classify every item as orphaned, unregistered, stale, generated, oversized,
broken-link, duplicate-parent, or ownership-ambiguous. Give it one disposition:

- `retained`;
- `reparented`;
- `archived`;
- `generated_refresh`;
- `owner_handoff`;
- `blocker`.

Do not delete solely for tidiness, infer a narrative from filenames, edit
another owner's doctrine, or split headings destructively.

## Safe Mutation

For accepted Core-owned cleanup, update parent MOC links, registry parentage,
archive provenance, and generated navigation as one bounded change. Preserve
source/history and use lossless migration manifests for structural splits.

Navigation sequence:

```text
python tools/vault_maintainer.py sync-navigation --scope <scope>
python tools/vault_maintainer.py sync-navigation --scope <scope> --apply
python tools/vault_maintainer.py sync-navigation --scope <scope>
```

The final dry-run must report no change. Hand-editing generated blocks is
prohibited.

## Cross-Owner Handoff

When narrative, parentage, or retention depends on another owner, publish an
A2A record containing exact paths, observed diagnostics, proposed disposition,
and remaining owner decision. Do not move or delete those files while waiting.

## Verification And Closeout

Validate all affected enforced scopes, run `git diff --check`, inspect exact
status, stage only Core-owned vault files, and complete continuity closeout in
the same cycle. Record retained warnings and owner handoffs explicitly.

Unsupported recovery, unreadable files, ambiguous ownership, or inability to
prove lossless restoration remains a blocker.
