# External Critique Handoff

<!-- generated:breadcrumbs:start -->
<< Previous: [[40_Coordination/Instructions/Owner-Scoped Development Lanes]] | Up: [[40_Coordination/Instructions/README]] | Next: none >>
<!-- generated:breadcrumbs:end -->

## Purpose

An A2A handoff is first an immutable local coordination record. An optional
external invocation can send its complete critique prompt to another model
provider and capture that provider's response in the same advisory lifecycle.
The provider is a reviewer, not an implementation owner, canonical authority,
approval source, or substitute for repository evidence.

External critique is useful because model families have different training,
tooling, context behavior, costs, and failure profiles. A second model may
notice an assumption the owner-facing Codex task missed. No provider has a
permanent guaranteed specialty: compare the exact model/version on sealed
project examples and treat every result as a hypothesis requiring owner review.

## Provider Choice And Model Diversity

| Provider path | Useful reason to evaluate it | Boundary |
| --- | --- | --- |
| Anthropic Claude Code | An alternate vendor and model family for long-form architecture, policy, or edge-case critique | Capability varies by model and release; CLI output is not approval |
| Google Gemini CLI | An alternate model/tool stack that may provide a different context, multimodal, or reasoning perspective | Account, model, and authentication availability vary |
| MiniMax CLI (`mmx`) | A lower-cost additional review path for routine coding-plan critique | Lower cost does not establish accuracy or authority |
| Antigravity (`agy`) | A locally installed wrapper may expose another configured provider/model path | The wrapper's exact command, permissions, and provider must be reviewed |
| Codex CLI | A captured-output fallback using the same broad model ecosystem | It offers less provider independence than a different model family |

Choose the provider because its measured behavior fits the critique, not
because its brand implies correctness. Pin or record the selected model where
the CLI supports that option. For material workflows, compare usefulness,
false objections, missed risks, latency, cost, and data handling before making
one path the normal reviewer.

## Local Environment Setup

The repository does not install or authenticate external tools. Install each
CLI from its official source and authenticate it separately. Then copy the
public, non-secret command template:

```powershell
Copy-Item .env.example .env
```

Edit only the provider you intend to call. Supported settings are:

```text
PROJECT_<PROVIDER>_COMMAND=<executable and fixed non-secret arguments>
PROJECT_<PROVIDER>_INPUT_MODE=argument|stdin
PROJECT_<PROVIDER>_MODEL_ID=<exact selected model or deployment identity>
```

The allowlisted providers are `agy`, `claude`, `codex`, `gemini`, and `mmx`.
Process-environment values override `.env`. The loader does not interpolate
variables or execute a shell. Unknown `.env` fields are ignored by this tool.

Keep API keys, tokens, passwords, and session credentials out of `.env`.
Use the provider CLI's approved login flow, its credential store, or an
operating-system secret mechanism. The `.env` file is ignored by Git while
`.env.example` is tracked. Before first use, verify the exact installed CLI and
its command contract; examples can become stale when vendors release updates.
Set `MODEL_ID` explicitly and configure the command to select the same model;
an invocation without a model identity fails closed. The identity is evidence,
not proof that a remote service honored its selection.

The supplied examples use argument mode for current Claude, Gemini, and
MiniMax command shapes. Argument mode can expose the handoff prompt in a local
process listing while the command runs. Prefer stdin when the exact CLI accepts
it without changing the returned result.

A team that uses a provider's HTTP API directly may configure a reviewed local
wrapper command that accepts the handoff by stdin or final argument and emits
only the required Markdown on stdout. The wrapper, dependency, authentication,
and data path must be governed separately; this tool is not a generic secret
manager or direct provider SDK.

Official references:

- [Claude Code CLI reference](https://code.claude.com/docs/en/cli-usage)
- [Gemini CLI headless mode](https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/headless.md)
- [MiniMax CLI](https://github.com/MiniMax-AI/cli)

## Create The Handoff

First inspect the provider-neutral prompt without transmitting it:

```powershell
python tools/agent_to_agent_plan_handoff.py --topic <topic> --plan-file <path> --dry-run
```

Create a local record with no external call:

```powershell
python tools/agent_to_agent_plan_handoff.py --topic <topic> --plan-file <path> --apply
```

Or invoke one configured reviewer and capture its response:

```powershell
python tools/agent_to_agent_plan_handoff.py --topic <topic> --plan-file <path> --invoke claude --apply
python tools/agent_to_agent_plan_handoff.py --topic <topic> --plan-file <path> --invoke gemini --apply
python tools/agent_to_agent_plan_handoff.py --topic <topic> --plan-file <path> --invoke mmx --apply
```

Installation or authentication alone does not authorize invocation. The
owning Sol task must confirm provider access, expected cost, allowed data, and
user or organizational authorization before using `--invoke`.

## Data Egress And Security

External invocation sends the complete generated prompt, including the plan,
topic, current disagreement, and target-record reference, to the selected
provider. Do not include credentials, private reasoning, regulated data,
confidential source content, personal data, or proprietary material unless the
selected provider and account are expressly authorized for it.

The tool runs the configured executable without a shell from an isolated
temporary directory, bounds and redacts its local log, removes the invocation
directory, and records the provider, input mode, and command hash rather than
the command text. These controls reduce local leakage; they do not change the
external provider's retention, training, residency, subprocessors, or account
terms. Those remain deployment decisions.

## Completion Evidence

Success requires a response containing the shared critique preamble and each
required heading exactly once in the assigned atomic record:

1. Common Agreement
2. All Remaining Disagreements
3. Critical Weak Points
4. Convergence Move
5. Decision Status

A zero exit code, empty stdout, quota message, authentication message, local
log, or fluent answer without the required shape is not completion. The
record's invocation metadata and critique hash are evidence of what was
captured, not proof that the critique is correct.

The owner must verify every repository claim and disposition every substantive
point as `Accepted`, `Partially accepted`, `Rejected`, `Deferred`, or
`Requires user approval`.

## Failure And Fallback

Record an unavailable provider or malformed output safely. Do not silently
substitute a provider, model, reasoning level, account, or data-egress path.
Use a configured fallback only when the same authorization covers it. If no
provider succeeds, preserve the local handoff prompt and proceed only with
already authorized work or user direction.

## Publication

The owning agent evaluates and disposes every substantive point. Core or the
authorized owner publishes indexes and any accepted canonical consequences.
External models never edit unrelated files, shared indexes, canonical
documents, branches, or owner continuity merely because they returned a
critique.
