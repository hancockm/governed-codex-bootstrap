# Repository Guidance

This file is the repository-wide operational authority. Detailed procedures
live in [docs/](docs); role-specific ownership and startup instructions live under
[roles/](roles) and in the registered continuity pack. Domain or product doctrine
must be derived from this project's research and canonical vault, never from
the reference repository used to design this bootstrap.

## Agent Role Instructions

Before substantial work, read the active owner's role, bootstrap prompt,
continuity MOC, and owner profile. Core starts at:

- [roles/core/ROLE.md](roles/core/ROLE.md)
- [roles/core/BOOTSTRAP.md](roles/core/BOOTSTRAP.md)
- [Project_Obsidian_Vault/30_Core/Core Bootstrap.md](Project_Obsidian_Vault/30_Core/Core%20Bootstrap.md)
- [Project_Obsidian_Vault/30_Core/Continuity/Core Continuity MOC.md](Project_Obsidian_Vault/30_Core/Continuity/Core%20Continuity%20MOC.md)

Shared vault-local coordination instructions begin at:

- [Project_Obsidian_Vault/40_Coordination/Instructions/README.md](Project_Obsidian_Vault/40_Coordination/Instructions/README.md)

Future-owner templates are non-authorizing. Only an owner marked `active` in
the owner registry may dispatch work. Role instructions may narrow ownership
or add checks, but they may not weaken this file's Git, continuity, safety, or
evidence rules.

## Mandatory Agent Continuity Closeout

Every substantial owner task exports its complete bounded user-visible
transcript to exactly one registered continuity pack. Use
[tools/export_agent_thread_continuity.py](tools/export_agent_thread_continuity.py) with the exact session source,
thread ID, owner label, owner schemas, transcript directory, and vault target.

A valid export:

- selects every user-visible `user` and `assistant` response-item record in a
  stable full-line source prefix;
- excludes hidden instructions, private reasoning, tool calls and outputs,
  encrypted content, runtime state, and duplicate projections;
- redacts detected credentials without retaining their plaintext;
- records source-prefix, selected-record, redaction, and output hashes;
- generates display-safe Markdown and chronological MOCs transactionally.

Dry-run first, apply the verified export, synchronize the owning vault scope,
refresh the manifest against post-navigation bytes, and require an idempotent
dry refresh. A narrative `no-update` disposition never waives transcript
export. If the exact source is unavailable, mark closeout incomplete rather
than reconstructing it from memory, summaries, or A2A notes.

One thread belongs to one owner pack. Ownership changes require a new task and
thread ID. Cross-owner context travels through A2A records and links, not
duplicate transcript archives. Terra and Luna produce compact receipts in the
owner's pack; they do not become independent continuity owners.

## User Collaboration And Decision Semantics

- A question, attachment, research note, critique, or hypothetical design is
  context, not implementation authorization.
- An accepted plan authorizes only its recorded scope, owner boundaries, and
  delivery conditions.
- The latest explicit user instruction controls intent. Current canonical
  documents control accepted project doctrine. Source, tests, configuration,
  receipts, and Git history establish implemented behavior.
- Continuity and A2A records preserve context and convergence but do not
  promote themselves into canonical truth.
- Challenge material assumptions and expose disagreement directly. Do not
  silently choose the interpretation that makes implementation easiest.
- Preserve distinctions between source and derived state, observation and
  authority, passive receipt and executed decision, proposal and truth.
- Do not create feature-local replacements for existing public contracts,
  parsers, ledgers, repositories, or schemas to bypass an owner boundary.
- Route another owner's work through an A2A request. Do not edit that owner's
  semantics, UI, doctrine, continuity, or private implementation.

## Mathematical Evidence And Verification

Mathematical audits are findings-only unless correction is explicitly
authorized. Do not supply numerical or algebraic claims from memory or mental
arithmetic. Use SymPy for exact symbolic constants, identities, rational
comparisons, and exponents; use NumPy for the finite floating-point behavior
the project executes. Cite the executable witness, repository constant, or
test output for each material claim.

For each accepted mathematical change, reconcile the active implementation,
configuration, tests, and canonical description. Distinguish analytic
invariants from rounding, overflow, underflow, tolerance, and platform
behavior. Add a focused executable witness. Metadata remains non-semantic and
non-geometric unless a separately accepted contract promotes it.

## Planning Evidence Cutoff

For planning-only work, freeze decision evidence at the first successfully
inspected repository state. Record the baseline commit and relevant worktree
state. Separate:

- **selection evidence**: canonical order, contracts, ownership,
  prerequisites, configuration, and relevant tests;
- **delivery conditions**: later unrelated commits, navigation drift,
  generated files, or other-owner worktree churn.

Reopen a conclusion only when a later change modifies the selected work, a
material prerequisite, ownership, authorization, or essential evidence. Do
not repeatedly refresh the entire repository in pursuit of a perfect
operational snapshot. If the user asks for reconsideration, start a new dated
baseline.

## Integrated Planning And Implementation Cycle

A planning cycle includes reorientation, assumption and ownership analysis,
the source-only work-selection audit, relevant A2A critique, and an approval-
ready plan. It does not implement the proposed gate.

After approval, the implementation cycle includes the accepted change,
focused and broader verification, canonical/package documentation, capability
evidence, A2A completion updates, generated navigation, scoped Git delivery,
and continuity closeout. These process artifacts do not consume a separate
user turn. Separate feature and continuity commits are allowed, but both must
be delivered before the cycle is reported complete.

Spillover requires a genuine blocker such as missing exact source, unresolved
ownership, a security/licensing decision, a target-file conflict, or a real
test failure. Documentation volume and unrelated repository churn are not
blockers.

## Universal Work-Selection Audit

Every substantial next-step selection produces one source-only work-selection
audit under the configured coordination scope. The audit is advisory: it does
not create ownership, authorization, or an implementation gate. A missing or
adverse audit must remain visible but cannot silently override the user or the
owner registry.

## Agent-to-Agent Critique Workflow

Before a substantial plan, inspect the coordination MOC, update log, and only
the records relevant to the current boundary. A critique uses:

1. Common Agreement
2. All Remaining Disagreements
3. Critical Weak Points
4. Convergence Move
5. Decision Status

Record each substantive point as `Accepted`, `Partially accepted`, `Rejected`,
`Deferred`, or `Requires user approval`. External critique is advisory. Core
alone promotes accepted conclusions to thesis, architecture, specification,
roadmap, or capability registry.

Use [tools/agent_to_agent_plan_handoff.py](tools/agent_to_agent_plan_handoff.py) for immutable content-addressed
records. The compatibility command is [tools/agent_to_agent_handoff.py](tools/agent_to_agent_handoff.py).
External CLI invocation is optional, explicitly configured, and successful
only when the assigned record changes; an empty response or zero process exit
is not evidence of a completed critique.

The local handoff record and the external critique are separate lifecycle
steps. Configure an external provider only through the allowlisted
`PROJECT_<PROVIDER>_COMMAND`, `PROJECT_<PROVIDER>_INPUT_MODE`, and
`PROJECT_<PROVIDER>_MODEL_ID` settings in the ignored repository-root `.env`,
using [.env.example](.env.example) as the public template. The declared model identity must
match the model selected by the configured command. Do not store provider
credentials in `.env`; authenticate the installed CLI through its approved
credential store or operating-system secret mechanism. Invocation transmits
the complete handoff prompt to the selected provider and therefore requires an
explicit data-egress, confidentiality, cost, and authorization decision.
Different model families can provide useful independent failure profiles, but
their output remains advisory and must be verified against repository evidence
and dispositioned by the owning agent.

## Coding Discipline

### Think Before Coding

Inspect discoverable repository facts before asking the user. State material
assumptions and stop when unresolved ambiguity changes scope, contracts,
ownership, security, or irreversible outcomes. Prefer the simpler design when
it satisfies the accepted behavior.

### Prefer The Smallest Sufficient Change

Implement only accepted behavior. Reuse current public patterns. Avoid
speculative abstractions, premature configuration, adjacent refactors, and
format-only churn. Every changed line must trace to the task, its tests, or
cleanup made necessary by those changes.

### Persistence Boundaries

Business and orchestration code depends on storage-neutral repository ports.
Database paths, schemas, queries, transactions, migrations, driver settings,
and ORM details belong in selected persistence adapters. Preserve atomic
domain operations such as claim-or-replay; do not replace them with vulnerable
generic `get()` then `insert()` choreography. Do not introduce a generic CRUD
layer or persistence owner without a demonstrated, approved need.

### Execute Against Verifiable Goals

Define concrete success criteria before editing. Reproduce bugs with a test,
exercise invalid inputs for validators, and establish before/after evidence
for refactors. Iterate with the narrowest checks, then run the broader boundary
required by risk. Report unrelated failures without absorbing them into scope.

### Test Execution Workflow

Use the repository runner rather than repeating the full suite during active
debugging:

```text
python tools/test_runner.py focused <tests>
python tools/test_runner.py failed
python tools/test_runner.py affected --base <ref>
python tools/test_runner.py broad
python tools/test_runner.py full
```

Focused work stops early. `failed` uses the local pytest failure cache without
falling back to the full suite. Affected selection is fail-closed through the
versioned impact map. Broad runs stop after a bounded number of failures.
Full runs parallel-safe tests once and then exclusive tests serially. A failed
full run returns to serial failed triage; do not repeatedly relaunch all
workers while debugging.

### Temporary Test Artifacts

All scratch data, reproductions, caches, and run output belong under `tmp/`.
Do not create root-level `.pytest-*`, `t0`, or `t1` directories. Use narrow
task-specific names and remove task-specific output before closeout. A shared
pytest failure cache may remain only at the configured ignored path. Report
the exact path and recovery action for any artifact that cannot be removed.

## Source Documentation

Follow [docs/SOURCE_DOCUMENTATION_STYLE.md](docs/SOURCE_DOCUMENTATION_STYLE.md). Public source uses native type
annotations plus concise Google-style docstrings. Run
`python tools/source_doc_audit.py` before closing source changes. Do not edit
vendored or generated source merely to satisfy local style.

### Folder Documentation

Every maintained repository directory has a local `README.md` registered in
[configs/documentation_system_v1.json](configs/documentation_system_v1.json). The README explains the directory's
purpose, significant files or subdirectories, and change discipline. Source,
tool, configuration, test, and third-party directories must describe each
maintained immediate artifact; generated-output directories identify their
generator and prohibit hand edits.

When adding, renaming, moving, or retiring a maintained artifact, update its
nearest folder README and the folder-documentation inventory in the same
change. Temporary, cache, Git-internal, and task-worktree directories are
excluded because they are not maintained repository content. Run
`python tools/architecture_conformance.py` to verify coverage.

## Feature Agent Documentation

Follow [docs/FEATURE_AGENT_DOCUMENTATION_STANDARD.md](docs/FEATURE_AGENT_DOCUMENTATION_STANDARD.md). An active feature
package documents purpose, status, ownership, non-ownership, module map,
public imports, test expectations, and vault/role links before more source is
added. Feature owners consume public Core contracts and request missing
boundaries through A2A rather than recreating them.

Every registered owner profile maps exactly four owner canonical documents:
Core Thesis, Architecture, Spec, and Implementation Roadmap. Core creates all
four in the inactive scaffold; the proposed owner challenges and adopts them;
and repository conformance blocks activation if any path is missing. These
documents govern only the accepted owner scope and cannot override project-
wide Core canon or another owner's public contract.

## Owner-Scoped Orchestration

Owner Orchestrator (Sol) controls authority, scope, review, publication, and
continuity. Implementer (Terra) makes one packet-bounded local candidate.
Verification Runner (Luna) independently verifies the exact candidate without
repository writes. Required model bindings and risk escalation are fail-
closed; no silent substitution is allowed.

Each lane uses its owner-neutral shared prompt artifact from [roles/shared/](roles/shared),
composed with the exact owner profile and task packet. Shared prompts cannot
grant ownership or relax the root policy, and a missing lane template is a
fail-closed orchestration configuration error.

One saved-project Luna task is reused through every correction in an
implementation cycle. A projectless runner task is invalid. Luna's accepted
receipt is not archive acknowledgment. Sol archives accepted or superseded
subordinate tasks only after receipt capture, no pending correction, delivery,
primary synchronization, terminal reconciliation, and worktree cleanup.
Before closeout, Sol supplies the exact recorded-bundle hash, captured Terra and
Luna receipt hashes, every packet-bound subordinate task ID and archive
disposition, terminal `landed` or authorized `superseded` reconciliation,
verified primary-branch synchronization, verified packet-worktree removal, and
the host archival acknowledgment. The repository tool must validate and bind
those facts in an immutable finalization record before the cycle may be called
closed. Failed, blocked, or user-input-needed tasks remain visible. The tool
records host archival evidence but cannot perform the host archive operation;
that action remains Sol's runtime responsibility.

## Git Staging, Commit, and Push Discipline

Root [AGENTS.md](AGENTS.md) is the sole repository-wide Git authority. Before staging,
inspect `git status --short --untracked-files=all --ignore-submodules=all` and
treat a nonzero exit as inspection failure. Separate current-task changes from
pre-existing or concurrent state. Stage explicit paths only, inspect
`git diff --cached --name-status` and `git diff --cached --check`, and push only
the intended commit or branch.

### Mandatory Branch Reconciliation

Every branch-owning agent runs:

```text
python tools/origin_reconciler.py inspect --agent <owner>
python tools/origin_reconciler.py closeout --agent <owner> --branch <branch> --disposition <state>
```

A pushed branch is not reconciled. `landed` requires exact reachability or a
complete unambiguous stable patch-ID mapping. `superseded` requires explicit
owner authorization and replacement/abandonment evidence.
`awaiting_named_integrator` is a routed blocker, not completion. Non-Core
owners must not update, reset, merge, or rebase the primary branch.

Core is the single primary-branch integrator. At startup and closeout, Core
runs `origin_reconciler.py inbox --agent core`. A nonempty inbox blocks a new
Core gate unless every item is landed, authorized as superseded, or explicitly
allowed to proceed in parallel. Only Core may run `sync-main --agent core`,
which uses a clean-primary `merge --ff-only` and verifies exact equality with
the configured remote primary branch.

### Branch Landing And Disposition

Every implementation branch ends in one durable owner-authored disposition:
`landed`, `superseded`, or `awaiting_named_integrator`. Record exact commits,
target, patch mappings when hashes changed, evidence reference, and remaining
action. A final chat statement is not durable evidence.

### Worktree Creation And Closeout

Reserve the primary checkout for clean Core integration. Normal work uses the
configured repository-local `.worktrees/<owner>-<slice>` root. Before removal,
verify exact registration, path containment, clean status, no active Git
operation, terminal disposition, and remote evidence. Remove with
`git worktree remove`, verify disappearance from `git worktree list`, and
delete only an exact verified leftover directory if Git deregisters but leaves
files. Worktree cleanup never authorizes discarding unowned changes.

## Average-user UX gate

For user-facing work, identify the ordinary primary user and shortest safe
path. Test plain-language comprehension, actionable error recovery, preserved
input after recoverable failures, keyboard access, focus order, labels, zoom,
reduced motion, responsive layout, and explicit unavailable/denied/degraded
states. Expert controls must not obscure the common path.

## Vault Information Architecture

The Obsidian vault is the maintained narrative reading surface. Canonical
prose has one location; every managed child has one parent; links are path-
qualified; MOCs contain narrative descriptions rather than filename dumps;
and generated breadcrumbs are maintainer-owned. Run report/check/navigation
through [tools/vault_maintainer.py](tools/vault_maintainer.py). Never hand-edit generated blocks or
destructively split notes without a lossless migration and restoration proof.

## Documentation-System Parity

Every governance instruction and maintained Markdown contract is classified
by [configs/documentation_system_v1.json](configs/documentation_system_v1.json). A short placeholder is not an
equivalent operational document. Changes must retain required headings,
commands, authority boundaries, recovery behavior, and neutral terminology.
Run `python tools/architecture_conformance.py` before closeout.
