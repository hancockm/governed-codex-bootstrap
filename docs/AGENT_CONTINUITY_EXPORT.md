# Agent Continuity Export

The complete continuity exporter is `tools/export_agent_thread_continuity.py`. It reads the exact Codex session JSONL source and selects only user-visible `response_item` messages whose role is `user` or `assistant`. It excludes hidden instructions, private reasoning, tool activity, duplicate event projections, encrypted material, and runtime records.

## Output contract

One transcript root contains:

- `visible_messages.jsonl`: exact selected source lines unless credential redaction was required;
- chronological Markdown parts containing HTML-escaped display projections;
- monthly and transcript MOCs with managed path-qualified links;
- `manifest.json` binding the source prefix, selected records, role and phase counts, redactions, schemas, and output inventory.

Detected credentials are replaced deterministically with `[REDACTED_CREDENTIAL]`. The manifest retains the original source-record hash without retaining the credential. Continuity remains source-only history, never canonical doctrine.

## Required closeout sequence

Set owner-specific values and run:

```powershell
python tools/export_agent_thread_continuity.py `
  --source <exact-session.jsonl> `
  --thread-id <thread-id> `
  --output-dir <registered-transcript-root> `
  --vault-target <vault-relative-transcript-root> `
  --agent-label <owner-label> `
  --manifest-schema-version <owner-manifest-schema> `
  --transcript-schema-version <owner-transcript-schema>
```

The first run is a dry run. Repeat it with `--apply`, then synchronize the owning vault scope. After navigation is final, run the same command with `--refresh-manifest`, apply the proposed refresh, and run it once more without `--apply`. The last run must report `changed: false`.

Run the owning vault check and `git diff --check`, inspect status, and stage only the registered transcript root. Do not add new durable reasoning after the exported boundary unless the transcript is exported again.

## Ownership and failure rules

- One thread ID belongs to exactly one continuity pack.
- Re-exporting the same thread to its owning root is allowed.
- Cross-owner copying, including an unfinished archive without a manifest, is rejected.
- Missing exact source is a closeout blocker; summaries and memory are not substitutes.
- Writes use a temporary sibling tree, retry bounded Windows replacements, fall back to in-place transactional restoration when necessary, and restore the prior tree after failure.
- Generated transcript files and manifest inventories are never hand-edited.
