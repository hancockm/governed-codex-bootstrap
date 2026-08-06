# Agent Continuity Export

`tools/export_agent_thread_continuity.py` exports a complete bounded,
user-visible task history into exactly one owner continuity pack. Continuity
is noncanonical source context.

## Selection Boundary

The exporter reads the exact session JSONL and selects user-visible
`response_item` messages whose role is `user` or `assistant`. It freezes the
stable full-line source prefix observed at startup and records its byte count
and SHA-256.

It excludes hidden instructions, private reasoning, tool calls and outputs,
encrypted material, runtime state, and duplicate event projections. Detected
credentials are replaced deterministically with `[REDACTED_CREDENTIAL]`; the
manifest retains the original record hash without retaining plaintext.

## Output Contract

One transcript root contains:

- `visible_messages.jsonl`: exact selected source lines except required
  credential redaction;
- chronological Markdown parts with HTML-safe projections;
- monthly and transcript MOCs;
- `manifest.json` binding source prefix, selected records, schemas, role/phase
  counts, redactions, and output inventory.

Markdown is a display projection. The selected JSONL and hashes are the source
evidence. Generated records are never hand-edited.

## Required Closeout Sequence

Dry-run with owner-specific values:

```text
python tools/export_agent_thread_continuity.py \
  --source <exact-session.jsonl> \
  --thread-id <thread-id> \
  --output-dir <registered-transcript-root> \
  --vault-target <vault-relative-root> \
  --agent-label <owner-label> \
  --manifest-schema-version <manifest-schema> \
  --transcript-schema-version <transcript-schema>
```

Then:

1. repeat with `--apply`;
2. link the transcript root from the owning continuity MOC if it is new;
3. run vault navigation dry-run, apply, and a second dry-run;
4. rerun exporter with `--refresh-manifest --apply`;
5. rerun `--refresh-manifest` without apply and require `changed: false`;
6. validate the owning vault scope and `git diff --check`;
7. inspect status and stage only the registered owner archive;
8. commit/push closeout before the substantial task ends.

Do not introduce new durable reasoning after the recorded export boundary. If
the final response needs a new material conclusion, export again.

## Ownership Rules

- one thread ID belongs to one owner pack;
- re-export to the same owning root is allowed;
- cross-owner copying or mirroring is rejected;
- ownership changes use a new task and thread ID;
- subordinate lane receipts stay in the Sol owner's pack;
- A2A links carry cross-owner context without transcript duplication.

## Transaction And Recovery

The exporter builds the complete output tree before replacement, validates
unique ownership and file hashes, and writes transactionally. On Windows it
uses bounded replacement retries and a restoration path when directory
replacement cannot complete. A failed write restores the prior tree and does
not leave a partial archive.

The manifest distinguishes source-observed state from final post-navigation
output inventory. Navigation changes therefore require a manifest refresh.
Repeated export/refresh against unchanged source and navigation must be byte-
idempotent.

## Failure Rules

- Missing exact source is a closeout blocker; memory and summaries are not
  substitutes.
- A duplicate thread claim is an ownership blocker.
- A truncated or changing source prefix requires a new bounded observation.
- Credential detection never permits plaintext retention for completeness.
- A write or validation failure is not a successful export.
- Size warnings do not waive structural or ownership errors.
