# Git Reconciliation Guide

This guide explains the universal Git reconciler. Binding Git authority lives
in root [AGENTS.md](../AGENTS.md); this document supplies commands, evidence interpretation,
and recovery procedures.

The reconciler is fail-closed. It reports facts and validates an owner's
declared disposition. It never decides that a branch should be merged,
rebased, deleted, or superseded.

## Start-of-work inspection

Run from any worktree:

```text
python tools/origin_reconciler.py inspect --agent <owner>
```

Inspection fetches and prunes the configured remote unless `--no-fetch` is
provided. It reports:

- local and remote branch heads;
- upstream and publication state;
- branch-only and target-only commits;
- exact target reachability;
- stable patch-ID replacement mappings;
- unmapped, empty, and merge commits;
- owner and confidence from strict namespace policy;
- registered worktrees and physical worktree-root entries;
- status-command success, cleanliness, and active Git operations;
- the primary checkout and primary-branch divergence.

Use JSON for machine consumption and Markdown for a durable record:

```text
python tools/origin_reconciler.py inspect --agent <owner> --format json
python tools/origin_reconciler.py inspect --agent <owner> --format markdown
```

Optional output files must be under ignored `tmp/`:

```text
python tools/origin_reconciler.py inspect --agent <owner> --format json --output tmp/reconciliation/inspect.json
```

A nonzero `git status` exit is `inspection_failed`, never `clean`. Dirty or
untracked state, unknown ownership, active operations, unpublished commits,
and ambiguous patch mappings remain visible evidence.

## Evidence, not inferred decisions

Ahead/behind counts are not dispositions:

- behind-only may mean an old checkpoint, not permission to move it;
- ahead-only may be accepted work, abandoned work, or unreviewed work;
- diverged may contain both accepted and obsolete changes;
- a clean worktree says nothing about whether the branch should land;
- a remote branch proves publication, not integration authority.

Inspect the owner-authored A2A or continuity disposition before integration.
Legacy branch prefixes may help reporting but never grant file ownership.
Unqualified prefixes such as [docs/](.), `integration/`, `reconcile/`, or
`safety/` remain ambiguous.

## Durable closeout evidence

Every branch-owning cycle records one disposition:

```text
python tools/origin_reconciler.py closeout \
  --agent <owner> \
  --branch <owner/slice> \
  --disposition landed
```

### Landed

`landed` succeeds only when every nonempty, non-merge branch-only commit is:

- exactly reachable from the configured target; or
- mapped one-to-one to an unambiguous stable patch-ID replacement on the
  target.

When integration changes hashes through cherry-pick, rebase, or squash,
retain original-to-replacement mappings with the stable patch IDs. Empty and
merge commits require explicit handling; they are not silently ignored.

### Awaiting named integrator

Use this only when a non-Core owner has pushed accepted candidate work but
cannot integrate the primary branch:

```text
python tools/origin_reconciler.py closeout \
  --agent <owner> \
  --branch <owner/slice> \
  --disposition awaiting_named_integrator \
  --named-integrator core \
  --remote-branch origin/<owner/slice> \
  --remaining-action "Core reviews and integrates the exact commits" \
  --evidence-ref <durable-record>
```

This disposition exits nonzero because it is routed but nonterminal. Record
the pushed branch, exact commits, target, named integrator, remaining action,
and durable A2A/continuity evidence. The owner may not report the branch as
complete or start the next same-role gate without explicit parallel-work
authorization.

### Superseded

`superseded` requires explicit authorized-owner evidence:

```text
python tools/origin_reconciler.py closeout \
  --agent <owner> \
  --branch <owner/slice> \
  --disposition superseded \
  --supersession "Replaced by <branch-or-commit>" \
  --evidence-ref <authorization-record>
```

Supersession may name a replacement or a deliberate abandonment. The tool
validates evidence shape; it does not create authorization.

## Core integration inbox

Core runs:

```text
python tools/origin_reconciler.py inbox --agent core
```

The inbox fetches/prunes by default and lists published, known-owner branches
with branch-only commits that have neither exact nor complete patch-equivalent
landing evidence. An active worktree does not suppress an item. Unknown-owner
branches are separate diagnostics.

Exit codes:

| Code | Meaning |
| --- | --- |
| `0` | Requested state is verified and the inbox is clear. |
| `2` | Reconciliation, integration, or owner disposition remains. |
| `3` | Inspection or safety failed. |

Core processes named requests in order and reads the owner-authored evidence
before acting. Inbox membership is not permission to merge or supersede.

## Core-only primary synchronization

Only Core may run:

```text
python tools/origin_reconciler.py sync-main --agent core
```

Synchronization requires:

- successful fetch;
- the repository-root primary checkout on the configured primary branch;
- no tracked or untracked changes;
- no active merge, rebase, cherry-pick, revert, or bisect;
- no local-only primary commits;
- a resolvable remote primary branch.

The only mutation is:

```text
git merge --ff-only origin/master
```

The tool never switches branches, resets, rebases, resolves conflicts,
discards files, or deletes branches/worktrees. It verifies exact local/remote
equality afterward. A newly created bootstrap has no remote by design, so
sync and remote-relative affected testing fail closed until a remote is
explicitly configured.

## Staging and publication

Before every commit:

```text
git status --short --untracked-files=all --ignore-submodules=all
git add -- <explicit-task-paths>
git diff --cached --name-status
git diff --cached --check
```

Do not absorb editor state, generated attachments, concurrent changes, or
another owner's files. A push is transport only. After a Core push changes the
remote primary branch, the same integration cycle must run `sync-main`, verify
a clean primary checkout, and rerun the Core inbox.

## Worktree lifecycle

Normal work uses `.worktrees/<owner>-<slice>`. Before removal, verify:

1. the exact path is inside the configured worktree root;
2. `git status --porcelain=v1 --untracked-files=all --ignore-submodules=all`
   succeeds and is empty;
3. no Git operation is active;
4. branch disposition is terminal;
5. remote evidence is preserved.

Then use `git worktree remove <exact-path>` and confirm the path disappeared
from `git worktree list`. If a registered worktree contains a deinitialized
submodule and ordinary removal refuses it, use force only after the same exact
cleanliness and terminal-evidence checks. Delete a physical leftover only when
Git has deregistered it and the resolved exact path remains inside the
configured root.

## Recovery examples

- **Dirty primary:** preserve and classify every path. Do not sync until the
  owning change is committed, routed, or explicitly discarded.
- **Local-only primary commit:** create a preservation branch and obtain a
  disposition; never reset merely to make the status green.
- **Patch-equivalent branch:** record every original-to-replacement mapping
  before cleanup.
- **Inspection failure:** fix the command/environment and rerun. Never convert
  failure into clean evidence.
- **Unknown owner:** route ownership review before integration or deletion.
- **No remote:** continue local work if authorized, but do not claim remote
  reconciliation or primary synchronization.

Reconciliation does not authorize cleanup. Cleanup follows only after terminal
evidence and the separate worktree safety checks.
