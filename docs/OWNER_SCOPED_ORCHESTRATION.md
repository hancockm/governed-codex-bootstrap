# Owner-Scoped Orchestration

The owner-facing Sol lane selects and authorizes work, Terra implements one
bounded candidate, and Luna independently verifies the exact candidate commit.
These are development lanes; they do not confer runtime application authority.

The registry binds the lanes fail-closed:

| Lane | Model | Reasoning | Writes |
| --- | --- | --- | --- |
| Owner Orchestrator | `gpt-5.6-sol` | `xhigh` | owner publication and closeout only |
| Implementer | `gpt-5.6-terra` | `high` | packet-bounded candidate and local commit |
| Verification Runner | `gpt-5.6-luna` | `max` | none |

The tool implements the complete reusable lifecycle:

```text
check owner/profile
→ classify risk
→ prepare self-hashing packet
→ validate Terra receipt
→ bind Luna to exact packet + candidate
→ validate Luna receipt
→ record Sol disposition and immutable bundle
```

Use:

```text
python tools/owner_scoped_orchestration.py check-owner --owner core --active
python tools/owner_scoped_orchestration.py classify --owner core --description "..."
python tools/owner_scoped_orchestration.py prepare ...
python tools/owner_scoped_orchestration.py bind-runner ...
python tools/owner_scoped_orchestration.py validate ...
python tools/owner_scoped_orchestration.py record ...
```

The three deterministic tiers are `orchestrator_only`,
`orchestrator_plus_implementer`, and `full_team`. Runtime behavior, public
contracts, canonical doctrine, persistence, security/privacy, mathematical
behavior, external adapters, migrations, user-facing work, legal release,
cross-owner integration, or a required full suite trigger `full_team`. A caller
may escalate but cannot downgrade a triggered tier.

One saved-project Luna task is reused through all corrections in one cycle.
After the accepted exact-candidate receipt, no correction pending, delivery,
primary synchronization, terminal reconciliation, and worktree cleanup, Sol
archives completed or superseded subordinate tasks. Failed, blocked, and
user-input-needed tasks remain visible. Terra and Luna create compact receipts,
not independent continuity packs; the owner-facing Sol task owns the transcript.

A future owner cannot dispatch lanes merely because a skeleton exists. Core
must recognize its boundary, assign Git identity, install role and bootstrap
instructions, initialize continuity, create and validate an orchestration
profile, integrate owner adoption, and activate the registry entry.
